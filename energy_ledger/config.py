from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .tariff import G13Zone, TariffRates


class ConfigurationError(ValueError):
	pass


def _decimal(options: dict[str, Any], key: str, default: str="0") -> Decimal:
	try:
		value=Decimal(str(options.get(key, default)))
	except (InvalidOperation, ValueError) as error:
		raise ConfigurationError(f"Option {key} must be a number") from error
	if not value.is_finite():
		raise ConfigurationError(f"Option {key} must be finite")
	return value


def _entity(options: dict[str, Any], key: str) -> str:
	value=str(options.get(key, "")).strip()
	if not value.startswith("sensor.") or len(value) <= len("sensor."):
		raise ConfigurationError(f"Option {key} must contain a sensor entity id")
	return value


@dataclass(frozen=True)
class AppConfig:
	import_entity: str
	export_entity: str
	discount: Decimal
	correction: Decimal
	history_days: int
	tariff_update_enabled: bool
	tariff_catalog_url: str
	manual_prices_enabled: bool
	manual_rates: TariffRates
	additional_fixed_monthly: Decimal
	monthly_bill_correction_pln: Decimal
	mqtt_base_topic: str
	mqtt_discovery_prefix: str
	device_name: str
	log_level: str

	@classmethod
	def from_options(cls, options: dict[str, Any]) -> "AppConfig":
		raw_correction=options.get("monthly_bill_correction_pln")
		bill_correction="0" if raw_correction is None or not str(raw_correction).strip() else str(raw_correction).strip().replace(",", ".")
		import_entity=_entity(options, "grid_import_total_entity")
		export_entity=_entity(options, "grid_export_total_entity")
		if import_entity == export_entity:
			raise ConfigurationError("Import and export entities must be different")
		percent=int(options.get("discount_percent", 80))
		if percent not in (70, 80):
			raise ConfigurationError("discount_percent must be 70 or 80")
		history_days=int(options.get("history_days", 370))
		if not 1 <= history_days <= 730:
			raise ConfigurationError("history_days must be between 1 and 730")
		manual_prices_enabled=bool(options.get("manual_prices_enabled", False))
		vat_percent=_decimal(options, "manual_vat_percent", "23")
		if vat_percent < 0 or vat_percent > 100:
			raise ConfigurationError("manual_vat_percent must be between 0 and 100")
		vat_rate=vat_percent/Decimal("100")
		gross_factor=Decimal("1")+vat_rate
		def gross_to_net(value: Decimal) -> Decimal:
			return value/gross_factor
		def net(key: str, default: str="0") -> Decimal:
			return gross_to_net(_decimal(options, key, default))
		split_import_fees="manual_oze_variable" in options or "manual_cogeneration_variable" in options
		oze_gross=_decimal(options, "manual_oze_variable") if split_import_fees else Decimal("0")
		cogeneration_gross=_decimal(options, "manual_cogeneration_variable") if split_import_fees else Decimal("0")
		quality_gross=_decimal(options, "manual_common_variable")-oze_gross-cogeneration_gross
		if quality_gross < 0:
			if manual_prices_enabled:
				raise ConfigurationError("manual_common_variable must include OZE and cogeneration fees")
			quality_gross=_decimal(options, "manual_common_variable")
			oze_gross=Decimal("0")
			cogeneration_gross=Decimal("0")
		manual_rates=TariffRates(
			energy={
				G13Zone.MORNING_PEAK: net("manual_energy_morning_peak"),
				G13Zone.AFTERNOON_PEAK: net("manual_energy_afternoon_peak"),
				G13Zone.OTHER: net("manual_energy_other"),
			},
			distribution={
				G13Zone.MORNING_PEAK: net("manual_distribution_morning_peak"),
				G13Zone.AFTERNOON_PEAK: net("manual_distribution_afternoon_peak"),
				G13Zone.OTHER: net("manual_distribution_other"),
			},
			quality=gross_to_net(quality_gross),
			import_fees={
				"oze": gross_to_net(oze_gross),
				"cogeneration": gross_to_net(cogeneration_gross),
			},
			fixed_monthly=net("manual_fixed_monthly"),
			vat_rate=vat_rate,
		)
		return cls(
			import_entity=import_entity,
			export_entity=export_entity,
			discount=Decimal(percent)/Decimal("100"),
			correction=_decimal(options, "balance_correction_kwh"),
			history_days=history_days,
			tariff_update_enabled=bool(options.get("tariff_update_enabled", True)),
			tariff_catalog_url=str(options.get("tariff_catalog_url", "")).strip(),
			manual_prices_enabled=manual_prices_enabled,
			manual_rates=manual_rates,
			additional_fixed_monthly=_decimal(options, "additional_fixed_monthly"),
			monthly_bill_correction_pln=_decimal({"monthly_bill_correction_pln":bill_correction}, "monthly_bill_correction_pln"),
			mqtt_base_topic=str(options.get("mqtt_base_topic", "energy_ledger")).strip(" /"),
			mqtt_discovery_prefix=str(options.get("mqtt_discovery_prefix", "homeassistant")).strip(" /"),
			device_name=str(options.get("device_name", "Energy Ledger")).strip() or "Energy Ledger",
			log_level=str(options.get("log_level", "INFO")).upper(),
		)

	def effective_rates(self, catalog_rates: TariffRates) -> TariffRates:
		if self.manual_prices_enabled:
			return self.manual_rates
		return TariffRates(
			energy=catalog_rates.energy,
			distribution=catalog_rates.distribution,
			quality=catalog_rates.quality,
			import_fees=catalog_rates.import_fees,
			fixed_monthly=catalog_rates.fixed_monthly+self.additional_fixed_monthly/(Decimal("1")+catalog_rates.vat_rate),
			vat_rate=catalog_rates.vat_rate,
		)
