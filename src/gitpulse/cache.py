"""File-based JSON cache.

Cache keyed by SHA256(repo_url + HEAD_sha), stored in ~/.cache/gitpulse/.
1-hour TTL. Atomic writes via temp file + rename.
"""
