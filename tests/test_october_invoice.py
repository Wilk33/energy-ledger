import unittest
from dataclasses import replace
from datetime import datetime, date
from decimal import Decimal as D
from pathlib import Path

from energy_ledger.ledger import EnergyLedger, DeficitLot
from energy_ledger.catalog import load_catalog, select_tariff
from energy_ledger.tariff import G13Zone as Z, WARSAW
from tests.test_ledger import september_invoice_tariff
from energy_ledger.runtime import restore_export_zones
from energy_ledger.ha import MeterEvent
from energy_ledger.ledger import MeterKind


class OctoberInvoiceTests(unittest.TestCase):
	def ledger(self):
		return EnergyLedger(D('0.8'),september_invoice_tariff(),now=datetime(2026,10,1,tzinfo=WARSAW))

	def test_export_covers_own_zone_even_when_another_deficit_is_older(self):
		ledger=self.ledger()
		ledger._apply_import(D('50'),Z.OTHER)
		ledger._apply_import(D('50'),Z.MORNING_PEAK)
		ledger._apply_export(D('50'),Z.MORNING_PEAK)
		self.assertEqual(ledger._deficit_by_zone[Z.MORNING_PEAK],D('10'))
		self.assertEqual(ledger._deficit_by_zone[Z.OTHER],D('50'))

	def test_surplus_covers_highest_distribution_rate_first(self):
		ledger=self.ledger()
		ledger._apply_import(D('50'),Z.OTHER)
		ledger._apply_import(D('10'),Z.AFTERNOON_PEAK)
		ledger._apply_export(D('25'),Z.MORNING_PEAK)
		self.assertEqual(ledger._deficit_by_zone[Z.AFTERNOON_PEAK],D('0'))
		self.assertEqual(ledger._deficit_by_zone[Z.OTHER],D('40'))

	def test_export_before_import_has_same_monthly_result(self):
		first=self.ledger()
		second=self.ledger()
		first._apply_export(D('50'),Z.MORNING_PEAK)
		for ledger in (first,second):
			ledger._apply_import(D('50'),Z.OTHER)
			ledger._apply_import(D('50'),Z.MORNING_PEAK)
		second._apply_export(D('50'),Z.MORNING_PEAK)
		self.assertEqual(first._deficit_by_zone,second._deficit_by_zone)
		self.assertEqual(first.variable_cost,second.variable_cost)

	def test_october_invoice_line_amounts(self):
		ledger=self.ledger()
		ledger.rates=replace(ledger.rates,fixed_monthly=D('34.91'))
		ledger.state.imports_by_zone=dict(zip(Z,map(D,('50','3','217'))))
		ledger.state.deficit_lots=[DeficitLot(z,D(k)) for z,k in zip(Z,('15','1','114'))]
		self.assertEqual(ledger.variable_cost_gross,D('88.16'))
		self.assertEqual(ledger.fixed_cost_gross,D('42.94'))
		self.assertEqual(ledger.estimated_bill_gross,D('131.10'))

	def test_catalog_preserves_september_and_removes_october_subscription(self):
		entries=load_catalog(Path(__file__).resolve().parents[1]/'energy_ledger/data/tauron-g13.json')
		self.assertEqual(select_tariff(entries,date(2026,9,30)).rates.fixed_monthly,D('15.42'))
		self.assertEqual(select_tariff(entries,date(2026,10,1)).rates.fixed_monthly,D('10.86'))

	def test_zone_exports_survive_restart(self):
		ledger=self.ledger()
		ledger._apply_import(D('50'),Z.OTHER)
		ledger._apply_export(D('20'),Z.MORNING_PEAK)
		restored=EnergyLedger.from_dict(ledger.to_dict(),ledger.rates)
		restored._apply_import(D('20'),Z.MORNING_PEAK)
		self.assertEqual(restored._deficit_by_zone[Z.MORNING_PEAK],D('4'))
		self.assertEqual(restored._deficit_by_zone[Z.OTHER],D('50'))

	def test_legacy_state_is_preserved_until_export_history_is_verified(self):
		ledger=self.ledger()
		start=datetime(2026,10,1,tzinfo=WARSAW)
		end=start.replace(hour=8)
		ledger.process_total(MeterKind.EXPORT,'100',start)
		ledger._apply_import(D('50'),Z.OTHER)
		ledger._apply_import(D('20'),Z.MORNING_PEAK)
		ledger.process_total(MeterKind.EXPORT,'120',end)
		data=ledger.to_dict()
		del data['state']['exports_by_zone']
		legacy=EnergyLedger.from_dict(data,ledger.rates)
		self.assertIsNone(legacy.state.exports_by_zone)
		self.assertFalse(restore_export_zones(legacy,[MeterEvent(MeterKind.EXPORT,'120',end)],start))
		self.assertIsNone(legacy.state.exports_by_zone)
		self.assertTrue(restore_export_zones(legacy,[MeterEvent(MeterKind.EXPORT,'100',start),MeterEvent(MeterKind.EXPORT,'120',end)],start))
		self.assertEqual(legacy._deficit_by_zone,ledger._deficit_by_zone)

	def test_new_period_enables_zone_accounting_after_legacy_month(self):
		ledger=self.ledger()
		ledger.state.exports_by_zone=None
		ledger.advance_to(datetime(2026,11,1,tzinfo=WARSAW))
		self.assertEqual(ledger.state.exports_by_zone,{zone:D('0') for zone in Z})

	def test_meter_event_classifies_export_zone(self):
		ledger=self.ledger()
		ledger.process_total(MeterKind.EXPORT,'100',datetime(2026,10,1,7,tzinfo=WARSAW))
		ledger.process_total(MeterKind.EXPORT,'125',datetime(2026,10,1,8,tzinfo=WARSAW))
		self.assertEqual(ledger.state.exports_by_zone[Z.MORNING_PEAK],D('25'))

	def test_october_energy_is_not_silently_rounded_to_invoice_units(self):
		ledger=self.ledger()
		for zone,imp,exp in zip(Z,('50','3','217'),('44','3','129')):
			ledger._apply_import(D(imp),zone)
			ledger._apply_export(D(exp),zone)
		self.assertEqual(ledger.state.uncovered_kwh,D('129.2'))
		self.assertEqual(ledger._deficit_by_zone,dict(zip(Z,map(D,('14.8','0.6','113.8')))))
