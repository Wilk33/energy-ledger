from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator
from urllib.parse import quote


UNAVAILABLE_STATES={"", "unknown", "unavailable", "none", "null"}


@dataclass(frozen=True)
class StateEvent:
	entity_id: str
	state: str
	updated_at: datetime | None


def parse_soc(value: Any) -> float | None:
	if value is None or str(value).strip().lower() in UNAVAILABLE_STATES:
		return None
	try:
		result=float(str(value).replace(",", "."))
	except ValueError:
		return None
	return result if 0 <= result <= 100 else None


def websocket_state_event(payload: dict[str, Any], watched: set[str]) -> StateEvent | None:
	data=payload.get("event", {}).get("data", {})
	entity_id=str(data.get("entity_id", ""))
	new_state=data.get("new_state")
	if entity_id not in watched or not isinstance(new_state, dict):
		return None
	stamp=new_state.get("last_updated") or new_state.get("last_changed")
	updated=None
	if stamp:
		try:
			updated=datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
		except ValueError:
			updated=None
	return StateEvent(entity_id, str(new_state.get("state", "")), updated)


class HomeAssistantClient:
	def __init__(self, session, token: str, rest_url: str="http://supervisor/core/api", websocket_url: str="ws://supervisor/core/websocket"):
		self.session=session
		self.rest_url=rest_url.rstrip("/")
		self.websocket_url=websocket_url
		self.token=token
		self.headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

	async def get_state(self, entity_id: str) -> str:
		url=f"{self.rest_url}/states/{quote(entity_id, safe='')}"
		async with self.session.get(url, headers=self.headers) as response:
			response.raise_for_status()
			payload=await response.json()
			return str(payload.get("state", ""))

	async def call_service(self, domain: str, service: str, entity_id: str, data: dict[str, Any]):
		payload={"entity_id": entity_id, **data}
		url=f"{self.rest_url}/services/{domain}/{service}"
		async with self.session.post(url, headers=self.headers, json=payload) as response:
			response.raise_for_status()
			await response.read()

	async def state_events(self, watched: set[str]) -> AsyncIterator[StateEvent]:
		async with self.session.ws_connect(self.websocket_url, heartbeat=30) as websocket:
			first=await websocket.receive_json()
			if first.get("type") != "auth_required":
				raise RuntimeError("Home Assistant WebSocket did not request authentication")
			await websocket.send_json({"type": "auth", "access_token": self.token})
			auth=await websocket.receive_json()
			if auth.get("type") != "auth_ok":
				raise RuntimeError("Home Assistant WebSocket authentication failed")
			await websocket.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
			subscribed=await websocket.receive_json()
			if not subscribed.get("success"):
				raise RuntimeError("Home Assistant rejected state_changed subscription")
			async for message in websocket:
				if message.type.name != "TEXT":
					continue
				event=websocket_state_event(message.json(), watched)
				if event is not None:
					yield event
