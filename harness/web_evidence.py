from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from harness.evidence_store import EvidenceStore
from harness.web_contract import FetchedPage, SearchResult, WebProvider


class WebEvidenceService:
    def __init__(
        self,
        *,
        provider: WebProvider,
        evidence_db: str | Path,
    ):
        self.provider = provider
        self.store = EvidenceStore(evidence_db)

    def search(
        self,
        query: str,
        max_results: int = 5,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        results = self.provider.search(
            query=query,
            max_results=max_results,
            domains=domains,
        )

        for result in results:
            self.store.upsert_source(
                url=result.url,
                title=result.title,
                retrieved_at=result.retrieved_at,
                provider=result.provider,
                status="discovered",
            )

        return results

    def fetch(
        self,
        url: str,
    ) -> FetchedPage:
        page = self.provider.fetch(url)

        self.store.upsert_source(
            url=page.url,
            title=page.title,
            publisher=page.publisher,
            published_at=page.published_at,
            retrieved_at=page.retrieved_at,
            provider=page.provider,
            content_hash=page.content_hash,
            status="fetched",
        )

        self.store.store_source_content(
            url=page.url,
            content=page.text,
            content_hash=page.content_hash,
            retrieved_at=page.retrieved_at,
        )

        return page
