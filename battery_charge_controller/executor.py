from __future__ import annotations

import asyncio
import logging
from typing import Any

from .calendar import Segment
from .config import AppConfig
from .ha import UNAVAILABLE_STATES


LOGGER=logging.getLogger(__name__)


class CommandError(RuntimeError):
	pass


class UncertainWriteError(CommandError):
	pass


class VerificationError(CommandError):
	pass


def _matches(actual: str, expected: Any) -> bool:
	if isinstance(expected, (int, float)):
		try:
			return abs(float(actual)-float(expected)) <= 0.1
		except ValueError:
			return False
	return str(actual).strip().lower() == str(expected).strip().lower()


class CommandExecutor:
	def __init__(self, home_assistant, config: AppConfig):
		self.home_assistant=home_assistant
		self.config=config
		self.lock=asyncio.Lock()

	async def _read_available(self, entity_id: str) -> str:
		loop=asyncio.get_running_loop()
		deadline=loop.time()+self.config.verify_timeout_seconds
		while True:
			actual=await self.home_assistant.get_state(entity_id)
			if str(actual).strip().lower() not in UNAVAILABLE_STATES:
				return actual
			remaining=deadline-loop.time()
			if remaining <= 0:
				raise UncertainWriteError(f"Brak dostępnego odczytu {entity_id} przez {self.config.verify_timeout_seconds:g} s")
			await asyncio.sleep(min(self.config.verify_poll_seconds, remaining))

	async def _wait_for_expected(self, entity_id: str, expected: Any) -> str:
		if self.config.verify_delay_seconds:
			await asyncio.sleep(self.config.verify_delay_seconds)
		loop=asyncio.get_running_loop()
		deadline=loop.time()+self.config.verify_timeout_seconds
		last="unavailable"
		while True:
			last=await self.home_assistant.get_state(entity_id)
			if _matches(last, expected):
				return last
			remaining=deadline-loop.time()
			if remaining <= 0:
				break
			await asyncio.sleep(min(self.config.verify_poll_seconds, remaining))
		if str(last).strip().lower() in UNAVAILABLE_STATES:
			raise UncertainWriteError(f"Brak odczytu kontrolnego {entity_id} przez {self.config.verify_timeout_seconds:g} s")
		return last

	async def _set_verified(self, entity_id: str, domain: str, service: str, data: dict[str, Any], expected: Any):
		for attempt in range(self.config.verified_mismatch_retries):
			LOGGER.info("Ustawiam %s na %s, próba %s", entity_id, expected, attempt+1)
			await self.home_assistant.call_service(domain, service, entity_id, data)
			actual=await self._wait_for_expected(entity_id, expected)
			if _matches(actual, expected):
				return
			LOGGER.warning("Niezgodny odczyt %s: oczekiwano %s, otrzymano %s", entity_id, expected, actual)
		raise VerificationError(f"Nie udało się potwierdzić {entity_id}={expected}")

	async def _force_grid_off(self):
		entity=self.config.entities.grid_charge
		try:
			await self.home_assistant.call_service("switch", "turn_off", entity, {})
			actual=await self._wait_for_expected(entity, "off")
			if not _matches(actual, "off"):
				raise UncertainWriteError(f"Nie potwierdzono awaryjnego wyłączenia {entity}: {actual}")
		except Exception as error:
			LOGGER.error("Awaryjne wyłączenie Grid Charge nie zostało potwierdzone: %s", error)

	async def start_charge(self, segment: Segment, target: float):
		async with self.lock:
			index=0 if segment is Segment.NIGHT else 3
			try:
				await self._set_verified(self.config.entities.capacity[index], "number", "set_value", {"value": target}, target)
				await self._set_verified(self.config.entities.charge[index], "select", "select_option", {"option": self.config.active_charge_option}, self.config.active_charge_option)
				await self._set_verified(self.config.entities.grid_charge, "switch", "turn_on", {}, "on")
			except Exception:
				await self._force_grid_off()
				raise

	async def full_reset(self, reason: str):
		async with self.lock:
			LOGGER.warning("Pełny reset ładowania: %s", reason)
			await self._set_verified(self.config.entities.grid_charge, "switch", "turn_off", {}, "off")
			errors=[]
			for entity in self.config.entities.capacity:
				try:
					await self._set_verified(entity, "number", "set_value", {"value": self.config.reset_capacity}, self.config.reset_capacity)
				except Exception as error:
					errors.append(f"{entity}: {error}")
			for entity in self.config.entities.charge:
				try:
					await self._set_verified(entity, "select", "select_option", {"option": self.config.reset_charge_option}, self.config.reset_charge_option)
				except Exception as error:
					errors.append(f"{entity}: {error}")
			if errors:
				raise CommandError("; ".join(errors))

	async def sync_prog5_time(self, expected: str):
		async with self.lock:
			entity=self.config.entities.prog5_time
			current=await self._read_available(entity)
			if _matches(current, expected):
				return
			await self._set_verified(entity, "select", "select_option", {"option": expected}, expected)
