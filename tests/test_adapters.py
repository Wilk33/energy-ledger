import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from energy_ledger.ha import history_events, websocket_meter_event
from energy_ledger.mqtt import discovery_messages, state_payload
from energy_ledger.ledger import EnergyLedger, MeterKind
from energy_ledger.tariff import G13Zone, TariffRates


class HomeAssistantAdapterTests(unittest.TestCase):
	def test_history_is_normalized_and_sorted_for_both_entities(self):
		payload=[
			[{"entity_id": "sensor.export_total", "state": "4", "last_updated": "2026-09-01T08:02:00+00:00"}],
			[{"entity_id": "sensor.import_total", "state": "3", "last_updated": "2026-09-01T08:01:00+00:00"}],
		]
		events=history_events(payload, "sensor.import_total", "sensor.export_total")
		self.assertEqual([(event.kind, event.value) for event in events], [(MeterKind.IMPORT, "3"), (MeterKind.EXPORT, "4")])

	def test_minimal_history_inherits_entity_id_from_first_series_item(self):
		payload=[[
			{"entity_id": "sensor.import_total", "state": "3", "last_updated": "2026-09-01T08:01:00+00:00"},
			{"state": "4", "last_changed": "2026-09-01T08:02:00+00:00"},
			{"state": "5", "last_changed": "2026-09-01T08:03:00+00:00"},
		]]
		events=history_events(payload, "sensor.import_total", "sensor.export_total")
		self.assertEqual([event.value for event in events], ["3", "4", "5"])

	def test_websocket_filters_unrelated_and_missing_new_state(self):
		unrelated={"event": {"data": {"entity_id": "sensor.temperature", "new_state": {"state": "20", "last_updated": "2026-09-01T08:00:00+00:00"}}}}
		removed={"event": {"data": {"entity_id": "sensor.import_total", "new_state": None}}}
		self.assertIsNone(websocket_meter_event(unrelated, "sensor.import_total", "sensor.export_total"))
		self.assertIsNone(websocket_meter_event(removed, "sensor.import_total", "sensor.export_total"))


class MqttAdapterTests(unittest.TestCase):
	def test_discovery_contains_stable_unique_ids_and_single_state_topic(self):
		messages=discovery_messages("homeassistant", "energy_ledger", "Dom")
		self.assertGreaterEqual(len(messages), 10)
		self.assertTrue(all(message.payload["state_topic"] == "energy_ledger/state" for message in messages))
		self.assertEqual(len({message.payload["unique_id"] for message in messages}), len(messages))

	def test_state_payload_exposes_live_signed_balance_and_costs(self):
		zero={zone: Decimal("0") for zone in G13Zone}
		ledger=EnergyLedger(discount=Decimal("0.8"), rates=TariffRates(zero, zero, Decimal("0"), Decimal("12")), now=datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/Warsaw")))
		ledger.apply_correction(Decimal("-5"), G13Zone.OTHER)
		payload=state_payload(ledger, "manual", "manual-prices", datetime(2026, 9, 1, 12, 0, tzinfo=ZoneInfo("Europe/Warsaw")))
		self.assertEqual(payload["virtual_storage_kwh"], -5.0)
		self.assertEqual(payload["uncovered_energy_kwh"], 5.0)
		self.assertEqual(payload["estimated_bill_pln"], 12.0)


if __name__ == "__main__":
	unittest.main()
