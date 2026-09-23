from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

from .settings import UserSettings


LOGGER=logging.getLogger(__name__)

NUMBER_NAMES={
	"night_summer_threshold": "Nocny próg SOC lato",
	"night_summer_target": "Nocny cel SOC lato",
	"night_winter_threshold": "Nocny próg SOC zima",
	"night_winter_target": "Nocny cel SOC zima",
	"day_summer_threshold": "Dzienny próg SOC lato",
	"day_summer_target": "Dzienny cel SOC lato",
	"day_winter_threshold": "Dzienny próg SOC zima",
	"day_winter_target": "Dzienny cel SOC zima",
}

LEGACY_NUMBER_KEYS=("night_threshold", "night_target", "day_threshold", "day_target")

SWITCH_NAMES={
	"night_enabled": "Ładowanie nocne",
	"day_enabled": "Ładowanie dzienne",
}

SENSOR_NAMES={
	"charging_starts_in": "Czas do rozpoczęcia ładowania",
	"charging_ends_in": "Czas do zakończenia ładowania",
}

WRITABLE=set(NUMBER_NAMES) | set(SWITCH_NAMES)


@dataclass(frozen=True)
class DiscoveryMessage:
	component: str
	object_id: str
	topic: str
	payload: dict[str, Any]


@dataclass(frozen=True)
class MqttCommand:
	key: str
	value: str


def discovery_messages(discovery_prefix: str, base_topic: str, device_name: str) -> list[DiscoveryMessage]:
	availability=f"{base_topic}/availability"
	device={"identifiers": ["battery_charge_controller"], "name": device_name, "manufacturer": "Wilk33", "model": "Battery Charge Controller", "sw_version": "1.1.0"}
	messages=[]
	for key,name in NUMBER_NAMES.items():
		payload={
			"name": name,
			"unique_id": f"battery_charge_controller_{key}",
			"state_topic": f"{base_topic}/state/{key}",
			"command_topic": f"{base_topic}/command/{key}",
			"availability_topic": availability,
			"min": 20,
			"max": 100,
			"step": 1,
			"mode": "slider",
			"unit_of_measurement": "%",
			"device": device,
		}
		messages.append(DiscoveryMessage("number", key, f"{discovery_prefix}/number/battery_charge_controller/{key}/config", payload))
	for key,name in SWITCH_NAMES.items():
		payload={
			"name": name,
			"unique_id": f"battery_charge_controller_{key}",
			"state_topic": f"{base_topic}/state/{key}",
			"command_topic": f"{base_topic}/command/{key}",
			"availability_topic": availability,
			"payload_on": "ON",
			"payload_off": "OFF",
			"device": device,
		}
		messages.append(DiscoveryMessage("switch", key, f"{discovery_prefix}/switch/battery_charge_controller/{key}/config", payload))
	for key,name in SENSOR_NAMES.items():
		payload={
			"name": name,
			"unique_id": f"battery_charge_controller_{key}",
			"state_topic": f"{base_topic}/state/{key}",
			"availability_topic": availability,
			"device_class": "duration",
			"unit_of_measurement": "s",
			"state_class": "measurement",
			"device": device,
		}
		messages.append(DiscoveryMessage("sensor", key, f"{discovery_prefix}/sensor/battery_charge_controller/{key}/config", payload))
	return messages


class MqttController:
	def __init__(self, service: dict[str, Any], base_topic: str, discovery_prefix: str, device_name: str, loop: asyncio.AbstractEventLoop, commands: asyncio.Queue[MqttCommand]):
		self.service=service
		self.base_topic=base_topic
		self.discovery_prefix=discovery_prefix
		self.device_name=device_name
		self.loop=loop
		self.commands=commands
		self.client=None

	def settings_payload(self, settings: UserSettings) -> dict[str, str | float]:
		value=asdict(settings)
		return {
			**{key: value[key] for key in NUMBER_NAMES},
			"night_enabled": "ON" if value["night_enabled"] else "OFF",
			"day_enabled": "ON" if value["day_enabled"] else "OFF",
		}

	def handle_message(self, message):
		if bool(getattr(message, "retain", False)):
			return
		prefix=f"{self.base_topic}/command/"
		topic=str(message.topic)
		if not topic.startswith(prefix):
			return
		key=topic.removeprefix(prefix)
		if key not in WRITABLE:
			return
		try:
			value=bytes(message.payload).decode("utf-8").strip()
		except (UnicodeDecodeError, TypeError):
			LOGGER.warning("Odrzucono niepoprawną komendę MQTT dla %s", key)
			return
		self.loop.call_soon_threadsafe(self.commands.put_nowait, MqttCommand(key, value))

	def connect(self):
		import paho.mqtt.client as mqtt
		self.client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="battery-charge-controller", protocol=mqtt.MQTTv311)
		username=self.service.get("username")
		if username:
			self.client.username_pw_set(username, self.service.get("password"))
		if self.service.get("ssl"):
			self.client.tls_set()
		self.client.will_set(f"{self.base_topic}/availability", "offline", qos=1, retain=True)
		self.client.on_message=lambda client,userdata,message: self.handle_message(message)
		def on_connect(client, userdata, flags, reason_code, properties):
			client.subscribe(f"{self.base_topic}/command/+", qos=1)
		self.client.on_connect=on_connect
		self.client.connect_async(str(self.service.get("host", "core-mosquitto")), int(self.service.get("port", 1883)), 60)
		self.client.loop_start()

	def _publish(self, topic: str, value: Any, retain: bool=True):
		if self.client is None:
			raise RuntimeError("MQTT controller is not connected")
		if isinstance(value, (dict, list)):
			value=json.dumps(value, ensure_ascii=False)
		self.client.publish(topic, str(value), qos=1, retain=retain)

	def publish_discovery(self):
		for key in LEGACY_NUMBER_KEYS:
			self._publish(f"{self.discovery_prefix}/number/battery_charge_controller/{key}/config", "")
		for message in discovery_messages(self.discovery_prefix, self.base_topic, self.device_name):
			self._publish(message.topic, message.payload)
		self._publish(f"{self.base_topic}/availability", "online")

	def publish_settings(self, settings: UserSettings):
		for key,value in self.settings_payload(settings).items():
			self._publish(f"{self.base_topic}/state/{key}", value)

	def publish_durations(self, starts_in: int | None, ends_in: int | None):
		self._publish(f"{self.base_topic}/state/charging_starts_in", "unavailable" if starts_in is None else max(0, int(starts_in)))
		self._publish(f"{self.base_topic}/state/charging_ends_in", "unavailable" if ends_in is None else max(0, int(ends_in)))

	def close(self):
		if self.client is None:
			return
		self._publish(f"{self.base_topic}/availability", "offline")
		self.client.disconnect()
		self.client.loop_stop()
