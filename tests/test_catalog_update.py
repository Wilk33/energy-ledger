import json
import tempfile
import unittest
from pathlib import Path

from energy_ledger.catalog_update import install_catalog_bytes


VALID={
	"schema_version": 1,
	"tariffs": [{
		"id": "catalog-test",
		"provider": "TAURON Dystrybucja S.A.",
		"tariff": "G13",
		"valid_from": "2026-01-01",
		"valid_to": "2026-12-31",
		"gross": True,
		"energy": {"morning_peak": 1, "afternoon_peak": 1, "other": 1},
		"distribution": {"morning_peak": 1, "afternoon_peak": 1, "other": 1},
		"common_variable": 1,
		"fixed_monthly": 1,
	}],
}


class CatalogUpdateTests(unittest.TestCase):
	def test_valid_download_replaces_catalog_atomically(self):
		with tempfile.TemporaryDirectory() as directory:
			target=Path(directory) / "catalog.json"
			target.write_text("old", encoding="utf-8")
			install_catalog_bytes(json.dumps(VALID).encode(), target)
			self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["tariffs"][0]["id"], "catalog-test")

	def test_invalid_download_preserves_previous_catalog(self):
		with tempfile.TemporaryDirectory() as directory:
			target=Path(directory) / "catalog.json"
			target.write_text(json.dumps(VALID), encoding="utf-8")
			with self.assertRaises(ValueError):
				install_catalog_bytes(b"{}", target)
			self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["tariffs"][0]["id"], "catalog-test")


if __name__ == "__main__":
	unittest.main()
