import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from battery_charge_controller.calendar import Segment, Season, is_workday, season_for, window_for
from battery_charge_controller.config import AppConfig, ConfigurationError
from battery_charge_controller.decision import DecisionAction, estimate_day_minutes, evaluate_segment
from battery_charge_controller.settings import SettingsCoordinator, SettingsError, UserSettings
from battery_charge_controller.storage import JsonStateStore


WARSAW=ZoneInfo("Europe/Warsaw")


def base_options():
	options={
		"battery_soc_entity": "sensor.deye_deye_10kw_battery_soc",
		"grid_charge_entity": "switch.deye_deye_10kw_grid_charge_enabled",
		"prog5_time_entity": "select.deye_deye_10kw_prog5_time",
		"timezone": "Europe/Warsaw",
		"summer_start": "04-01",
		"winter_start": "10-01",
		"night_start": "22:00",
		"night_end": "06:55",
		"summer_day_start": "16:10",
		"summer_day_end": "18:55",
		"summer_prog5_time": "19:00",
		"winter_day_start": "13:10",
		"winter_day_end": "15:55",
		"winter_prog5_time": "16:00",
		"night_full_charge_minutes": 157,
		"night_reference_soc_range": 80,
		"night_safety_minutes": 15,
		"day_full_charge_minutes": 201,
		"day_reference_soc_range": 80,
		"day_safety_minutes": 0,
		"evaluation_seconds": 300,
		"soc_stale_seconds": 180,
		"verify_delay_seconds": 0,
		"verified_mismatch_retries": 2,
		"reset_capacity": 20,
		"active_charge_option": "Allow Grid & Gen",
		"reset_charge_option": "Allow Gen",
		"mqtt_base_topic": "battery_charge_controller",
		"mqtt_discovery_prefix": "homeassistant",
		"device_name": "Ładowanie baterii",
		"log_level": "INFO",
	}
	for index in range(1, 7):
		options[f"prog{index}_capacity_entity"]=f"number.deye_deye_10kw_prog{index}_capacity"
		options[f"prog{index}_charge_entity"]=f"select.deye_deye_10kw_prog{index}_charge"
	return options


class ChargeConfigurationTests(unittest.TestCase):
	def test_parses_entities_models_and_hard_stops(self):
		config=AppConfig.from_options(base_options())
		self.assertEqual(config.entities.capacity[0], "number.deye_deye_10kw_prog1_capacity")
		self.assertEqual(config.entities.capacity[3], "number.deye_deye_10kw_prog4_capacity")
		self.assertEqual(config.night.full_charge_minutes, 157)
		self.assertEqual(config.day.full_charge_minutes, 201)
		self.assertEqual(str(config.summer_day_end), "18:55")
		self.assertEqual(str(config.winter_day_end), "15:55")

	def test_rejects_wrong_entity_domain(self):
		options=base_options()
		options["prog1_capacity_entity"]="sensor.wrong"
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_duplicate_control_entity(self):
		options=base_options()
		options["prog2_capacity_entity"]=options["prog1_capacity_entity"]
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_day_stop_not_before_prog5(self):
		options=base_options()
		options["summer_day_end"]="19:00"
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_overlapping_day_and_night_windows(self):
		options=base_options()
		options["summer_day_end"]="22:30"
		options["summer_prog5_time"]="23:00"
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_nonexistent_calendar_date(self):
		options=base_options()
		options["summer_start"]="02-31"
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)


class ChargeCalendarTests(unittest.TestCase):
	def setUp(self):
		self.config=AppConfig.from_options(base_options())

	def test_season_boundaries(self):
		self.assertEqual(season_for(date(2026, 4, 1), self.config), Season.SUMMER)
		self.assertEqual(season_for(date(2026, 9, 30), self.config), Season.SUMMER)
		self.assertEqual(season_for(date(2026, 10, 1), self.config), Season.WINTER)

	def test_weekends_and_polish_holidays_are_not_workdays(self):
		for value in (date(2026, 6, 14), date(2026, 4, 6), date(2026, 12, 24), date(2026, 12, 25)):
			with self.subTest(value=value):
				self.assertFalse(is_workday(value))

	def test_day_hard_stops_follow_season(self):
		summer=window_for(datetime(2026, 6, 15, 17, 0, tzinfo=WARSAW), Segment.DAY, self.config)
		winter=window_for(datetime(2026, 1, 15, 14, 0, tzinfo=WARSAW), Segment.DAY, self.config)
		self.assertEqual(summer.end.strftime("%H:%M"), "18:55")
		self.assertEqual(winter.end.strftime("%H:%M"), "15:55")

	def test_night_crossing_midnight_has_one_execution_key(self):
		before=window_for(datetime(2026, 10, 24, 23, 30, tzinfo=WARSAW), Segment.NIGHT, self.config)
		after=window_for(datetime(2026, 10, 25, 2, 30, fold=1, tzinfo=WARSAW), Segment.NIGHT, self.config)
		self.assertEqual(before.execution_key, after.execution_key)
		self.assertEqual(after.end.strftime("%H:%M"), "06:55")


class ChargeDecisionTests(unittest.TestCase):
	def setUp(self):
		self.config=AppConfig.from_options(base_options())
		self.now=datetime(2026, 9, 23, 23, 0, tzinfo=WARSAW)
		self.window=window_for(self.now, Segment.NIGHT, self.config)

	def evaluate(self, **overrides):
		values={
			"segment": Segment.NIGHT,
			"now": self.now,
			"window": self.window,
			"soc": 30,
			"threshold": 40,
			"target": 80,
			"enabled": True,
			"active": False,
			"model": self.config.night,
		}
		values.update(overrides)
		return evaluate_segment(**values)

	def test_night_waits_until_latest_safe_start(self):
		decision=self.evaluate()
		self.assertEqual(decision.action, DecisionAction.WAIT)
		self.assertAlmostEqual(decision.estimated_minutes, 98.125)

	def test_night_starts_at_latest_safe_start(self):
		estimate=98.125+15
		start=self.window.end-timedelta(minutes=estimate)
		decision=self.evaluate(now=start)
		self.assertEqual(decision.action, DecisionAction.START)

	def test_day_taper_matches_node_red_model(self):
		self.assertAlmostEqual(estimate_day_minutes(98, 100, self.config.day), 11.525)
		self.assertAlmostEqual(estimate_day_minutes(99, 100, self.config.day), 8.2125)

	def test_disabled_invalid_and_above_threshold_do_not_start(self):
		self.assertEqual(self.evaluate(enabled=False).action, DecisionAction.DISABLED)
		self.assertEqual(self.evaluate(threshold=90, target=80).action, DecisionAction.INVALID_SETTINGS)
		self.assertEqual(self.evaluate(soc=80, threshold=75).action, DecisionAction.OBSERVE)

	def test_target_reached_and_hard_stop_request_reset_when_active(self):
		self.assertEqual(self.evaluate(active=True, soc=80).action, DecisionAction.RESET)
		self.assertEqual(self.evaluate(active=True, now=self.window.end).action, DecisionAction.RESET)

	def test_dst_fallback_uses_elapsed_time_instead_of_wall_clock_subtraction(self):
		now=datetime(2026, 10, 25, 2, 30, fold=0, tzinfo=WARSAW)
		window=window_for(now, Segment.NIGHT, self.config)
		model=type(self.config.night)(300, 80, 0)
		decision=evaluate_segment(segment=Segment.NIGHT, now=now, window=window, soc=20, threshold=30, target=100, enabled=True, active=False, model=model)
		self.assertEqual(decision.action, DecisionAction.WAIT)
		self.assertEqual(decision.start_at.strftime("%H:%M"), "02:55")
		self.assertEqual(decision.start_at.fold, 0)
		self.assertEqual(
			int((decision.start_at.astimezone(ZoneInfo("UTC"))-now.astimezone(ZoneInfo("UTC"))).total_seconds()),
			1500,
		)


class ChargeSettingsTests(unittest.TestCase):
	def setUp(self):
		self.temporary=tempfile.TemporaryDirectory()
		self.path=Path(self.temporary.name) / "state.json"
		self.store=JsonStateStore(self.path)

	def tearDown(self):
		self.temporary.cleanup()

	def test_first_start_defaults_are_disabled(self):
		settings=UserSettings.defaults()
		self.assertEqual((settings.night_threshold, settings.night_target), (30, 80))
		self.assertEqual((settings.day_threshold, settings.day_target), (75, 80))
		self.assertFalse(settings.night_enabled)
		self.assertFalse(settings.day_enabled)

	def test_atomic_round_trip_preserves_settings_and_completed_keys(self):
		settings=UserSettings.defaults()
		self.store.save({"settings": settings.to_dict(), "completed": ["night:2026-09-24"]})
		loaded=self.store.load()
		self.assertEqual(UserSettings.from_dict(loaded["settings"]), settings)
		self.assertEqual(loaded["completed"], ["night:2026-09-24"])

	def test_rejects_target_below_threshold_without_saving(self):
		coordinator=SettingsCoordinator(self.store, UserSettings.defaults())
		coordinator.apply_number("night_threshold", 70)
		with self.assertRaises(SettingsError):
			coordinator.apply_number("night_target", 60)
		self.assertEqual(coordinator.settings.night_target, 80)

	def test_switch_accepts_only_on_and_off(self):
		coordinator=SettingsCoordinator(self.store, UserSettings.defaults())
		with self.assertRaises(SettingsError):
			coordinator.apply_switch("day_enabled", "yes")
		coordinator.apply_switch("day_enabled", "ON")
		self.assertTrue(coordinator.settings.day_enabled)


if __name__ == "__main__":
	unittest.main()
