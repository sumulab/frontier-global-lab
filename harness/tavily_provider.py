from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from tavily import TavilyClient

from harness.web_contract import (
    FetchedPage,
    SearchResult,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publisher_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()

    if host.startswith("www."):
        host = host[4:]

    return host


class TavilyWebProvider:
    provider_name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
    ):
        key = api_key or os.getenv("TAVILY_API_KEY")

        if not key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set."
            )

        self.client = TavilyClient(
            api_key=key,
        )

    def search(
        self,
        query: str,
        max_results: int = 5,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        kwargs = {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }

        if domains:
            kwargs["include_domains"] = domains

        response = self.client.search(**kwargs)

        retrieved_at = _utc_now()
        results: list[SearchResult] = []

        for item in response.get("results", []):
            url = item.get("url")

            if not url:
                continue

            results.append(
                SearchResult(
                    title=item.get("title") or url,
                    url=url,
                    snippet=item.get("content") or "",
                    provider=self.provider_name,
                    retrieved_at=retrieved_at,
                )
            )

        return results

    def fetch(
        self,
        url: str,
    ) -> FetchedPage:
        response = self.client.extract(
            url,
            extract_depth="basic",
            format="markdown",
        )

        results = response.get("results", [])

        if not results:
            failures = response.get(
                "failed_results",
                [],
            )

            raise RuntimeError(
                f"Tavily extract failed for {url}: "
                f"{failures}"
            )

        item = results[0]

        final_url = item.get("url") or url
        text = item.get("raw_content") or ""

        if not text.strip():
            raise RuntimeError(
                f"Tavily returned empty content for {url}"
            )

        content_hash = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

        return FetchedPage(
            url=url,
            final_url=final_url,
            title=item.get("title") or final_url,
            publisher=_publisher_from_url(final_url),
            published_at=None,
            retrieved_at=_utc_now(),
            text=text,
            content_hash=content_hash,
            provider=self.provider_name,
        )
