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
	"manual_common_variable": 0.053505,
	"manual_oze_variable": 0.008979,
	"manual_cogeneration_variable": 0.003690,
	"manual_fixed_monthly": 48.5481,
	"manual_vat_percent": 23,
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
		result=config.effective_rates(TariffRates(zero, zero, Decimal("0"), {"oze": Decimal("0"), "cogeneration": Decimal("0")}, Decimal("0"), Decimal("0.23")))
		self.assertEqual(result.energy[G13Zone.MORNING_PEAK], Decimal("0.5803")/Decimal("1.23"))
		self.assertEqual(result.distribution[G13Zone.AFTERNOON_PEAK], Decimal("0.4795")/Decimal("1.23"))
		self.assertEqual(result.quality, Decimal("0.0332"))
		self.assertEqual(result.import_fees["oze"], Decimal("0.0073"))
		self.assertEqual(result.import_fees["cogeneration"], Decimal("0.003"))
		self.assertEqual(result.fixed_monthly, Decimal("39.47"))
		self.assertEqual(result.vat_rate, Decimal("0.23"))

	def test_automatic_catalog_can_include_contract_specific_fixed_fee(self):
		options=dict(BASE)
		options["additional_fixed_monthly"]=Decimal("29.5815")
		config=AppConfig.from_options(options)
		zero={zone: Decimal("0") for zone in G13Zone}
		result=config.effective_rates(TariffRates(zero, zero, Decimal("0"), {"oze": Decimal("0"), "cogeneration": Decimal("0")}, Decimal("15.42"), Decimal("0.23")))
		self.assertEqual(result.fixed_monthly, Decimal("39.47"))

	def test_legacy_combined_manual_variable_fee_remains_supported(self):
		options=dict(BASE)
		options["manual_common_variable"]=Decimal("0.0535")
		config=AppConfig.from_options(options)
		combined=config.manual_rates.quality+config.manual_rates.full_import_price_net
		self.assertEqual(combined, Decimal("0.0535")/Decimal("1.23"))
		self.assertEqual(config.manual_rates.import_fees["oze"], Decimal("0.0073"))

	def test_legacy_configuration_without_split_fields_keeps_old_behavior(self):
		options=dict(BASE)
		for key in ("manual_oze_variable", "manual_cogeneration_variable"):
			options.pop(key)
		options["manual_common_variable"]=Decimal("0.0535")
		config=AppConfig.from_options(options)
		self.assertEqual(config.manual_rates.quality, Decimal("0.0535")/Decimal("1.23"))
		self.assertEqual(config.manual_rates.full_import_price_net, Decimal("0"))

	def test_disabled_manual_prices_do_not_block_upgrade_with_zero_legacy_fee(self):
		options=dict(BASE)
		options["manual_prices_enabled"]=False
		options["manual_common_variable"]=0
		config=AppConfig.from_options(options)
		self.assertFalse(config.manual_prices_enabled)

	def test_enabled_manual_prices_reject_components_above_combined_fee(self):
		options=dict(BASE)
		options["manual_prices_enabled"]=True
		options["manual_common_variable"]=0
		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)


if __name__ == "__main__":
	unittest.main()
