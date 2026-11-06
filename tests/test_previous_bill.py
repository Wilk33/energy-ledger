import unittest
from datetime import datetime, timezone
from decimal import Decimal as D

from energy_ledger.ledger import EnergyLedger, ClosedPeriod
from energy_ledger.mqtt import state_payload, discovery_messages, SENSORS
from energy_ledger.tariff import WARSAW
from tests.test_ledger import tariff


class PreviousBillTests(unittest.TestCase):
	def setUp(self):
		self.now=datetime(2026,11,6,tzinfo=WARSAW)
		self.ledger=EnergyLedger(D('.8'),tariff(),now=self.now)

	def payload(self):
		return state_payload(self.ledger,'test','ok',self.now)

	def test_missing_previous_month_is_unknown_not_zero_or_older_month(self):
		self.ledger.state.closed_periods=[ClosedPeriod('2026-09',D('0'),D('10'),D('35'),D('20'),D('0'))]
		self.assertIsNone(self.payload()['previous_month_bill_pln'])

	def test_saved_gross_bill_survives_restart_and_rate_changes(self):
		self.ledger.state.closed_periods=[ClosedPeriod('2026-10',D('130'),D('88.16'),D('42.94'),D('270'),D('176'))]
		self.ledger=EnergyLedger.from_dict(self.ledger.to_dict(),tariff())
		self.assertEqual(self.payload()['previous_month_bill_pln'],131.10)
		self.assertEqual(self.payload()['previous_month_bill_details']['period'],'2026-10')

	def test_january_reads_december_and_includes_fixed_fees_with_surplus(self):
		self.now=datetime(2027,1,1,tzinfo=WARSAW)
		ledger=EnergyLedger(D('.8'),tariff(),now=datetime(2026,12,1,tzinfo=WARSAW))
		ledger.apply_correction(D('100'))
		ledger.advance_to(self.now)
		self.ledger=ledger
		self.assertEqual(self.payload()['previous_month_bill_pln'],35)

	def test_previous_month_uses_polish_calendar_at_utc_boundary(self):
		self.now=datetime(2026,10,31,23,30,tzinfo=timezone.utc)
		self.ledger.state.closed_periods=[ClosedPeriod('2026-10',D('130'),D('88.16'),D('42.94'),D('270'),D('176'))]
		self.assertEqual(self.payload()['previous_month_bill_details']['period'],'2026-10')
		self.assertEqual(self.payload()['previous_month_bill_pln'],131.10)

	def test_adds_one_sensor_with_no_data_availability_and_period_attribute(self):
		self.assertEqual(len(SENSORS),15)
		message=next(m for m in discovery_messages('homeassistant','energy_ledger','Dom') if m.payload['unique_id'] == 'energy_ledger_previous_month_bill_pln')
		self.assertEqual(message.payload['unit_of_measurement'],'PLN')
		self.assertEqual(message.payload['availability_mode'],'all')
		self.assertIn('previous_month_bill_details',message.payload['json_attributes_template'])
