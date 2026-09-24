from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp

from .calendar import Segment, Season, is_workday, season_for, window_for
from .config import AppConfig
from .decision import DecisionAction, evaluate_segment
from .executor import CommandExecutor
from .ha import EntityNotFoundError, HomeAssistantClient, parse_soc
from .mqtt import MqttCommand, MqttController
from .settings import SettingsCoordinator, SettingsError, UserSettings
from .storage import JsonStateStore
from .supervisor import SupervisorClient


LOGGER=logging.getLogger(__name__)


class MissingEntitiesError(RuntimeError):
	pass


class ControllerState(str, Enum):
	STARTING="starting"
	IDLE="idle"
	WAITING_NIGHT="waiting_night"
	WAITING_DAY="waiting_day"
	CHARGING_NIGHT="charging_night"
	CHARGING_DAY="charging_day"
	RESETTING="resetting"
	FAULT="fault"


class BatteryChargeRuntime:
	def __init__(self, config: AppConfig, home_assistant, executor: CommandExecutor, mqtt: MqttController, settings: SettingsCoordinator):
		self.config=config
		self.home_assistant=home_assistant
		self.executor=executor
		self.mqtt=mqtt
		self.settings=settings
		self.state=ControllerState.STARTING
		self.active_segment: Segment | None=None
		self.active_window=None
		self.last_valid_soc_at: datetime | None=None
		self.synced_prog5_value: str | None=None
		self.evaluate_lock=asyncio.Lock()
		self.stop_event=asyncio.Event()

	@property
	def watched_entities(self) -> set[str]:
		entities=self.config.entities
		return {entities.battery_soc, entities.grid_charge, entities.prog5_time, *entities.capacity, *entities.charge}

	def _prog5_value(self, now: datetime) -> str:
		season=season_for(now.date(), self.config)
		clock=self.config.summer_prog5_time if season is Season.SUMMER else self.config.winter_prog5_time
		return str(clock)

	async def _sync_prog5(self, now: datetime):
		expected=self._prog5_value(now)
		if self.synced_prog5_value == expected:
			return
		await self.executor.sync_prog5_time(expected)
		self.synced_prog5_value=expected

	async def initialize(self, now: datetime | None=None):
		local=(now or datetime.now(timezone.utc)).astimezone(self.config.timezone)
		self.mqtt.publish_discovery()
		self.mqtt.publish_settings(self.settings.settings)
		self.mqtt.publish_durations(None, None)
		missing=[]
		for entity_id in sorted(self.watched_entities):
			try:
				await self.home_assistant.get_state(entity_id)
			except EntityNotFoundError:
				missing.append(entity_id)
		if missing:
			formatted="\n- ".join(missing)
			raise MissingEntitiesError(
				"Nie znaleziono skonfigurowanych encji Home Assistant. "
				"Popraw identyfikatory w zakładce Konfiguracja aplikacji:\n- "
				+formatted
			)
		await self._sync_prog5(local)
		await self._reconcile_startup(local)
		self.state=ControllerState.IDLE if self.active_segment is None else self._charging_state(self.active_segment)

	def _charging_state(self, segment: Segment) -> ControllerState:
		return ControllerState.CHARGING_NIGHT if segment is Segment.NIGHT else ControllerState.CHARGING_DAY

	def _soc_settings(self, segment: Segment, season: Season) -> tuple[float, float]:
		prefix=f"{segment.value}_{season.value}"
		settings=self.settings.settings
		return (
			float(getattr(settings, f"{prefix}_threshold")),
			float(getattr(settings, f"{prefix}_target")),
		)

	async def _segment_matches_active_settings(self, segment: Segment, now: datetime) -> bool:
		window=window_for(now, segment, self.config)
		if not window.contains(now):
			return False
		if segment is Segment.DAY and not is_workday(now.date()):
			return False
		settings=self.settings.settings
		enabled=settings.night_enabled if segment is Segment.NIGHT else settings.day_enabled
		_threshold,target=self._soc_settings(segment, window.season)
		if not enabled:
			return False
		index=0 if segment is Segment.NIGHT else 3
		capacity=await self.home_assistant.get_state(self.config.entities.capacity[index])
		charge=await self.home_assistant.get_state(self.config.entities.charge[index])
		try:
			capacity_matches=abs(float(capacity)-float(target)) <= 0.1
		except ValueError:
			capacity_matches=False
		return capacity_matches and charge.strip().lower() == self.config.active_charge_option.lower()

	async def _reconcile_startup(self, now: datetime):
		grid=(await self.home_assistant.get_state(self.config.entities.grid_charge)).strip().lower()
		if grid == "on":
			for segment in (Segment.NIGHT, Segment.DAY):
				if await self._segment_matches_active_settings(segment, now):
					self.active_segment=segment
					self.active_window=window_for(now, segment, self.config)
					self.last_valid_soc_at=now
					return
			await self.executor.full_reset("startup_reconciliation")
			return
		partial=False
		for entity in self.config.entities.capacity:
			try:
				partial=partial or abs(float(await self.home_assistant.get_state(entity))-self.config.reset_capacity) > 0.1
			except ValueError:
				partial=True
		for entity in self.config.entities.charge:
			partial=partial or (await self.home_assistant.get_state(entity)).strip().lower() != self.config.reset_charge_option.lower()
		if partial:
			await self.executor.full_reset("startup_partial_state")

	async def _reset(self, reason: str, mark_completed: bool=False):
		self.state=ControllerState.RESETTING
		window=self.active_window
		try:
			await self.executor.full_reset(reason)
		except Exception:
			self.state=ControllerState.FAULT
			raise
		if mark_completed and window is not None:
			self.settings.mark_completed(window.execution_key)
		self.active_segment=None
		self.active_window=None
		self.last_valid_soc_at=None
		self.state=ControllerState.IDLE
		self.mqtt.publish_durations(None, None)

	async def apply_command(self, command: MqttCommand, now: datetime | None=None):
		local=(now or datetime.now(timezone.utc)).astimezone(self.config.timezone)
		try:
			if command.key.endswith("_enabled"):
				self.settings.apply_switch(command.key, command.value)
			else:
				self.settings.apply_number(command.key, float(command.value.replace(",", ".")))
		except (SettingsError, ValueError) as error:
			LOGGER.warning("Odrzucono komendę MQTT %s=%s: %s", command.key, command.value, error)
			self.mqtt.publish_settings(self.settings.settings)
			return
		self.mqtt.publish_settings(self.settings.settings)
		if self.active_segment is Segment.NIGHT and command.key == "night_enabled" and command.value == "OFF":
			async with self.evaluate_lock:
				if self.active_segment is Segment.NIGHT:
					await self._reset("night_disabled")
			return
		if self.active_segment is Segment.DAY and command.key == "day_enabled" and command.value == "OFF":
			async with self.evaluate_lock:
				if self.active_segment is Segment.DAY:
					await self._reset("day_disabled")
			return
		await self.evaluate(local)

	async def evaluate(self, now: datetime | None=None):
		async with self.evaluate_lock:
			local=(now or datetime.now(timezone.utc)).astimezone(self.config.timezone)
			await self._sync_prog5(local)
			soc=parse_soc(await self.home_assistant.get_state(self.config.entities.battery_soc))
			if self.active_segment is not None:
				if soc is None:
					if self.last_valid_soc_at is None or (local-self.last_valid_soc_at).total_seconds() >= self.config.soc_stale_seconds:
						await self._reset("stale_soc")
					else:
						remaining=self._seconds_until(self.active_window.end, local)
						self.mqtt.publish_durations(0, remaining)
					return
				self.last_valid_soc_at=local
				settings=self.settings.settings
				threshold,target=self._soc_settings(self.active_segment, self.active_window.season)
				enabled=settings.night_enabled if self.active_segment is Segment.NIGHT else settings.day_enabled
				model=self.config.night if self.active_segment is Segment.NIGHT else self.config.day
				decision=evaluate_segment(segment=self.active_segment, now=local, window=self.active_window, soc=soc, threshold=threshold, target=target, enabled=enabled, active=True, model=model)
				if decision.action is DecisionAction.RESET:
					await self._reset(decision.reason, mark_completed=True)
				else:
					remaining=self._seconds_until(self.active_window.end, local)
					self.mqtt.publish_durations(0, remaining)
				return
			segment=None
			day_window=window_for(local, Segment.DAY, self.config)
			night_window=window_for(local, Segment.NIGHT, self.config)
			if day_window.contains(local) and is_workday(local.date()):
				segment=Segment.DAY
				window=day_window
			elif night_window.contains(local):
				segment=Segment.NIGHT
				window=night_window
			else:
				self.state=ControllerState.IDLE
				self.mqtt.publish_durations(None, None)
				return
			if window.execution_key in self.settings.completed:
				self.state=ControllerState.IDLE
				self.mqtt.publish_durations(None, None)
				return
			settings=self.settings.settings
			threshold,target=self._soc_settings(segment, window.season)
			enabled=settings.night_enabled if segment is Segment.NIGHT else settings.day_enabled
			model=self.config.night if segment is Segment.NIGHT else self.config.day
			decision=evaluate_segment(segment=segment, now=local, window=window, soc=soc, threshold=threshold, target=target, enabled=enabled, active=False, model=model)
			LOGGER.info("Decyzja %s: %s, SOC=%s, próg=%s, cel=%s", segment.value, decision.action.value, soc, threshold, target)
			if decision.action is DecisionAction.START:
				await self.executor.start_charge(segment, target)
				self.active_segment=segment
				self.active_window=window
				self.last_valid_soc_at=local
				self.state=self._charging_state(segment)
				self.mqtt.publish_durations(0, self._seconds_until(window.end, local))
			elif decision.action is DecisionAction.WAIT:
				self.state=ControllerState.WAITING_NIGHT if segment is Segment.NIGHT else ControllerState.WAITING_DAY
				starts=self._seconds_until(decision.start_at, local)
				ends=self._seconds_until(window.end, local)
				self.mqtt.publish_durations(starts, ends)
			else:
				self.state=ControllerState.IDLE
				self.mqtt.publish_durations(None, None)

	async def _websocket_loop(self):
		while not self.stop_event.is_set():
			try:
				async for event in self.home_assistant.state_events(self.watched_entities):
					await self.evaluate(datetime.now(timezone.utc))
			except asyncio.CancelledError:
				raise
			except Exception as error:
				LOGGER.warning("Rozłączono zdarzenia Home Assistant: %s", error)
				await asyncio.sleep(5)

	async def _command_loop(self):
		while not self.stop_event.is_set():
			command=await self.mqtt.commands.get()
			try:
				await self.apply_command(command)
			except asyncio.CancelledError:
				raise
			except Exception as error:
				LOGGER.exception("Błąd obsługi komendy MQTT %s: %s", command.key, error)

	async def _timer_loop(self):
		while not self.stop_event.is_set():
			try:
				await asyncio.wait_for(self.stop_event.wait(), timeout=self.next_delay(datetime.now(timezone.utc)))
			except asyncio.TimeoutError:
				try:
					await self.evaluate()
				except asyncio.CancelledError:
					raise
				except Exception as error:
					LOGGER.exception("Błąd okresowej oceny: %s", error)
					await asyncio.sleep(5)

	@staticmethod
	def _seconds_until(end: datetime, now: datetime) -> int:
		return max(0, int((end.astimezone(timezone.utc)-now.astimezone(timezone.utc)).total_seconds()))

	def next_delay(self, now: datetime) -> float:
		delay=float(self.config.evaluation_seconds)
		if self.active_window is not None:
			remaining=(self.active_window.end.astimezone(timezone.utc)-now.astimezone(timezone.utc)).total_seconds()
			if remaining > 0:
				delay=min(delay, remaining)
			else:
				delay=0.1
		return max(0.1, delay)

	async def run(self):
		await self.initialize()
		tasks=[asyncio.create_task(self._websocket_loop()), asyncio.create_task(self._command_loop()), asyncio.create_task(self._timer_loop())]
		await self.stop_event.wait()
		for task in tasks:
			task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)
		self.mqtt.close()


def load_options_file(path: Path=Path("/data/options.json")) -> dict[str, Any]:
	value=json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(value, dict):
		raise ValueError("Options root must be an object")
	return value


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
		store=JsonStateStore(Path("/data/battery-charge-controller-state.json"))
		stored=store.load()
		settings=UserSettings.from_dict(stored.get("settings", {}))
		coordinator=SettingsCoordinator(store, settings, set(stored.get("completed", [])))
		home_assistant=HomeAssistantClient(session, token)
		executor=CommandExecutor(home_assistant, config)
		commands=asyncio.Queue()
		mqtt=MqttController(await supervisor.mqtt_service(), config.mqtt_base_topic, config.mqtt_discovery_prefix, config.device_name, asyncio.get_running_loop(), commands)
		mqtt.connect()
		runtime=BatteryChargeRuntime(config, home_assistant, executor, mqtt, coordinator)
		loop=asyncio.get_running_loop()
		for sig in (signal.SIGTERM, signal.SIGINT):
			try:
				loop.add_signal_handler(sig, runtime.stop_event.set)
			except NotImplementedError:
				pass
		await runtime.run()


def main():
	asyncio.run(async_main())
