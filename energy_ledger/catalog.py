from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .tariff import G13Zone, TariffRates


class CatalogError(ValueError):
	pass


@dataclass(frozen=True)
class TariffEntry:
	identifier: str
	provider: str
	tariff: str
	valid_from: date
	valid_to: date
	gross: bool
	rates: TariffRates


def _money(value: Any, field: str) -> Decimal:
	try:
		result=Decimal(str(value))
	except (InvalidOperation, ValueError) as error:
		raise CatalogError(f"Invalid number in {field}") from error
	if not result.is_finite() or result < 0:
		raise CatalogError(f"Invalid non-negative number in {field}")
	return result


def _zones(value: Any, field: str) -> dict[G13Zone, Decimal]:
	if not isinstance(value, dict) or set(value) != {zone.value for zone in G13Zone}:
		raise CatalogError(f"{field} must contain exactly all G13 zones")
	return {zone: _money(value[zone.value], f"{field}.{zone.value}") for zone in G13Zone}


def load_catalog(path: Path) -> list[TariffEntry]:
	try:
		root=json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as error:
		raise CatalogError(f"Cannot read tariff catalog: {error}") from error
	if not isinstance(root, dict) or root.get("schema_version") != 1 or not isinstance(root.get("tariffs"), list):
		raise CatalogError("Unsupported tariff catalog schema")
	entries=[]
	for index,item in enumerate(root["tariffs"]):
		try:
			valid_from=date.fromisoformat(item["valid_from"])
			valid_to=date.fromisoformat(item["valid_to"])
			if valid_to < valid_from or item["gross"] is not True:
				raise CatalogError("Dates or gross flag are invalid")
			entries.append(TariffEntry(
				identifier=str(item["id"]),
				provider=str(item["provider"]),
				tariff=str(item["tariff"]),
				valid_from=valid_from,
				valid_to=valid_to,
				gross=True,
				rates=TariffRates(
					energy=_zones(item["energy"], "energy"),
					distribution=_zones(item["distribution"], "distribution"),
					common_variable=_money(item["common_variable"], "common_variable"),
					fixed_monthly=_money(item["fixed_monthly"], "fixed_monthly"),
				),
			))
		except (KeyError, TypeError, ValueError) as error:
			if isinstance(error, CatalogError):
				raise
			raise CatalogError(f"Invalid tariff entry {index}: {error}") from error
	return entries


def select_tariff(entries: list[TariffEntry], day: date, tariff: str="G13") -> TariffEntry:
	matches=[entry for entry in entries if entry.tariff == tariff and entry.valid_from <= day <= entry.valid_to]
	if not matches:
		raise CatalogError(f"No {tariff} tariff is valid on {day.isoformat()}")
	return max(matches, key=lambda entry: entry.valid_from)
