import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from energy_ledger.ledger import EnergyLedger, MeterKind
from energy_ledger.tariff import G13Zone, TariffRates


WARSAW=ZoneInfo("Europe/Warsaw")


def tariff():
	return TariffRates(
		energy={G13Zone.MORNING_PEAK: Decimal("0.50"), G13Zone.AFTERNOON_PEAK: Decimal("0.70"), G13Zone.OTHER: Decimal("0.30")},
		distribution={G13Zone.MORNING_PEAK: Decimal("0.20"), G13Zone.AFTERNOON_PEAK: Decimal("0.40"), G13Zone.OTHER: Decimal("0.05")},
		common_variable=Decimal("0.04"),
		fixed_monthly=Decimal("35.00"),
	)


class EnergyLedgerTests(unittest.TestCase):
	def test_total_meter_deltas_update_signed_balance_with_discount(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		ledger.process_total(MeterKind.IMPORT, "100", datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.EXPORT, "200", datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.IMPORT, "110", datetime(2026, 9, 1, 9, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.EXPORT, "205", datetime(2026, 9, 1, 10, 0, tzinfo=WARSAW))
		self.assertEqual(ledger.state.balance_kwh, Decimal("-6.0"))
		self.assertEqual(ledger.state.import_month_kwh, Decimal("10"))
		self.assertEqual(ledger.state.export_month_kwh, Decimal("5"))

	def test_invalid_states_are_ignored_and_counter_reset_only_changes_baseline(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		t0=datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW)
		ledger.process_total(MeterKind.IMPORT, "100", t0)
		self.assertFalse(ledger.process_total(MeterKind.IMPORT, "unknown", t0.replace(minute=1)))
		self.assertFalse(ledger.process_total(MeterKind.IMPORT, "NaN", t0.replace(minute=2)))
		self.assertTrue(ledger.process_total(MeterKind.IMPORT, "5", t0.replace(minute=3)))
		ledger.process_total(MeterKind.IMPORT, "8", t0.replace(minute=4))
		self.assertEqual(ledger.state.import_month_kwh, Decimal("3"))
		self.assertEqual(ledger.state.balance_kwh, Decimal("-3"))

	def test_older_or_duplicate_history_event_is_not_counted_again(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		t0=datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW)
		ledger.process_total(MeterKind.IMPORT, "100", t0)
		ledger.process_total(MeterKind.IMPORT, "110", t0.replace(minute=10))
		self.assertFalse(ledger.process_total(MeterKind.IMPORT, "105", t0.replace(minute=5)))
		self.assertEqual(ledger.state.import_month_kwh, Decimal("10"))

	def test_later_export_reduces_uncovered_energy_and_live_cost(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		ledger.process_total(MeterKind.IMPORT, "0", datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.EXPORT, "0", datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.IMPORT, "10", datetime(2026, 9, 1, 9, 0, tzinfo=WARSAW))
		self.assertEqual(ledger.variable_cost, Decimal("7.40"))
		ledger.process_total(MeterKind.EXPORT, "5", datetime(2026, 9, 1, 10, 0, tzinfo=WARSAW))
		self.assertEqual(ledger.state.uncovered_kwh, Decimal("6.0"))
		self.assertEqual(ledger.variable_cost, Decimal("4.440"))

	def test_positive_balance_carries_to_next_month(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		ledger.apply_correction(Decimal("12"), G13Zone.OTHER)
		ledger.advance_to(datetime(2026, 10, 1, 0, 0, tzinfo=WARSAW))
		self.assertEqual(ledger.state.balance_kwh, Decimal("12"))
		self.assertEqual(ledger.state.closed_periods[0].shortage_kwh, Decimal("0"))

	def test_negative_correction_consumes_positive_balance_before_creating_shortage(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		ledger.apply_correction(Decimal("5"), G13Zone.OTHER)
		ledger.apply_correction(Decimal("-8"), G13Zone.OTHER)
		self.assertEqual(ledger.state.balance_kwh, Decimal("-3"))
		self.assertEqual(ledger.state.uncovered_kwh, Decimal("3"))

	def test_negative_balance_is_closed_and_reset_for_next_month(self):
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=tariff())
		ledger.process_total(MeterKind.IMPORT, "0", datetime(2026, 9, 1, 8, 0, tzinfo=WARSAW))
		ledger.process_total(MeterKind.IMPORT, "10", datetime(2026, 9, 2, 8, 0, tzinfo=WARSAW))
		ledger.advance_to(datetime(2026, 10, 1, 0, 0, tzinfo=WARSAW))
		self.assertEqual(ledger.state.balance_kwh, Decimal("0"))
		self.assertEqual(ledger.state.closed_periods[0].shortage_kwh, Decimal("10"))
		self.assertEqual(ledger.state.closed_periods[0].variable_cost_pln, Decimal("7.40"))
		self.assertEqual(ledger.state.import_month_kwh, Decimal("0"))


if __name__ == "__main__":
	unittest.main()
