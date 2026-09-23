from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigurationError(ValueError):
	pass


@dataclass(frozen=True, order=True)
class ClockTime:
	hour: int
	minute: int

	@classmethod
	def parse(cls, value: str) -> "ClockTime":
		try:
			parts=str(value).split(":")
			if len(parts) != 2:
				raise ValueError
			hour,minute=(int(part) for part in parts)
		except (TypeError, ValueError) as error:
			raise ConfigurationError(f"Invalid time: {value}") from error
		if not 0 <= hour <= 23 or not 0 <= minute <= 59:
			raise ConfigurationError(f"Invalid time: {value}")
		return cls(hour, minute)

	@property
	def minutes(self) -> int:
		return self.hour*60+self.minute

	def __str__(self) -> str:
		return f"{self.hour:02d}:{self.minute:02d}"


@dataclass(frozen=True, order=True)
class MonthDay:
	month: int
	day: int

	@classmethod
	def parse(cls, value: str) -> "MonthDay":
		try:
			parts=str(value).split("-")
			if len(parts) != 2:
				raise ValueError
			month,day=(int(part) for part in parts)
		except (TypeError, ValueError) as error:
			raise ConfigurationError(f"Invalid month-day: {value}") from error
		try:
			date(2000, month, day)
		except ValueError as error:
			raise ConfigurationError(f"Invalid month-day: {value}") from error
		return cls(month, day)


@dataclass(frozen=True)
class EntityMap:
	battery_soc: str
	capacity: tuple[str, str, str, str, str, str]
	charge: tuple[str, str, str, str, str, str]
	grid_charge: str
	prog5_time: str


@dataclass(frozen=True)
class ChargeModel:
	full_charge_minutes: float
	reference_soc_range: float
	safety_minutes: float


def _entity(options: dict[str, Any], key: str, domain: str) -> str:
	value=str(options.get(key, "")).strip()
	if not value.startswith(f"{domain}.") or len(value) <= len(domain)+1:
		raise ConfigurationError(f"Option {key} must contain a {domain} entity id")
	return value


def _number(options: dict[str, Any], key: str, default: float, minimum: float=0) -> float:
	try:
		value=float(options.get(key, default))
	except (TypeError, ValueError) as error:
		raise ConfigurationError(f"Option {key} must be a number") from error
	if value < minimum:
		raise ConfigurationError(f"Option {key} must be at least {minimum}")
	return value


def _integer(options: dict[str, Any], key: str, default: int, minimum: int=0) -> int:
	try:
		value=int(options.get(key, default))
	except (TypeError, ValueError) as error:
		raise ConfigurationError(f"Option {key} must be an integer") from error
	if value < minimum:
		raise ConfigurationError(f"Option {key} must be at least {minimum}")
	return value


@dataclass(frozen=True)
class AppConfig:
	entities: EntityMap
	timezone: ZoneInfo
	summer_start: MonthDay
	winter_start: MonthDay
	night_start: ClockTime
	night_end: ClockTime
	summer_day_start: ClockTime
	summer_day_end: ClockTime
	summer_prog5_time: ClockTime
	winter_day_start: ClockTime
	winter_day_end: ClockTime
	winter_prog5_time: ClockTime
	night: ChargeModel
	day: ChargeModel
	evaluation_seconds: int
	soc_stale_seconds: int
	verify_delay_seconds: float
	verified_mismatch_retries: int
	reset_capacity: float
	active_charge_option: str
	reset_charge_option: str
	mqtt_base_topic: str
	mqtt_discovery_prefix: str
	device_name: str
	log_level: str

	@classmethod
	def from_options(cls, options: dict[str, Any]) -> "AppConfig":
		capacity=tuple(_entity(options, f"prog{index}_capacity_entity", "number") for index in range(1, 7))
		charge=tuple(_entity(options, f"prog{index}_charge_entity", "select") for index in range(1, 7))
		entities=EntityMap(
			battery_soc=_entity(options, "battery_soc_entity", "sensor"),
			capacity=capacity,
			charge=charge,
			grid_charge=_entity(options, "grid_charge_entity", "switch"),
			prog5_time=_entity(options, "prog5_time_entity", "select"),
		)
		controlled=(*entities.capacity, *entities.charge, entities.grid_charge, entities.prog5_time)
		if len(set(controlled)) != len(controlled):
			raise ConfigurationError("Controlled entity ids must be unique")
		try:
			timezone=ZoneInfo(str(options.get("timezone", "Europe/Warsaw")))
		except ZoneInfoNotFoundError as error:
			raise ConfigurationError("timezone must be a valid IANA timezone") from error
		summer_start=MonthDay.parse(options.get("summer_start", "04-01"))
		winter_start=MonthDay.parse(options.get("winter_start", "10-01"))
		if summer_start >= winter_start:
			raise ConfigurationError("summer_start must be before winter_start")
		night_start=ClockTime.parse(options.get("night_start", "22:00"))
		night_end=ClockTime.parse(options.get("night_end", "06:55"))
		if night_start.minutes <= night_end.minutes:
			raise ConfigurationError("night window must cross midnight")
		summer_day_start=ClockTime.parse(options.get("summer_day_start", "16:10"))
		summer_day_end=ClockTime.parse(options.get("summer_day_end", "18:55"))
		summer_prog5=ClockTime.parse(options.get("summer_prog5_time", "19:00"))
		winter_day_start=ClockTime.parse(options.get("winter_day_start", "13:10"))
		winter_day_end=ClockTime.parse(options.get("winter_day_end", "15:55"))
		winter_prog5=ClockTime.parse(options.get("winter_prog5_time", "16:00"))
		for name,start,end,prog5 in (
			("summer", summer_day_start, summer_day_end, summer_prog5),
			("winter", winter_day_start, winter_day_end, winter_prog5),
		):
			if not start < end < prog5:
				raise ConfigurationError(f"{name} day start, end and Prog5 time must be ordered")
			if end.minutes >= night_start.minutes:
				raise ConfigurationError(f"{name} day and night windows overlap")
		reset_capacity=_number(options, "reset_capacity", 20)
		if reset_capacity > 100:
			raise ConfigurationError("reset_capacity must not exceed 100")
		mqtt_base=str(options.get("mqtt_base_topic", "battery_charge_controller")).strip(" / ")
		discovery=str(options.get("mqtt_discovery_prefix", "homeassistant")).strip(" / ")
		if not mqtt_base or not discovery:
			raise ConfigurationError("MQTT topics cannot be empty")
		active=str(options.get("active_charge_option", "Allow Grid & Gen")).strip()
		reset=str(options.get("reset_charge_option", "Allow Gen")).strip()
		if not active or not reset:
			raise ConfigurationError("Charge select options cannot be empty")
		return cls(
			entities=entities,
			timezone=timezone,
			summer_start=summer_start,
			winter_start=winter_start,
			night_start=night_start,
			night_end=night_end,
			summer_day_start=summer_day_start,
			summer_day_end=summer_day_end,
			summer_prog5_time=summer_prog5,
			winter_day_start=winter_day_start,
			winter_day_end=winter_day_end,
			winter_prog5_time=winter_prog5,
			night=ChargeModel(
				_number(options, "night_full_charge_minutes", 157, 0.001),
				_number(options, "night_reference_soc_range", 80, 0.001),
				_number(options, "night_safety_minutes", 15),
			),
			day=ChargeModel(
				_number(options, "day_full_charge_minutes", 201, 0.001),
				_number(options, "day_reference_soc_range", 80, 0.001),
				_number(options, "day_safety_minutes", 0),
			),
			evaluation_seconds=_integer(options, "evaluation_seconds", 300, 1),
			soc_stale_seconds=_integer(options, "soc_stale_seconds", 180, 1),
			verify_delay_seconds=_number(options, "verify_delay_seconds", 2),
			verified_mismatch_retries=_integer(options, "verified_mismatch_retries", 2, 1),
			reset_capacity=reset_capacity,
			active_charge_option=active,
			reset_charge_option=reset,
			mqtt_base_topic=mqtt_base,
			mqtt_discovery_prefix=discovery,
			device_name=str(options.get("device_name", "Ładowanie baterii")).strip() or "Ładowanie baterii",
			log_level=str(options.get("log_level", "INFO")).upper(),
		)
