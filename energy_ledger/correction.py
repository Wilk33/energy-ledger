from __future__ import annotations

from decimal import Decimal
from typing import Awaitable, Callable

from .ledger import EnergyLedger
from .storage import JsonStateStore


class CorrectionCoordinator:
	def __init__(self, store: JsonStateStore):
		self.store=store

	def consume(self, configured_value: Decimal, ledger: EnergyLedger, reset_option: Callable[[], None]) -> bool:
		data=self.store.load()
		pending=data.get("correction_awaiting_reset")
		if configured_value == 0:
			data.pop("correction_awaiting_reset", None)
			data["ledger"]=ledger.to_dict()
			self.store.save(data)
			return False
		canonical=str(configured_value.normalize())
		if pending is not None and pending != canonical:
			raise RuntimeError("Previous correction has not yet been reset")
		applied=pending is None
		if applied:
			ledger.apply_correction(configured_value)
			data["ledger"]=ledger.to_dict()
			data["correction_awaiting_reset"]=canonical
			self.store.save(data)
		reset_option()
		self._complete_reset(ledger)
		return applied

	async def consume_async(self, configured_value: Decimal, ledger: EnergyLedger, reset_option: Callable[[], Awaitable[None]]) -> bool:
		data=self.store.load()
		pending=data.get("correction_awaiting_reset")
		if configured_value == 0:
			data.pop("correction_awaiting_reset", None)
			data["ledger"]=ledger.to_dict()
			self.store.save(data)
			return False
		canonical=str(configured_value.normalize())
		if pending is not None and pending != canonical:
			raise RuntimeError("Previous correction has not yet been reset")
		applied=pending is None
		if applied:
			ledger.apply_correction(configured_value)
			data["ledger"]=ledger.to_dict()
			data["correction_awaiting_reset"]=canonical
			self.store.save(data)
		await reset_option()
		self._complete_reset(ledger)
		return applied

	def _complete_reset(self, ledger: EnergyLedger):
		data=self.store.load()
		data.pop("correction_awaiting_reset", None)
		data["ledger"]=ledger.to_dict()
		self.store.save(data)
