import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from energy_ledger.catalog import CatalogError, load_catalog, select_tariff
from energy_ledger.tariff import G13Zone


VALID={
	"schema_version": 1,
	"tariffs": [
		{
			"id": "old",
			"provider": "TAURON Dystrybucja S.A.",
			"tariff": "G13",
			"valid_from": "2026-01-01",
			"valid_to": "2026-01-31",
			"gross": True,
			"energy": {"morning_peak": 0, "afternoon_peak": 0, "other": 0},
			"distribution": {"morning_peak": 0.1, "afternoon_peak": 0.2, "other": 0.03},
			"common_variable": 0.04,
			"fixed_monthly": 10,
		},
		{
			"id": "current",
			"provider": "TAURON Dystrybucja S.A.",
			"tariff": "G13",
			"valid_from": "2026-02-01",
			"valid_to": "2026-12-31",
			"gross": True,
			"energy": {"morning_peak": 0, "afternoon_peak": 0, "other": 0},
			"distribution": {"morning_peak": 0.271, "afternoon_peak": 0.4795, "other": 0.0482},
			"common_variable": 0.053469,
			"fixed_monthly": 48.55,
		},
	],
}


class CatalogTests(unittest.TestCase):
	def test_bundled_tauron_catalog_contains_verified_2026_g13_rates(self):
		path=Path(__file__).resolve().parents[1] / "energy_ledger" / "data" / "tauron-g13.json"
		entry=select_tariff(load_catalog(path), date(2026, 9, 22))
		self.assertEqual(entry.identifier, "tauron-g13-2026-regulated")
		self.assertEqual(entry.rates.energy[G13Zone.AFTERNOON_PEAK], Decimal("0.9631"))
		self.assertEqual(entry.rates.distribution[G13Zone.OTHER], Decimal("0.0482"))

	def test_selects_entry_effective_on_requested_date(self):
		with tempfile.TemporaryDirectory() as directory:
			path=Path(directory) / "catalog.json"
			path.write_text(json.dumps(VALID), encoding="utf-8")
			catalog=load_catalog(path)
			self.assertEqual(select_tariff(catalog, date(2026, 9, 22)).identifier, "current")

	def test_rejects_catalog_with_missing_zone(self):
		broken=json.loads(json.dumps(VALID))
		del broken["tariffs"][1]["distribution"]["other"]
		with tempfile.TemporaryDirectory() as directory:
			path=Path(directory) / "catalog.json"
			path.write_text(json.dumps(broken), encoding="utf-8")
			with self.assertRaises(CatalogError):
				load_catalog(path)


if __name__ == "__main__":
	unittest.main()
