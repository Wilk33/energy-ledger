import unittest
from datetime import datetime
from decimal import Decimal as D

from energy_ledger.config import AppConfig, ConfigurationError
from energy_ledger.ledger import EnergyLedger, ClosedPeriod
from energy_ledger.mqtt import state_payload
from energy_ledger.tariff import WARSAW
from tests.test_config import BASE
from tests.test_ledger import tariff


class BillCorrectionTests(unittest.TestCase):
	def test_missing_empty_null_and_zero_are_zero(self):
		self.assertEqual(AppConfig.from_options(BASE).monthly_bill_correction_pln,D('0'))
		for value in ('',None,'  ',0):
			with self.subTest(value=value):
				self.assertEqual(AppConfig.from_options({**BASE,'monthly_bill_correction_pln':value}).monthly_bill_correction_pln,D('0'))

	def test_signed_decimal_comma_and_invalid_values(self):
		for value,expected in [('5,94','5.94'),('-2.50','-2.50')]:
			self.assertEqual(AppConfig.from_options({**BASE,'monthly_bill_correction_pln':value}).monthly_bill_correction_pln,D(expected))
		for value in ('NaN','Infinity','abc'):
			with self.assertRaises(ConfigurationError):
				AppConfig.from_options({**BASE,'monthly_bill_correction_pln':value})

	def test_final_gross_only_once_per_month_and_not_vat_or_energy(self):
		ledger=EnergyLedger(D('.8'),tariff(),now=datetime(2026,10,1,tzinfo=WARSAW),monthly_bill_correction_pln=D('5.94'))
		base=EnergyLedger(D('.8'),tariff(),now=datetime(2026,10,1,tzinfo=WARSAW))
		for _ in range(3):
			self.assertEqual(ledger.estimated_bill_gross,base.estimated_bill_gross+D('5.94'))
		self.assertEqual(ledger.estimated_vat,base.estimated_vat)
		self.assertEqual(ledger.state.balance_kwh,D('0'))
		ledger.advance_to(datetime(2026,11,1,tzinfo=WARSAW))
		self.assertEqual(ledger.estimated_bill_gross,base.estimated_bill_gross+D('5.94'))

	def test_closed_correction_is_frozen_and_survives_reload(self):
		ledger=EnergyLedger(D('.8'),tariff(),now=datetime(2026,10,1,tzinfo=WARSAW),monthly_bill_correction_pln=D('-2.50'))
		expected=ledger.estimated_bill_gross
		now=datetime(2026,11,1,tzinfo=WARSAW)
		ledger.advance_to(now)
		ledger=EnergyLedger.from_dict(ledger.to_dict(),tariff())
		ledger.monthly_bill_correction_pln=D('10')
		payload=state_payload(ledger,'test','ok',now)
		self.assertEqual(payload['previous_month_bill_pln'],float(expected))
		self.assertEqual(payload['previous_month_bill_details']['correction_gross_pln'],-2.5)

	def test_old_closed_period_defaults_to_zero_correction(self):
		old=ClosedPeriod('2026-10',D('0'),D('10'),D('20'),D('0'),D('0')).to_dict()
		old.pop('bill_correction_pln',None)
		self.assertEqual(ClosedPeriod.from_dict(old).bill_correction_pln,D('0'))
