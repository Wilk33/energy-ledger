from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStateStore:
	def __init__(self, path: Path):
		self.path=path

	def load(self) -> dict[str, Any]:
		if not self.path.exists():
			return {}
		try:
			value=json.loads(self.path.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, OSError) as error:
			raise ValueError(f"Cannot load state file: {error}") from error
		if not isinstance(value, dict):
			raise ValueError("State file root must be an object")
		return value

	def save(self, value: dict[str, Any]):
		self.path.parent.mkdir(parents=True, exist_ok=True)
		descriptor,temp_name=tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
		try:
			with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
				json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temp_name, self.path)
		finally:
			if os.path.exists(temp_name):
				os.unlink(temp_name)
