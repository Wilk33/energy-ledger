import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from energy_ledger.catalog import CatalogError, load_catalog, select_tariff
from energy_ledger.tariff import G13Zone


VALID={
	"schema_version": 2,
	"tariffs": [
		{
			"id": "old",
			"provider": "TAURON Dystrybucja S.A.",
			"tariff": "G13",
			"valid_from": "2026-01-01",
			"valid_to": "2026-01-31",
			"prices": "net",
			"vat_rate": 0.23,
			"energy": {"morning_peak": 0, "afternoon_peak": 0, "other": 0},
			"distribution": {"morning_peak": 0.1, "afternoon_peak": 0.2, "other": 0.03},
			"quality": 0.0332,
			"import_fees": {"oze": 0.0073, "cogeneration": 0.003},
			"fixed_monthly": 10,
		},
		{
			"id": "current",
			"provider": "TAURON Dystrybucja S.A.",
			"tariff": "G13",
			"valid_from": "2026-02-01",
			"valid_to": "2026-12-31",
			"prices": "net",
			"vat_rate": 0.23,
			"energy": {"morning_peak": 0.4718, "afternoon_peak": 0.783, "other": 0.426},
			"distribution": {"morning_peak": 0.2203, "afternoon_peak": 0.3898, "other": 0.0392},
			"quality": 0.0332,
			"import_fees": {"oze": 0.0073, "cogeneration": 0.003},
			"fixed_monthly": 15.42,
		},
	],
}


class CatalogTests(unittest.TestCase):
	def test_bundled_tauron_catalog_contains_verified_2026_g13_rates(self):
		path=Path(__file__).resolve().parents[1] / "energy_ledger" / "data" / "tauron-g13.json"
		entry=select_tariff(load_catalog(path), date(2026, 9, 22))
		self.assertEqual(entry.identifier, "tauron-g13-2026-invoice-verified")
		self.assertEqual(entry.rates.energy[G13Zone.AFTERNOON_PEAK], Decimal("0.78300"))
		self.assertEqual(entry.rates.distribution[G13Zone.OTHER], Decimal("0.03920"))
		self.assertEqual(entry.rates.quality, Decimal("0.03320"))
		self.assertEqual(entry.rates.import_fees["oze"], Decimal("0.00730"))
		self.assertEqual(entry.rates.vat_rate, Decimal("0.23"))

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
