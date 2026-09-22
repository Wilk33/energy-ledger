from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .catalog import load_catalog


MAX_CATALOG_BYTES=1024*1024


def install_catalog_bytes(content: bytes, target: Path):
	if not content or len(content) > MAX_CATALOG_BYTES:
		raise ValueError("Tariff catalog has an invalid size")
	target.parent.mkdir(parents=True, exist_ok=True)
	file_descriptor,temp_name=tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
	try:
		with os.fdopen(file_descriptor, "wb") as handle:
			handle.write(content)
			handle.flush()
			os.fsync(handle.fileno())
		load_catalog(Path(temp_name))
		os.replace(temp_name, target)
	finally:
		if os.path.exists(temp_name):
			os.unlink(temp_name)


async def update_catalog(session, url: str, target: Path, timeout_seconds: int=15):
	if not url.lower().startswith("https://"):
		raise ValueError("Tariff catalog URL must use HTTPS")
	async with session.get(url, timeout=timeout_seconds) as response:
		response.raise_for_status()
		content=await response.read()
	install_catalog_bytes(content, target)
