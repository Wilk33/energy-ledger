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


if __name__ == "__main__":
	unittest.main()
