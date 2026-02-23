"""File-based JSON cache.

Cache keyed by SHA256(repo_url + HEAD_sha), stored in ~/.cache/gitpulse/.
1-hour TTL. Atomic writes via temp file + rename.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class Cache:
	"""File-based JSON cache with TTL and atomic writes."""

	def __init__(
		self,
		cache_dir: str | Path = "~/.cache/gitpulse",
		ttl: int = 3600,
	) -> None:
		self.cache_dir = Path(cache_dir).expanduser()
		self.ttl = ttl
		self.cache_dir.mkdir(parents=True, exist_ok=True)

	@staticmethod
	def _make_key(repo_url: str, head_sha: str) -> str:
		return hashlib.sha256(f"{repo_url}:{head_sha}".encode()).hexdigest()

	def get(self, repo_url: str, head_sha: str) -> dict[str, Any] | None:
		key = self._make_key(repo_url, head_sha)
		path = self.cache_dir / f"{key}.json"
		if not path.exists():
			return None
		if time.time() - path.stat().st_mtime > self.ttl:
			return None
		with open(path, "r") as f:
			return json.load(f)

	def set(self, repo_url: str, head_sha: str, data: dict[str, Any]) -> None:
		key = self._make_key(repo_url, head_sha)
		tmp_path = self.cache_dir / f"{key}.tmp"
		final_path = self.cache_dir / f"{key}.json"
		with open(tmp_path, "w") as f:
			json.dump(data, f)
		os.rename(tmp_path, final_path)
