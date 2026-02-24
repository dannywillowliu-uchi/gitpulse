import socket
import threading
import time
from collections.abc import Generator

import pytest

playwright = pytest.importorskip("playwright")
import uvicorn  # noqa: E402
from playwright.sync_api import Page  # noqa: E402


def _get_free_port() -> int:
	"""Find a random available TCP port."""
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.bind(("127.0.0.1", 0))
		return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
	"""Block until the given host:port accepts connections."""
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		try:
			with socket.create_connection((host, port), timeout=0.5):
				return
		except OSError:
			time.sleep(0.1)
	raise TimeoutError(f"Server on {host}:{port} not ready after {timeout}s")


@pytest.fixture(scope="session")
def base_url() -> Generator[str, None, None]:
	"""Start uvicorn in a background thread on a random port, yield the base URL."""
	host = "127.0.0.1"
	port = _get_free_port()

	config = uvicorn.Config(
		"gitpulse.app:app",
		host=host,
		port=port,
		log_level="warning",
	)
	server = uvicorn.Server(config)

	thread = threading.Thread(target=server.run, daemon=True)
	thread.start()

	_wait_for_port(host, port)

	yield f"http://{host}:{port}"

	server.should_exit = True
	thread.join(timeout=5)


@pytest.fixture
def live_page(page: Page, base_url: str) -> Page:
	"""Playwright page navigated to the running server's base URL."""
	page.goto(base_url)
	return page
