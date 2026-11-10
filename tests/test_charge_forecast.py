import unittest
from dataclasses import replace
from datetime import datetime

from battery_charge_controller.config import AppConfig, ConfigurationError
from battery_charge_controller.mqtt import discovery_messages, MqttCommand
from battery_charge_controller.settings import UserSettings, SettingsError
from battery_charge_controller.calendar import Segment
from tests.test_charge_core import base_options
from tests import test_charge_runtime as runtime_tests


class ForecastConfigTests(unittest.TestCase):
	def test_disabled_by_default_and_enabled_requires_sensor(self):
		self.assertFalse(AppConfig.from_options(base_options()).forecast_condition_enabled)
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options({**base_options(),'forecast_condition_enabled':True})

	def test_slider_only_when_enabled_and_has_energy_range(self):
		messages=discovery_messages('homeassistant','test','Test',forecast_condition_enabled=True)
		slider=next(m for m in messages if m.object_id == 'night_forecast_threshold')
		self.assertEqual((slider.payload['min'],slider.payload['max'],slider.payload['unit_of_measurement']),(1,100,'kWh'))
		self.assertEqual(slider.payload['mode'],'slider')
		self.assertFalse(any(m.object_id == slider.object_id for m in discovery_messages('homeassistant','test','Test')))


class ForecastRuntimeTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		await runtime_tests.ChargeRuntimeTests.asyncSetUp(self)
		self.runtime.config=AppConfig.from_options({**base_options(),'forecast_condition_enabled':True,'forecast_entity':'sensor.forecast'})
		self.coordinator.settings=replace(self.coordinator.settings,night_forecast_threshold=20)
		self.ha.states[self.config.entities.battery_soc]='25'
		self.ha.states['sensor.forecast']='0'
		self.now=datetime(2026,6,15,6,50,tzinfo=runtime_tests.WARSAW)

	async def asyncTearDown(self):
		self.temporary.cleanup()

	async def test_forecast_at_or_above_threshold_blocks_and_lower_allows(self):
		for value in ('20','45'):
			self.ha.states['sensor.forecast']=value
			await self.runtime.evaluate(self.now)
			self.assertEqual(self.executor.started,[])
		self.ha.states['sensor.forecast']='19.9'
		await self.runtime.evaluate(self.now)
		self.assertEqual(self.executor.started,[(Segment.NIGHT,80)])

	async def test_invalid_or_missing_forecast_falls_back_to_soc(self):
		for value in ('unknown','unavailable','NaN','Infinity','-1','', 'abc'):
			self.runtime.active_segment=None
			self.runtime.active_window=None
			self.executor.started.clear()
			self.ha.states['sensor.forecast']=value
			await self.runtime.evaluate(self.now)
			self.assertEqual(self.executor.started,[(Segment.NIGHT,80)])
		self.runtime.active_segment=None
		self.runtime.active_window=None
		self.executor.started.clear()
		self.ha.missing.add('sensor.forecast')
		await self.runtime.evaluate(self.now)
		self.assertEqual(self.executor.started,[(Segment.NIGHT,80)])

	async def test_forecast_does_not_stop_running_charge(self):
		self.ha.states['sensor.forecast']='0'
		await self.runtime.evaluate(self.now)
		self.ha.states['sensor.forecast']='100'
		await self.runtime.evaluate(self.now)
		self.assertEqual(self.executor.reset_reasons,[])

	async def test_threshold_is_persisted_and_range_checked(self):
		await self.runtime.apply_command(MqttCommand('night_forecast_threshold','1'),self.now)
		self.assertEqual(UserSettings.from_dict(self.store.load()['settings']).night_forecast_threshold,1)
		for value in (0,101,float('nan')):
			with self.assertRaises(SettingsError):
				self.coordinator.apply_number('night_forecast_threshold',value)

	async def test_missing_forecast_does_not_abort_startup(self):
		self.ha.missing.add('sensor.forecast')
		await self.runtime.initialize(self.now)
		self.assertIn('sensor.forecast',self.runtime.watched_entities)

	async def test_high_forecast_does_not_block_day_and_low_forecast_does_not_override_soc(self):
		self.ha.states['sensor.forecast']='100'
		await self.runtime.evaluate(datetime(2026,6,15,18,50,tzinfo=runtime_tests.WARSAW))
		self.assertEqual(self.executor.started,[(Segment.DAY,80)])
		self.runtime.active_segment=None
		self.runtime.active_window=None
		self.executor.started.clear()
		self.ha.states['sensor.forecast']='0'
		self.ha.states[self.config.entities.battery_soc]='50'
		await self.runtime.evaluate(self.now)
		self.assertEqual(self.executor.started,[])

	async def test_disabled_condition_does_not_read_or_use_forecast(self):
		self.runtime.config=replace(self.runtime.config,forecast_condition_enabled=False)
		self.ha.states['sensor.forecast']='100'
		await self.runtime.evaluate(self.now)
		self.assertEqual(self.executor.started,[(Segment.NIGHT,80)])
