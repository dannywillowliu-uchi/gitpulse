"""GitHub REST API client.

Async httpx wrapper for GitHub's statistics and repository endpoints.
Handles 202 retry pattern (GitHub returns 202 while computing stats),
rate limit detection, and authentication via GITHUB_TOKEN env var.
"""
