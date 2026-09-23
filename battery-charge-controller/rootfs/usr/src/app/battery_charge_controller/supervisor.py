from __future__ import annotations

from typing import Any


class SupervisorClient:
	def __init__(self, session, token: str, base_url: str="http://supervisor"):
		self.session=session
		self.base_url=base_url.rstrip("/")
		self.headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

	async def get_self_info(self) -> dict[str, Any]:
		async with self.session.get(f"{self.base_url}/addons/self/info", headers=self.headers) as response:
			response.raise_for_status()
			payload=await response.json()
			return payload.get("data", payload)

	async def mqtt_service(self) -> dict[str, Any]:
		async with self.session.get(f"{self.base_url}/services/mqtt", headers=self.headers) as response:
			response.raise_for_status()
			payload=await response.json()
			return payload.get("data", payload)
