from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    retrieved_at: str


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str
    title: str
    publisher: str | None
    published_at: str | None
    retrieved_at: str
    text: str
    content_hash: str
    provider: str


class WebProvider(Protocol):
    """Provider-neutral contract for Frontier web evidence adapters."""

    def search(
        self,
        query: str,
        max_results: int = 5,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        """Discover candidate sources.

        Search results are NOT evidence.
        """
        ...

    def fetch(
        self,
        url: str,
    ) -> FetchedPage:
        """Fetch and normalize a source page.

        A fetched page may become evidence only after claim-level checking.
        """
        ...
