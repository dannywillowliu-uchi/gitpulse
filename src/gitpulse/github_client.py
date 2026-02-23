"""GitHub REST API client.

Async httpx wrapper for GitHub's statistics and repository endpoints.
Handles 202 retry pattern (GitHub returns 202 while computing stats),
rate limit detection, and authentication via GITHUB_TOKEN env var.
"""

import asyncio
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.github.com"


class GitHubClient:
	"""Async GitHub REST API client with retry and rate limit handling."""

	def __init__(self, token: str | None = None) -> None:
		self._token = token or os.environ.get("GITHUB_TOKEN")
		headers: dict[str, str] = {
			"Accept": "application/vnd.github.v3+json",
		}
		if self._token:
			headers["Authorization"] = f"Bearer {self._token}"
		self._client = httpx.AsyncClient(
			base_url=BASE_URL,
			headers=headers,
			timeout=30.0,
		)

	async def close(self) -> None:
		await self._client.aclose()

	async def __aenter__(self) -> "GitHubClient":
		return self

	async def __aexit__(self, *args: object) -> None:
		await self.close()

	async def _check_rate_limit(self, response: httpx.Response) -> None:
		remaining = response.headers.get("X-RateLimit-Remaining")
		if remaining is None:
			return
		remaining_int = int(remaining)
		if remaining_int < 10:
			logger.warning("GitHub rate limit low: %d remaining", remaining_int)
		if remaining_int == 0:
			reset_ts = int(response.headers.get("X-RateLimit-Reset", "0"))
			sleep_time = max(reset_ts - time.time(), 0)
			logger.warning("Rate limit exhausted, sleeping %.1f seconds", sleep_time)
			await asyncio.sleep(sleep_time)

	async def fetch_with_retry(self, path: str) -> list | dict:
		"""Fetch a GitHub API endpoint with 202 retry pattern.

		GitHub stats endpoints return 202 while computing data.
		Retries up to 5 times with exponential backoff.
		"""
		for attempt in range(5):
			response = await self._client.get(path)
			await self._check_rate_limit(response)
			if response.status_code == 200:
				return response.json()
			if response.status_code == 202:
				await asyncio.sleep(2**attempt)
				continue
			if response.status_code == 404:
				raise httpx.HTTPStatusError(
					"Not Found",
					request=response.request,
					response=response,
				)
			response.raise_for_status()
		raise TimeoutError(f"GitHub still computing stats after 5 retries: {path}")

	async def get_repo(self, owner: str, repo: str) -> dict:
		"""Get repository metadata."""
		response = await self._client.get(f"/repos/{owner}/{repo}")
		await self._check_rate_limit(response)
		if response.status_code == 404:
			raise httpx.HTTPStatusError(
				"Not Found",
				request=response.request,
				response=response,
			)
		response.raise_for_status()
		return response.json()

	async def get_commit_activity(self, owner: str, repo: str) -> list:
		"""Get weekly commit counts for the last 52 weeks."""
		return await self.fetch_with_retry(f"/repos/{owner}/{repo}/stats/commit_activity")

	async def get_code_frequency(self, owner: str, repo: str) -> list:
		"""Get weekly additions/deletions."""
		return await self.fetch_with_retry(f"/repos/{owner}/{repo}/stats/code_frequency")

	async def get_contributors(self, owner: str, repo: str) -> list:
		"""Get per-contributor weekly commit data."""
		return await self.fetch_with_retry(f"/repos/{owner}/{repo}/stats/contributors")

	async def get_punch_card(self, owner: str, repo: str) -> list:
		"""Get day x hour commit counts."""
		return await self.fetch_with_retry(f"/repos/{owner}/{repo}/stats/punch_card")

	async def get_open_pulls(self, owner: str, repo: str) -> list:
		"""Get open pull requests."""
		response = await self._client.get(f"/repos/{owner}/{repo}/pulls?state=open")
		await self._check_rate_limit(response)
		if response.status_code == 404:
			raise httpx.HTTPStatusError(
				"Not Found",
				request=response.request,
				response=response,
			)
		response.raise_for_status()
		return response.json()

	async def get_languages(self, owner: str, repo: str) -> dict:
		"""Get language byte counts."""
		response = await self._client.get(f"/repos/{owner}/{repo}/languages")
		await self._check_rate_limit(response)
		if response.status_code == 404:
			raise httpx.HTTPStatusError(
				"Not Found",
				request=response.request,
				response=response,
			)
		response.raise_for_status()
		return response.json()
