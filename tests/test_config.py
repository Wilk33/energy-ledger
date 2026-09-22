import unittest
from decimal import Decimal

from energy_ledger.config import AppConfig, ConfigurationError
from energy_ledger.tariff import G13Zone, TariffRates


BASE={
	"grid_import_total_entity": "sensor.grid_import_total",
	"grid_export_total_entity": "sensor.grid_export_total",
	"discount_percent": 80,
	"balance_correction_kwh": 0,
	"manual_prices_enabled": False,
	"manual_energy_morning_peak": 0.5803,
	"manual_energy_afternoon_peak": 0.9631,
	"manual_energy_other": 0.5240,
	"manual_distribution_morning_peak": 0.271,
	"manual_distribution_afternoon_peak": 0.4795,
	"manual_distribution_other": 0.0482,
	"manual_common_variable": 0.0535,
	"manual_fixed_monthly": 48.55,
}


class ConfigurationTests(unittest.TestCase):
	def test_parses_discount_and_entities(self):
		config=AppConfig.from_options(BASE)
		self.assertEqual(config.discount, Decimal("0.8"))
		self.assertEqual(config.import_entity, "sensor.grid_import_total")

	def test_rejects_same_entity_for_import_and_export(self):
		options=dict(BASE)
		options["grid_export_total_entity"]=options["grid_import_total_entity"]
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_manual_mode_replaces_every_cost_component(self):
		options=dict(BASE)
		options["manual_prices_enabled"]=True
		config=AppConfig.from_options(options)
		zero={zone: Decimal("0") for zone in G13Zone}
		result=config.effective_rates(TariffRates(zero, zero, Decimal("0"), Decimal("0")))
		self.assertEqual(result.energy[G13Zone.MORNING_PEAK], Decimal("0.5803"))
		self.assertEqual(result.distribution[G13Zone.AFTERNOON_PEAK], Decimal("0.4795"))
		self.assertEqual(result.common_variable, Decimal("0.0535"))
		self.assertEqual(result.fixed_monthly, Decimal("48.55"))

	def test_automatic_catalog_can_include_contract_specific_fixed_fee(self):
		options=dict(BASE)
		options["additional_fixed_monthly"]=Decimal("29.58")
		config=AppConfig.from_options(options)
		zero={zone: Decimal("0") for zone in G13Zone}
		result=config.effective_rates(TariffRates(zero, zero, Decimal("0"), Decimal("18.97")))
		self.assertEqual(result.fixed_monthly, Decimal("48.55"))


if __name__ == "__main__":
	unittest.main()
