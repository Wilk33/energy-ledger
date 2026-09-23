import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
	def test_container_runtime_copy_matches_tested_source(self):
		source=ROOT / "energy_ledger"
		target=ROOT / "energy-ledger" / "rootfs" / "usr" / "src" / "app" / "energy_ledger"
		for path in source.rglob("*"):
			if not path.is_file() or "__pycache__" in path.parts:
				continue
			relative=path.relative_to(source)
			with self.subTest(path=str(relative)):
				self.assertEqual((target / relative).read_bytes(), path.read_bytes())

	def test_addon_version_matches_python_package(self):
		config=(ROOT / "energy-ledger" / "config.yaml").read_text(encoding="utf-8")
		package=(ROOT / "energy_ledger" / "__init__.py").read_text(encoding="utf-8")
		self.assertIn('version: "1.0.0"', config)
		self.assertIn('__version__="1.0.0"', package)

	def test_battery_controller_runtime_copy_matches_tested_source(self):
		source=ROOT / "battery_charge_controller"
		target=ROOT / "battery-charge-controller" / "rootfs" / "usr" / "src" / "app" / "battery_charge_controller"
		for path in source.rglob("*"):
			if not path.is_file() or "__pycache__" in path.parts:
				continue
			relative=path.relative_to(source)
			with self.subTest(path=str(relative)):
				self.assertEqual((target / relative).read_bytes(), path.read_bytes())

	def test_battery_addon_version_matches_python_package(self):
		config=(ROOT / "battery-charge-controller" / "config.yaml").read_text(encoding="utf-8")
		package=(ROOT / "battery_charge_controller" / "__init__.py").read_text(encoding="utf-8")
		self.assertIn('version: "1.0.0"', config)
		self.assertIn('__version__="1.0.0"', package)

	def test_battery_addon_has_no_ingress_and_needs_mqtt(self):
		config=(ROOT / "battery-charge-controller" / "config.yaml").read_text(encoding="utf-8")
		self.assertNotIn("ingress:", config)
		self.assertIn("mqtt:need", config)


if __name__ == "__main__":
	unittest.main()
