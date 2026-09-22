from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiohttp

from .catalog import CatalogError, TariffEntry, load_catalog, select_tariff
from .catalog_update import update_catalog
from .config import AppConfig
from .correction import CorrectionCoordinator
from .ha import HomeAssistantClient
from .ledger import EnergyLedger
from .mqtt import MqttPublisher, state_payload
from .storage import JsonStateStore
from .supervisor import SupervisorClient
from .tariff import TariffRates, WARSAW


LOGGER=logging.getLogger(__name__)
PACKAGE_DIR=Path(__file__).resolve().parent
BUILTIN_CATALOG=PACKAGE_DIR / "data" / "tauron-g13.json"


def history_start(ledger_data: dict[str, Any], now: datetime, history_days: int) -> datetime:
	limit=now-timedelta(days=history_days)
	last_events=ledger_data.get("state", {}).get("last_event_at", {})
	if last_events:
		oldest=min(datetime.fromisoformat(value) for value in last_events.values())
		return max(oldest.astimezone(timezone.utc)-timedelta(minutes=5), limit.astimezone(timezone.utc))
	local=now.astimezone(WARSAW)
	month_start=local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
	return max(month_start.astimezone(timezone.utc), limit.astimezone(timezone.utc))


def manual_tariff_entry(rates: TariffRates, day: date) -> TariffEntry:
	return TariffEntry("manual", "manual", "G13", day, date.max, True, rates)


def load_options_file(path: Path=Path("/data/options.json")) -> dict[str, Any]:
	value=json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(value, dict):
		raise ValueError("Options root must be an object")
	return value


class EnergyLedgerRuntime:
	def __init__(self, session, token: str, options: dict[str, Any], state_path: Path=Path("/data/energy-ledger-state.json"), cache_catalog: Path=Path("/data/tariff-catalog.json")):
		self.session=session
		self.options=options
		self.config=AppConfig.from_options(options)
		self.store=JsonStateStore(state_path)
		self.cache_catalog=cache_catalog
		self.supervisor=SupervisorClient(session, token)
		self.home_assistant=HomeAssistantClient(session, token)
		self.ledger=None
		self.mqtt=None
		self.tariff_version="unknown"
		self.data_quality="stale"
		self.stop_event=asyncio.Event()

	async def initialize(self):
		entry=await self._load_tariff()
		rates=self.config.effective_rates(entry.rates)
		self.tariff_version=entry.identifier
		if self.config.manual_prices_enabled:
			self.data_quality="manual-prices"
		stored=self.store.load()
		ledger_data=stored.get("ledger")
		if ledger_data:
			self.ledger=EnergyLedger.from_dict(ledger_data, rates)
			self.ledger.discount=self.config.discount
		else:
			self.ledger=EnergyLedger(self.config.discount, rates)
		now=datetime.now(timezone.utc)
		start=history_start(ledger_data or {}, now, self.config.history_days)
		events=await self.home_assistant.history(start, now, self.config.import_entity, self.config.export_entity)
		if not ledger_data and events:
			self.ledger=EnergyLedger(self.config.discount, rates, now=events[0].occurred_at)
		for event in events:
			self.ledger.process_total(event.kind, event.value, event.occurred_at)
		self.ledger.advance_to(now)
		self.store.save_ledger(self.ledger)
		coordinator=CorrectionCoordinator(self.store)
		async def reset():
			await self.supervisor.reset_correction(self.options)
		await coordinator.consume_async(self.config.correction, self.ledger, reset)
		service=await self.supervisor.mqtt_service()
		self.mqtt=MqttPublisher(service, self.config.mqtt_base_topic, self.config.mqtt_discovery_prefix, self.config.device_name)
		self.mqtt.connect()
		self.mqtt.publish_discovery()
		self.publish()

	async def _load_tariff(self):
		if self.config.manual_prices_enabled:
			self.data_quality="manual-prices"
			return manual_tariff_entry(self.config.manual_rates, datetime.now(WARSAW).date())
		updated=False
		if self.config.tariff_update_enabled and self.config.tariff_catalog_url:
			try:
				await update_catalog(self.session, self.config.tariff_catalog_url, self.cache_catalog)
				updated=True
			except Exception as error:
				LOGGER.warning("Tariff update failed, using last valid catalog: %s", error)
		for path,quality in ((self.cache_catalog, "ok" if updated else "catalog-fallback"), (BUILTIN_CATALOG, "catalog-fallback")):
			if not path.exists():
				continue
			try:
				entry=select_tariff(load_catalog(path), datetime.now(WARSAW).date())
				self.data_quality=quality
				return entry
			except CatalogError as error:
				LOGGER.warning("Tariff catalog %s is unusable: %s", path, error)
		raise RuntimeError("No valid tariff catalog is available")

	def publish(self):
		if self.mqtt is None or self.ledger is None:
			return
		self.mqtt.publish_state(state_payload(self.ledger, self.tariff_version, self.data_quality, datetime.now(timezone.utc)))

	async def run(self):
		await self.initialize()
		tasks=[asyncio.create_task(self._stream_loop()), asyncio.create_task(self._calendar_loop())]
		await self.stop_event.wait()
		for task in tasks:
			task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)
		if self.mqtt:
			self.mqtt.close()

	async def _stream_loop(self):
		while not self.stop_event.is_set():
			try:
				async for event in self.home_assistant.event_stream(self.config.import_entity, self.config.export_entity):
					if self.ledger.process_total(event.kind, event.value, event.occurred_at):
						self.store.save_ledger(self.ledger)
						self.publish()
			except asyncio.CancelledError:
				raise
			except Exception as error:
				LOGGER.warning("Home Assistant event stream disconnected: %s", error)
				await asyncio.sleep(5)

	async def _calendar_loop(self):
		while not self.stop_event.is_set():
			try:
				await asyncio.wait_for(self.stop_event.wait(), timeout=60)
			except asyncio.TimeoutError:
				before=self.ledger.state.current_period
				self.ledger.advance_to(datetime.now(timezone.utc))
				if self.ledger.state.current_period != before:
					self.store.save_ledger(self.ledger)
					self.publish()


async def async_main():
	token=os.environ.get("SUPERVISOR_TOKEN", "")
	if not token:
		raise RuntimeError("SUPERVISOR_TOKEN is missing")
	async with aiohttp.ClientSession() as session:
		supervisor=SupervisorClient(session, token)
		try:
			info=await supervisor.get_self_info()
			options=info.get("options") or load_options_file()
		except Exception:
			options=load_options_file()
		config=AppConfig.from_options(options)
		logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
		runtime=EnergyLedgerRuntime(session, token, options)
		loop=asyncio.get_running_loop()
		for sig in (signal.SIGTERM, signal.SIGINT):
			try:
				loop.add_signal_handler(sig, runtime.stop_event.set)
			except NotImplementedError:
				pass
		await runtime.run()


def main():
	asyncio.run(async_main())


if __name__ == "__main__":
	main()
