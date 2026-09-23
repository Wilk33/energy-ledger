import asyncio
import unittest
from types import SimpleNamespace

from battery_charge_controller.mqtt import MqttController, discovery_messages
from battery_charge_controller.settings import UserSettings


class ChargeMqttTests(unittest.TestCase):
	def setUp(self):
		self.messages=discovery_messages("homeassistant", "battery_charge_controller", "Ładowanie baterii")

	def test_discovery_contains_exactly_four_numbers_two_switches_two_sensors(self):
		components=[message.component for message in self.messages]
		self.assertEqual(len(self.messages), 8)
		self.assertEqual(components.count("number"), 4)
		self.assertEqual(components.count("switch"), 2)
		self.assertEqual(components.count("sensor"), 2)

	def test_discovery_has_no_duplicate_soc_season_decision_or_write_status(self):
		identifiers={message.object_id for message in self.messages}
		self.assertFalse(identifiers & {"soc", "season", "decision", "write_status"})
		self.assertEqual(len(identifiers), 8)

	def test_duration_sensors_use_seconds_and_duration_device_class(self):
		for message in [item for item in self.messages if item.component == "sensor"]:
			self.assertEqual(message.payload["device_class"], "duration")
			self.assertEqual(message.payload["unit_of_measurement"], "s")

	def test_numbers_are_sliders_from_twenty_to_one_hundred(self):
		for message in [item for item in self.messages if item.component == "number"]:
			self.assertEqual((message.payload["min"], message.payload["max"], message.payload["step"]), (20, 100, 1))
			self.assertEqual(message.payload["mode"], "slider")


class ChargeMqttCommandTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		self.queue=asyncio.Queue()
		self.controller=MqttController({}, "battery_charge_controller", "homeassistant", "Ładowanie baterii", asyncio.get_running_loop(), self.queue)

	async def test_retained_command_is_ignored_but_live_command_is_queued(self):
		retained=SimpleNamespace(topic="battery_charge_controller/command/night_enabled", payload=b"ON", retain=True)
		live=SimpleNamespace(topic="battery_charge_controller/command/night_enabled", payload=b"ON", retain=False)
		self.controller.handle_message(retained)
		self.assertTrue(self.queue.empty())
		self.controller.handle_message(live)
		command=await asyncio.wait_for(self.queue.get(), 1)
		self.assertEqual((command.key, command.value), ("night_enabled", "ON"))

	async def test_unrecognized_topic_is_ignored(self):
		message=SimpleNamespace(topic="battery_charge_controller/command/soc", payload=b"10", retain=False)
		self.controller.handle_message(message)
		self.assertTrue(self.queue.empty())

	async def test_settings_payload_contains_exactly_six_writable_states(self):
		payload=self.controller.settings_payload(UserSettings.defaults())
		self.assertEqual(set(payload), {"night_threshold", "night_target", "day_threshold", "day_target", "night_enabled", "day_enabled"})
		self.assertEqual(payload["night_enabled"], "OFF")


if __name__ == "__main__":
	unittest.main()
