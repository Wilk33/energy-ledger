import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from battery_charge_controller.calendar import Segment, window_for
from battery_charge_controller.config import AppConfig
from battery_charge_controller.mqtt import MqttCommand
from battery_charge_controller.runtime import BatteryChargeRuntime
from battery_charge_controller.settings import SettingsCoordinator, UserSettings
from battery_charge_controller.storage import JsonStateStore
from tests.test_charge_core import base_options


WARSAW=ZoneInfo("Europe/Warsaw")


class FakeHomeAssistant:
	def __init__(self, config):
		entities=config.entities
		self.states={entities.battery_soc: "50", entities.grid_charge: "off", entities.prog5_time: "16:00"}
		self.states.update({entity: str(config.reset_capacity) for entity in entities.capacity})
		self.states.update({entity: config.reset_charge_option for entity in entities.charge})

	async def get_state(self, entity_id):
		return self.states[entity_id]

	async def state_events(self, watched):
		if False:
			yield None


class FakeExecutor:
	def __init__(self, ha, config):
		self.ha=ha
		self.config=config
		self.started=[]
		self.reset_reasons=[]
		self.prog5_values=[]

	async def start_charge(self, segment, target):
		self.started.append((segment, target))
		self.ha.states[self.config.entities.grid_charge]="on"

	async def full_reset(self, reason):
		self.reset_reasons.append(reason)
		self.ha.states[self.config.entities.grid_charge]="off"

	async def sync_prog5_time(self, value):
		self.prog5_values.append(value)
		self.ha.states[self.config.entities.prog5_time]=value


class FakeMqtt:
	def __init__(self):
		self.discovery_count=0
		self.settings=[]
		self.durations=[]

	def publish_discovery(self):
		self.discovery_count+=1

	def publish_settings(self, settings):
		self.settings.append(settings)

	def publish_durations(self, starts, ends):
		self.durations.append((starts, ends))

	def close(self):
		pass


class ChargeRuntimeTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		options=base_options()
		options["soc_stale_seconds"]=180
		self.config=AppConfig.from_options(options)
		self.temporary=tempfile.TemporaryDirectory()
		self.store=JsonStateStore(Path(self.temporary.name) / "state.json")
		settings=UserSettings(40, 80, 75, 80, True, True)
		self.coordinator=SettingsCoordinator(self.store, settings)
		self.ha=FakeHomeAssistant(self.config)
		self.executor=FakeExecutor(self.ha, self.config)
		self.mqtt=FakeMqtt()
		self.runtime=BatteryChargeRuntime(self.config, self.ha, self.executor, self.mqtt, self.coordinator)

	async def asyncTearDown(self):
		self.temporary.cleanup()

	async def test_startup_syncs_summer_prog5_when_day_switch_is_off(self):
		self.coordinator.settings=UserSettings(40, 80, 75, 80, True, False)
		await self.runtime.initialize(datetime(2026, 6, 15, 12, 0, tzinfo=WARSAW))
		self.assertEqual(self.executor.prog5_values, ["19:00"])
		self.assertEqual(self.mqtt.discovery_count, 1)

	async def test_startup_outside_window_resets_active_grid_charge(self):
		self.ha.states[self.config.entities.grid_charge]="on"
		await self.runtime.initialize(datetime(2026, 6, 15, 12, 0, tzinfo=WARSAW))
		self.assertEqual(self.executor.reset_reasons, ["startup_reconciliation"])

	async def test_startup_resets_partial_program_even_when_grid_is_off(self):
		self.ha.states[self.config.entities.capacity[0]]="80"
		await self.runtime.initialize(datetime(2026, 6, 15, 12, 0, tzinfo=WARSAW))
		self.assertEqual(self.executor.reset_reasons, ["startup_partial_state"])

	async def test_turning_off_active_night_switch_resets_immediately(self):
		self.runtime.active_segment=Segment.NIGHT
		self.runtime.active_window=window_for(datetime(2026, 6, 15, 23, 0, tzinfo=WARSAW), Segment.NIGHT, self.config)
		await self.runtime.apply_command(MqttCommand("night_enabled", "OFF"), datetime(2026, 6, 15, 23, 0, tzinfo=WARSAW))
		self.assertEqual(self.executor.reset_reasons, ["night_disabled"])

	async def test_turning_off_day_does_not_modify_night_setting(self):
		await self.runtime.apply_command(MqttCommand("day_enabled", "OFF"), datetime(2026, 6, 15, 12, 0, tzinfo=WARSAW))
		self.assertTrue(self.coordinator.settings.night_enabled)
		self.assertFalse(self.coordinator.settings.day_enabled)

	async def test_stale_soc_during_charge_requests_reset(self):
		now=datetime(2026, 6, 15, 17, 0, tzinfo=WARSAW)
		self.runtime.active_segment=Segment.DAY
		self.runtime.active_window=window_for(now, Segment.DAY, self.config)
		self.runtime.last_valid_soc_at=now-timedelta(seconds=181)
		self.ha.states[self.config.entities.battery_soc]="unavailable"
		await self.runtime.evaluate(now)
		self.assertEqual(self.executor.reset_reasons, ["stale_soc"])

	async def test_failed_reset_marks_runtime_as_fault(self):
		async def fail_reset(reason):
			raise RuntimeError("write failed")
		self.executor.full_reset=fail_reset
		self.runtime.active_segment=Segment.DAY
		self.runtime.active_window=window_for(datetime(2026, 6, 15, 17, 0, tzinfo=WARSAW), Segment.DAY, self.config)
		with self.assertRaises(RuntimeError):
			await self.runtime._reset("test_failure")
		self.assertEqual(self.runtime.state.value, "fault")

	async def test_completed_execution_key_blocks_duplicate_start(self):
		now=datetime(2026, 6, 15, 18, 0, tzinfo=WARSAW)
		window=window_for(now, Segment.DAY, self.config)
		self.coordinator.completed.add(window.execution_key)
		self.ha.states[self.config.entities.battery_soc]="40"
		await self.runtime.evaluate(now)
		self.assertEqual(self.executor.started, [])

	async def test_waiting_plan_publishes_seconds_and_no_plan_is_unavailable(self):
		night=datetime(2026, 6, 15, 23, 0, tzinfo=WARSAW)
		self.ha.states[self.config.entities.battery_soc]="30"
		await self.runtime.evaluate(night)
		starts,ends=self.mqtt.durations[-1]
		self.assertGreater(starts, 0)
		self.assertGreater(ends, starts)
		await self.runtime.evaluate(datetime(2026, 6, 15, 12, 0, tzinfo=WARSAW))
		self.assertEqual(self.mqtt.durations[-1], (None, None))

	async def test_day_charge_is_skipped_on_holiday(self):
		now=datetime(2026, 12, 24, 15, 0, tzinfo=WARSAW)
		self.ha.states[self.config.entities.battery_soc]="20"
		await self.runtime.evaluate(now)
		self.assertEqual(self.executor.started, [])

	async def test_timer_delay_reaches_hard_stop_without_waiting_full_interval(self):
		now=datetime(2026, 6, 15, 18, 54, tzinfo=WARSAW)
		self.runtime.active_segment=Segment.DAY
		self.runtime.active_window=window_for(now, Segment.DAY, self.config)
		self.assertEqual(self.runtime.next_delay(now), 60)


if __name__ == "__main__":
	unittest.main()
