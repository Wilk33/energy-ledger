from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from .ledger import MeterKind


@dataclass(frozen=True)
class MeterEvent:
	kind: MeterKind
	value: str
	occurred_at: datetime


def _kind(entity_id: str, import_entity: str, export_entity: str) -> MeterKind | None:
	if entity_id == import_entity:
		return MeterKind.IMPORT
	if entity_id == export_entity:
		return MeterKind.EXPORT
	return None


def history_events(payload: list[list[dict[str, Any]]], import_entity: str, export_entity: str) -> list[MeterEvent]:
	events=[]
	for series in payload:
		series_entity=series[0].get("entity_id", "") if series else ""
		for item in series:
			kind=_kind(item.get("entity_id", series_entity), import_entity, export_entity)
			stamp=item.get("last_updated") or item.get("last_changed")
			if kind is None or not stamp or "state" not in item:
				continue
			events.append(MeterEvent(kind, str(item["state"]), datetime.fromisoformat(stamp.replace("Z", "+00:00"))))
	return sorted(events, key=lambda event: event.occurred_at)


def websocket_meter_event(payload: dict[str, Any], import_entity: str, export_entity: str) -> MeterEvent | None:
	data=payload.get("event", {}).get("data", {})
	new_state=data.get("new_state")
	if not isinstance(new_state, dict):
		return None
	entity_id=data.get("entity_id", "")
	kind=_kind(entity_id, import_entity, export_entity)
	stamp=new_state.get("last_updated") or new_state.get("last_changed")
	if kind is None or not stamp or "state" not in new_state:
		return None
	return MeterEvent(kind, str(new_state["state"]), datetime.fromisoformat(stamp.replace("Z", "+00:00")))


class HomeAssistantClient:
	def __init__(self, session, token: str, rest_url: str="http://supervisor/core/api", websocket_url: str="ws://supervisor/core/websocket"):
		self.session=session
		self.rest_url=rest_url.rstrip("/")
		self.websocket_url=websocket_url
		self.headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

	async def history(self, start: datetime, end: datetime, import_entity: str, export_entity: str) -> list[MeterEvent]:
		url=f"{self.rest_url}/history/period/{quote(start.isoformat(), safe='')}"
		params={
			"end_time": end.isoformat(),
			"filter_entity_id": f"{import_entity},{export_entity}",
			"minimal_response": "",
			"no_attributes": "",
			"significant_changes_only": "",
		}
		async with self.session.get(url, headers=self.headers, params=params) as response:
			response.raise_for_status()
			payload=await response.json()
		return history_events(payload, import_entity, export_entity)

	async def event_stream(self, import_entity: str, export_entity: str):
		async with self.session.ws_connect(self.websocket_url, heartbeat=30) as websocket:
			first=await websocket.receive_json()
			if first.get("type") != "auth_required":
				raise RuntimeError("Home Assistant WebSocket did not request authentication")
			await websocket.send_json({"type": "auth", "access_token": self.headers["Authorization"].removeprefix("Bearer ")})
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
				payload=message.json()
				event=websocket_meter_event(payload, import_entity, export_entity)
				if event is not None:
					yield event
