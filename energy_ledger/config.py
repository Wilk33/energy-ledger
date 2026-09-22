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
	mqtt_base_topic: str
	mqtt_discovery_prefix: str
	device_name: str
	log_level: str

	@classmethod
	def from_options(cls, options: dict[str, Any]) -> "AppConfig":
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
		manual_rates=TariffRates(
			energy={
				G13Zone.MORNING_PEAK: _decimal(options, "manual_energy_morning_peak"),
				G13Zone.AFTERNOON_PEAK: _decimal(options, "manual_energy_afternoon_peak"),
				G13Zone.OTHER: _decimal(options, "manual_energy_other"),
			},
			distribution={
				G13Zone.MORNING_PEAK: _decimal(options, "manual_distribution_morning_peak"),
				G13Zone.AFTERNOON_PEAK: _decimal(options, "manual_distribution_afternoon_peak"),
				G13Zone.OTHER: _decimal(options, "manual_distribution_other"),
			},
			common_variable=_decimal(options, "manual_common_variable"),
			fixed_monthly=_decimal(options, "manual_fixed_monthly"),
		)
		return cls(
			import_entity=import_entity,
			export_entity=export_entity,
			discount=Decimal(percent)/Decimal("100"),
			correction=_decimal(options, "balance_correction_kwh"),
			history_days=history_days,
			tariff_update_enabled=bool(options.get("tariff_update_enabled", True)),
			tariff_catalog_url=str(options.get("tariff_catalog_url", "")).strip(),
			manual_prices_enabled=bool(options.get("manual_prices_enabled", False)),
			manual_rates=manual_rates,
			additional_fixed_monthly=_decimal(options, "additional_fixed_monthly"),
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
			common_variable=catalog_rates.common_variable,
			fixed_monthly=catalog_rates.fixed_monthly+self.additional_fixed_monthly,
		)
