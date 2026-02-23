"""Tests for the file-based JSON cache."""

import json
import os
import time

from gitpulse.cache import Cache


class TestCacheKeyGeneration:
	def test_key_is_deterministic(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		key1 = cache._make_key("owner/repo", "abc123")
		key2 = cache._make_key("owner/repo", "abc123")
		assert key1 == key2

	def test_different_inputs_produce_different_keys(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		key1 = cache._make_key("owner/repo", "abc123")
		key2 = cache._make_key("owner/repo", "def456")
		key3 = cache._make_key("other/repo", "abc123")
		assert key1 != key2
		assert key1 != key3

	def test_key_is_valid_sha256_hex(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		key = cache._make_key("owner/repo", "abc123")
		assert len(key) == 64
		int(key, 16)  # raises if not valid hex


class TestCacheMiss:
	def test_get_returns_none_on_miss(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		assert cache.get("owner/repo", "abc123") is None


class TestCacheHit:
	def test_set_then_get_returns_data(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		data = {"commits": 42, "repo": "owner/repo"}
		cache.set("owner/repo", "abc123", data)
		result = cache.get("owner/repo", "abc123")
		assert result == data

	def test_different_keys_are_independent(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		cache.set("owner/repo", "sha1", {"val": 1})
		cache.set("owner/repo", "sha2", {"val": 2})
		assert cache.get("owner/repo", "sha1") == {"val": 1}
		assert cache.get("owner/repo", "sha2") == {"val": 2}


class TestCacheTTLExpiry:
	def test_expired_entry_returns_none(self, tmp_path):
		cache = Cache(cache_dir=tmp_path, ttl=60)
		data = {"commits": 42}
		cache.set("owner/repo", "abc123", data)
		# Set mtime to 120 seconds ago
		key = cache._make_key("owner/repo", "abc123")
		path = tmp_path / f"{key}.json"
		old_time = time.time() - 120
		os.utime(path, (old_time, old_time))
		assert cache.get("owner/repo", "abc123") is None

	def test_fresh_entry_returns_data(self, tmp_path):
		cache = Cache(cache_dir=tmp_path, ttl=3600)
		data = {"commits": 42}
		cache.set("owner/repo", "abc123", data)
		assert cache.get("owner/repo", "abc123") == data


class TestAtomicWrite:
	def test_final_file_is_valid_json(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		data = {"key": "value", "nested": {"a": 1}}
		cache.set("owner/repo", "abc123", data)
		key = cache._make_key("owner/repo", "abc123")
		path = tmp_path / f"{key}.json"
		with open(path) as f:
			loaded = json.load(f)
		assert loaded == data

	def test_no_tmp_file_remains_after_set(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		cache.set("owner/repo", "abc123", {"a": 1})
		tmp_files = list(tmp_path.glob("*.tmp"))
		assert tmp_files == []

	def test_json_file_exists_after_set(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		cache.set("owner/repo", "abc123", {"a": 1})
		json_files = list(tmp_path.glob("*.json"))
		assert len(json_files) == 1


class TestDirectoryAutoCreation:
	def test_creates_cache_dir_on_init(self, tmp_path):
		nested = tmp_path / "a" / "b" / "c"
		assert not nested.exists()
		Cache(cache_dir=nested)
		assert nested.is_dir()

	def test_works_with_existing_dir(self, tmp_path):
		cache = Cache(cache_dir=tmp_path)
		data = {"x": 1}
		cache.set("r", "s", data)
		assert cache.get("r", "s") == data
