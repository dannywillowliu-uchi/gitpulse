import time
from collections import defaultdict


class SlidingWindowRateLimiter:
	"""In-memory sliding window rate limiter."""

	def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
		self.max_requests = max_requests
		self.window_seconds = window_seconds
		self._requests: dict[str, list[float]] = defaultdict(list)

	def is_allowed(self, client_ip: str) -> bool:
		now = time.monotonic()
		cutoff = now - self.window_seconds
		self._requests[client_ip] = [
			ts for ts in self._requests[client_ip] if ts > cutoff
		]
		if len(self._requests[client_ip]) >= self.max_requests:
			return False
		self._requests[client_ip].append(now)
		return True

	def reset(self) -> None:
		self._requests.clear()
