import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from energy_ledger.runtime import history_start, manual_tariff_entry
from energy_ledger.tariff import G13Zone, TariffRates


class RuntimeTests(unittest.TestCase):
	def test_first_run_backfills_from_start_of_current_warsaw_month(self):
		now=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
		self.assertEqual(history_start({}, now, 45).isoformat(), "2026-08-31T22:00:00+00:00")

	def test_restart_resumes_shortly_before_oldest_entity_cursor(self):
		state={"state": {"last_event_at": {"import": "2026-09-20T10:00:00+00:00", "export": "2026-09-20T11:00:00+00:00"}}}
		now=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
		self.assertEqual(history_start(state, now, 45).isoformat(), "2026-09-20T09:55:00+00:00")

	def test_restart_history_is_capped_by_configured_limit(self):
		state={"state": {"last_event_at": {"import": "2026-01-01T00:00:00+00:00", "export": "2026-01-02T00:00:00+00:00"}}}
		now=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
		self.assertEqual(history_start(state, now, 45).isoformat(), "2026-08-08T12:00:00+00:00")

	def test_manual_tariff_does_not_depend_on_catalog_validity_dates(self):
		zero={zone: Decimal("0") for zone in G13Zone}
		entry=manual_tariff_entry(TariffRates(zero, zero, Decimal("0"), Decimal("12")), date(2030, 1, 1))
		self.assertEqual(entry.identifier, "manual")
		self.assertEqual(entry.valid_to, date.max)


if __name__ == "__main__":
	unittest.main()
