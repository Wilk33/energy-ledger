from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import json

from .ledger import EnergyLedger
from .tariff import G13Zone


@dataclass(frozen=True)
class DiscoveryMessage:
	topic: str
	payload: dict[str, Any]


SENSORS={
	"virtual_storage_kwh": ("Magazyn wirtualny", "kWh", "energy", None),
	"uncovered_energy_kwh": ("Niepokryta energia", "kWh", "energy", None),
	"current_variable_cost_pln": ("Koszt energii w miesiącu", "PLN", "monetary", None),
	"current_fixed_cost_pln": ("Opłaty stałe w miesiącu", "PLN", "monetary", None),
	"estimated_bill_pln": ("Szacowana kwota miesiąca", "PLN", "monetary", None),
	"import_month_kwh": ("Import w miesiącu", "kWh", "energy", "total_increasing"),
	"export_month_kwh": ("Eksport w miesiącu", "kWh", "energy", "total_increasing"),
	"import_morning_peak_kwh": ("Import G13 szczyt przedpołudniowy", "kWh", "energy", "total_increasing"),
	"import_afternoon_peak_kwh": ("Import G13 szczyt popołudniowy", "kWh", "energy", "total_increasing"),
	"import_other_kwh": ("Import G13 pozostałe godziny", "kWh", "energy", "total_increasing"),
	"tariff_version": ("Wersja taryfy", None, None, None),
	"data_quality": ("Jakość danych", None, "enum", None),
	"last_update": ("Ostatnia aktualizacja", None, "timestamp", None),
}


def discovery_messages(prefix: str, base_topic: str, device_name: str) -> list[DiscoveryMessage]:
	device={"identifiers": ["energy_ledger"], "name": device_name, "manufacturer": "Energy Ledger", "model": "Virtual storage", "sw_version": "1.0.0"}
	messages=[]
	for key,(name,unit,device_class,state_class) in SENSORS.items():
		payload={
			"name": name,
			"unique_id": f"energy_ledger_{key}",
			"object_id": f"energy_ledger_{key}",
			"state_topic": f"{base_topic}/state",
			"value_template": "{{ value_json."+key+" }}",
			"availability_topic": f"{base_topic}/availability",
			"payload_available": "online",
			"payload_not_available": "offline",
			"device": device,
		}
		if unit:
			payload["unit_of_measurement"]=unit
		if device_class:
			payload["device_class"]=device_class
		if state_class:
			payload["state_class"]=state_class
		if key == "data_quality":
			payload["options"]=["ok", "manual-prices", "catalog-fallback", "stale"]
		messages.append(DiscoveryMessage(f"{prefix}/sensor/energy_ledger/{key}/config", payload))
	return messages


def state_payload(ledger: EnergyLedger, tariff_version: str, data_quality: str, updated_at: datetime) -> dict[str, Any]:
	state=ledger.state
	return {
		"virtual_storage_kwh": float(state.balance_kwh),
		"uncovered_energy_kwh": float(state.uncovered_kwh),
		"current_variable_cost_pln": float(ledger.variable_cost),
		"current_fixed_cost_pln": float(ledger.rates.fixed_monthly),
		"estimated_bill_pln": float(ledger.estimated_bill),
		"import_month_kwh": float(state.import_month_kwh),
		"export_month_kwh": float(state.export_month_kwh),
		"import_morning_peak_kwh": float(state.imports_by_zone[G13Zone.MORNING_PEAK]),
		"import_afternoon_peak_kwh": float(state.imports_by_zone[G13Zone.AFTERNOON_PEAK]),
		"import_other_kwh": float(state.imports_by_zone[G13Zone.OTHER]),
		"tariff_version": tariff_version,
		"data_quality": data_quality,
		"last_update": updated_at.isoformat(),
	}


class MqttPublisher:
	def __init__(self, service: dict[str, Any], base_topic: str, discovery_prefix: str, device_name: str):
		self.service=service
		self.base_topic=base_topic
		self.discovery_prefix=discovery_prefix
		self.device_name=device_name
		self.client=None

	def connect(self):
		import paho.mqtt.client as mqtt
		self.client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="energy-ledger", protocol=mqtt.MQTTv311)
		username=self.service.get("username")
		if username:
			self.client.username_pw_set(username, self.service.get("password"))
		if self.service.get("ssl"):
			self.client.tls_set()
		self.client.will_set(f"{self.base_topic}/availability", "offline", qos=1, retain=True)
		self.client.connect_async(str(self.service.get("host", "core-mosquitto")), int(self.service.get("port", 1883)), 60)
		self.client.loop_start()

	def publish_discovery(self):
		self._require_client()
		for message in discovery_messages(self.discovery_prefix, self.base_topic, self.device_name):
			self.client.publish(message.topic, json.dumps(message.payload, ensure_ascii=False), qos=1, retain=True)

	def publish_state(self, payload: dict[str, Any]):
		self._require_client()
		self.client.publish(f"{self.base_topic}/availability", "online", qos=1, retain=True)
		self.client.publish(f"{self.base_topic}/state", json.dumps(payload, ensure_ascii=False), qos=1, retain=True)

	def close(self):
		if self.client is None:
			return
		self.client.publish(f"{self.base_topic}/availability", "offline", qos=1, retain=True)
		self.client.disconnect()
		self.client.loop_stop()

	def _require_client(self):
		if self.client is None:
			raise RuntimeError("MQTT publisher is not connected")
