from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from .storage import JsonStateStore


class SettingsError(ValueError):
	pass


@dataclass(frozen=True)
class UserSettings:
	night_threshold: float
	night_target: float
	day_threshold: float
	day_target: float
	night_enabled: bool
	day_enabled: bool

	@classmethod
	def defaults(cls) -> "UserSettings":
		return cls(30, 80, 75, 80, False, False)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "UserSettings":
		defaults=asdict(cls.defaults())
		defaults.update({key: item for key,item in value.items() if key in defaults})
		settings=cls(**defaults)
		_validate(settings)
		return settings

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)


def _validate(settings: UserSettings):
	for value in (settings.night_threshold, settings.night_target, settings.day_threshold, settings.day_target):
		if not 20 <= float(value) <= 100:
			raise SettingsError("SOC settings must be between 20 and 100")
	if settings.night_target < settings.night_threshold:
		raise SettingsError("Night target cannot be below threshold")
	if settings.day_target < settings.day_threshold:
		raise SettingsError("Day target cannot be below threshold")


class SettingsCoordinator:
	def __init__(self, store: JsonStateStore, settings: UserSettings, completed: set[str] | None=None):
		self.store=store
		self.settings=settings
		self.completed=set(completed or ())

	def _persist(self, candidate: UserSettings | None=None):
		self.store.save({"settings": (candidate or self.settings).to_dict(), "completed": sorted(self.completed)})

	def apply_number(self, key: str, value: float) -> UserSettings:
		if key not in {"night_threshold", "night_target", "day_threshold", "day_target"}:
			raise SettingsError(f"Unknown number setting: {key}")
		try:
			parsed=float(value)
		except (TypeError, ValueError) as error:
			raise SettingsError("SOC setting must be numeric") from error
		candidate=replace(self.settings, **{key: parsed})
		_validate(candidate)
		self._persist(candidate)
		self.settings=candidate
		return candidate

	def apply_switch(self, key: str, value: str) -> UserSettings:
		if key not in {"night_enabled", "day_enabled"}:
			raise SettingsError(f"Unknown switch setting: {key}")
		if value not in {"ON", "OFF"}:
			raise SettingsError("Switch command must be ON or OFF")
		candidate=replace(self.settings, **{key: value == "ON"})
		_validate(candidate)
		self._persist(candidate)
		self.settings=candidate
		return candidate

	def mark_completed(self, execution_key: str):
		self.completed.add(execution_key)
		self._persist()
