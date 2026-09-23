import unittest

from battery_charge_controller.calendar import Segment
from battery_charge_controller.config import AppConfig
from battery_charge_controller.executor import CommandExecutor, UncertainWriteError
from battery_charge_controller.ha import EntityNotFoundError, HomeAssistantClient, parse_soc, websocket_state_event
from tests.test_charge_core import base_options


class FakeHomeAssistant:
	def __init__(self, states):
		self.states=dict(states)
		self.calls=[]
		self.read_sequences={}

	async def call_service(self, domain, service, entity_id, data):
		self.calls.append((f"{domain}.{service}", entity_id, data))
		if domain == "number":
			self.states[entity_id]=str(data["value"])
		elif domain == "select":
			self.states[entity_id]=str(data["option"])
		elif domain == "switch":
			self.states[entity_id]="on" if service == "turn_on" else "off"

	async def get_state(self, entity_id):
		self.calls.append(("get", entity_id, {}))
		sequence=self.read_sequences.get(entity_id)
		if sequence:
			return sequence.pop(0)
		return self.states.get(entity_id, "unavailable")

	@property
	def written_entities(self):
		return [entity for action,entity,data in self.calls if action != "get"]

	def write_count(self, entity_id):
		return sum(1 for action,entity,data in self.calls if action != "get" and entity == entity_id)


class HomeAssistantNormalizationTests(unittest.TestCase):
	def test_parse_soc_rejects_unavailable_non_numeric_and_out_of_range(self):
		for value in ("unknown", "unavailable", "", "abc", "-1", "101", None):
			with self.subTest(value=value):
				self.assertIsNone(parse_soc(value))
		self.assertEqual(parse_soc("42,5"), 42.5)

	def test_websocket_filters_to_configured_entities(self):
		watched={"sensor.battery"}
		payload={"event": {"data": {"entity_id": "sensor.battery", "new_state": {"state": "42", "last_updated": "2026-09-23T10:00:00+00:00"}}}}
		event=websocket_state_event(payload, watched)
		self.assertEqual((event.entity_id, event.state), ("sensor.battery", "42"))
		payload["event"]["data"]["entity_id"]="sensor.other"
		self.assertIsNone(websocket_state_event(payload, watched))


class MissingResponse:
	status=404

	async def __aenter__(self):
		return self

	async def __aexit__(self, exc_type, exc, traceback):
		return False

	async def read(self):
		return b""


class MissingSession:
	def get(self, url, headers):
		return MissingResponse()


class HomeAssistantClientTests(unittest.IsolatedAsyncioTestCase):
	async def test_state_404_reports_exact_missing_entity(self):
		client=HomeAssistantClient(MissingSession(), "token")
		with self.assertRaisesRegex(EntityNotFoundError, "select\\.deye_prog4_charge"):
			await client.get_state("select.deye_prog4_charge")


class CommandExecutorTests(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		options=base_options()
		options["verify_delay_seconds"]=0
		self.config=AppConfig.from_options(options)
		entities=self.config.entities
		states={entities.grid_charge: "off", entities.prog5_time: "16:00"}
		states.update({entity: "20" for entity in entities.capacity})
		states.update({entity: self.config.reset_charge_option for entity in entities.charge})
		self.client=FakeHomeAssistant(states)
		self.executor=CommandExecutor(self.client, self.config)

	async def test_night_sets_prog1_then_mode_then_grid_with_readback(self):
		await self.executor.start_charge(Segment.NIGHT, 80)
		entities=self.config.entities
		self.assertEqual(self.client.calls, [
			("number.set_value", entities.capacity[0], {"value": 80}),
			("get", entities.capacity[0], {}),
			("select.select_option", entities.charge[0], {"option": "Allow Grid & Gen"}),
			("get", entities.charge[0], {}),
			("switch.turn_on", entities.grid_charge, {}),
			("get", entities.grid_charge, {}),
		])

	async def test_day_writes_only_prog4_before_grid(self):
		await self.executor.start_charge(Segment.DAY, 80)
		entities=self.config.entities
		self.assertEqual(self.client.written_entities, [entities.capacity[3], entities.charge[3], entities.grid_charge])

	async def test_full_reset_turns_grid_off_then_resets_all_programs(self):
		await self.executor.full_reset("hard_stop")
		entities=self.config.entities
		self.assertEqual(self.client.written_entities, [entities.grid_charge, *entities.capacity, *entities.charge])

	async def test_missing_readback_blocks_grid_on_and_attempts_grid_off(self):
		capacity=self.config.entities.capacity[0]
		self.client.read_sequences[capacity]=["unavailable"]
		with self.assertRaises(UncertainWriteError):
			await self.executor.start_charge(Segment.NIGHT, 80)
		grid=self.config.entities.grid_charge
		self.assertNotIn(("switch.turn_on", grid, {}), self.client.calls)
		self.assertIn(("switch.turn_off", grid, {}), self.client.calls)

	async def test_confirmed_mismatch_retries_and_then_succeeds(self):
		capacity=self.config.entities.capacity[0]
		self.client.read_sequences[capacity]=["79", "80"]
		await self.executor.start_charge(Segment.NIGHT, 80)
		self.assertEqual(self.client.write_count(capacity), 2)

	async def test_prog5_is_written_only_when_season_value_differs(self):
		await self.executor.sync_prog5_time("16:00")
		self.assertEqual(self.client.written_entities, [])
		await self.executor.sync_prog5_time("19:00")
		self.assertEqual(self.client.written_entities, [self.config.entities.prog5_time])


if __name__ == "__main__":
	unittest.main()
