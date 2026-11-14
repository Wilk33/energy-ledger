import unittest
from datetime import datetime, timezone

from battery_charge_controller.calendar import Segment, window_for
from battery_charge_controller.runtime import ControllerState
from tests import test_charge_runtime as fixtures


class WorkdayRuntimeTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		await fixtures.ChargeRuntimeTests.asyncSetUp(self)
		self.ha.states[self.config.entities.battery_soc]='20'

	async def asyncTearDown(self):
		self.temporary.cleanup()

	async def test_both_segments_are_blocked_on_weekends_and_holidays(self):
		for month,day in ((6,13),(6,14),(11,11),(1,6),(12,24),(4,6),(6,4)):
			for hour,minute in ((6,50),(23,0),(15,50),(18,50)):
				with self.subTest(month=month,day=day,hour=hour):
					await self.runtime.evaluate(datetime(2026,month,day,hour,minute,tzinfo=fixtures.WARSAW))
					self.assertEqual(self.executor.started,[])
					self.assertEqual(self.runtime.state,ControllerState.IDLE)
					self.assertEqual(self.mqtt.durations[-1],(None,None))

	async def test_friday_session_stops_at_saturday_midnight_even_with_invalid_soc(self):
		friday=datetime(2026,11,13,23,59,tzinfo=fixtures.WARSAW)
		self.runtime.active_segment=Segment.NIGHT
		self.runtime.active_window=window_for(friday,Segment.NIGHT,self.config)
		self.runtime.last_valid_soc_at=friday
		self.ha.states[self.config.entities.battery_soc]='unknown'
		await self.runtime.evaluate(datetime(2026,11,14,0,0,tzinfo=fixtures.WARSAW))
		self.assertEqual(self.executor.reset_reasons,['non_workday'])
		self.assertIsNone(self.runtime.active_segment)

	async def test_timer_wakes_at_midnight_instead_of_full_poll_interval(self):
		friday=datetime(2026,11,13,23,59,50,tzinfo=fixtures.WARSAW)
		self.runtime.active_segment=Segment.NIGHT
		self.runtime.active_window=window_for(friday,Segment.NIGHT,self.config)
		self.assertEqual(self.runtime.next_delay(friday),10)

	async def test_friday_evening_remains_eligible_until_midnight(self):
		friday=datetime(2026,11,13,23,0,tzinfo=fixtures.WARSAW)
		await self.runtime.evaluate(friday)
		self.assertEqual(self.runtime.state,ControllerState.WAITING_NIGHT)
		self.ha.states[self.config.entities.grid_charge]='on'
		self.ha.states[self.config.entities.capacity[0]]='80'
		self.ha.states[self.config.entities.charge[0]]=self.config.active_charge_option
		await self.runtime.initialize(friday)
		self.assertEqual(self.runtime.active_segment,Segment.NIGHT)
		self.assertEqual(self.executor.reset_reasons,[])

	async def test_active_charge_stops_when_workday_becomes_holiday(self):
		now=datetime(2026,11,10,23,59,tzinfo=fixtures.WARSAW)
		self.runtime.active_segment=Segment.NIGHT
		self.runtime.active_window=window_for(now,Segment.NIGHT,self.config)
		await self.runtime.evaluate(datetime(2026,11,11,0,0,tzinfo=fixtures.WARSAW))
		self.assertEqual(self.executor.reset_reasons,['non_workday'])

	async def test_startup_does_not_resume_night_charge_on_holiday(self):
		self.ha.states[self.config.entities.grid_charge]='on'
		self.ha.states[self.config.entities.capacity[0]]='80'
		self.ha.states[self.config.entities.charge[0]]=self.config.active_charge_option
		await self.runtime.initialize(datetime(2026,11,11,6,0,tzinfo=fixtures.WARSAW))
		self.assertEqual(self.executor.reset_reasons,['startup_reconciliation'])
		self.assertIsNone(self.runtime.active_segment)

	async def test_monday_morning_can_charge_after_blocked_sunday(self):
		await self.runtime.evaluate(datetime(2026,11,15,23,0,tzinfo=fixtures.WARSAW))
		self.assertEqual(self.executor.started,[])
		await self.runtime.evaluate(datetime(2026,11,16,6,50,tzinfo=fixtures.WARSAW))
		self.assertEqual(self.executor.started,[(Segment.NIGHT,80)])

	async def test_utc_timestamp_is_classified_by_local_date(self):
		await self.runtime.evaluate(datetime(2026,11,13,23,0,tzinfo=timezone.utc))
		self.assertEqual(self.runtime.state,ControllerState.IDLE)
		self.assertEqual(self.mqtt.durations[-1],(None,None))
