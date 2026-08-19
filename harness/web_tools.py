from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

from agents import function_tool

from harness.evidence import (
    Claim,
    Evidence,
    EvidenceStatus,
)
from harness.tavily_provider import TavilyWebProvider
from harness.web_evidence import WebEvidenceService


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_web_tools(
    evidence_db: str | Path,
    *,
    runtime_policy: dict | None = None,
):
    service = WebEvidenceService(
        provider=TavilyWebProvider(),
        evidence_db=evidence_db,
    )

    policy = runtime_policy or {}

    limits = {
        "searches": int(
            policy.get("max_web_searches", 8)
        ),
        "fetches": int(
            policy.get("max_fetches", 8)
        ),
        "new_evidence": int(
            policy.get("max_new_evidence", 8)
        ),
    }

    usage = {
        "searches": 0,
        "fetches": 0,
        "new_evidence": 0,
    }

    def budget_exhausted(
        resource: str,
    ) -> str:
        return json.dumps(
            {
                "status": "BUDGET_EXHAUSTED",
                "resource": resource,
                "used": usage[resource],
                "limit": limits[resource],
                "instruction": (
                    "Do not retry this exhausted resource. "
                    "Continue with existing evidence and finish the task."
                ),
            },
            ensure_ascii=False,
        )

    @function_tool
    def search_web(
        query: str,
        max_results: int = 5,
        domains_csv: str = "",
    ) -> str:
        """Search the public web for candidate sources.

        Search results are discovery only and MUST NOT be treated
        as verified evidence.

        Args:
            query: Search query.
            max_results: Maximum number of results.
            domains_csv: Optional comma-separated domain allowlist.
        """
        if usage["searches"] >= limits["searches"]:
            return budget_exhausted("searches")

        usage["searches"] += 1

        domains = [
            item.strip()
            for item in domains_csv.split(",")
            if item.strip()
        ]

        results = service.search(
            query=query,
            max_results=max_results,
            domains=domains or None,
        )

        payload = [
            {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "provider": item.provider,
                "retrieved_at": item.retrieved_at,
                "evidence_status": "DISCOVERED_NOT_EVIDENCE",
            }
            for item in results
        ]

        return json.dumps(
            payload,
            ensure_ascii=False,
        )

    @function_tool
    def fetch_web_page(
        url: str,
        max_chars: int = 12000,
    ) -> str:
        """Fetch a discovered public webpage and persist its full text.

        Fetching a page does NOT by itself verify any claim.

        Args:
            url: Public webpage URL.
            max_chars: Maximum page characters returned to the model.
                The complete page is still stored in the evidence database.
        """
        if usage["fetches"] >= limits["fetches"]:
            return budget_exhausted("fetches")

        usage["fetches"] += 1

        page = service.fetch(url)

        payload = {
            "url": page.url,
            "final_url": page.final_url,
            "title": page.title,
            "publisher": page.publisher,
            "published_at": page.published_at,
            "retrieved_at": page.retrieved_at,
            "content_hash": page.content_hash,
            "content_length": len(page.text),
            "content": page.text[:max_chars],
            "truncated": len(page.text) > max_chars,
            "evidence_status": "FETCHED_NOT_VERIFIED",
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
        )

    @function_tool
    def record_claim_evidence(
        claim_text: str,
        topic: str,
        source_url: str,
        excerpt: str,
        reasoning: str,
        assessment: Literal[
            "supported",
            "contradicted",
            "insufficient",
        ],
        importance: Literal[
            "low",
            "normal",
            "high",
        ] = "normal",
    ) -> str:
        """Record claim-level evidence from an already fetched webpage.

        The source MUST already have been fetched.
        The excerpt MUST exist in the stored fetched page.
        This records machine-assessed evidence only; it does not perform
        human verification or canonical promotion.
        """
        if usage["new_evidence"] >= limits["new_evidence"]:
            return budget_exhausted("new_evidence")

        if not service.store.is_fetched_source(source_url):
            raise ValueError(
                "Evidence rejected: source has not been fetched."
            )

        source_content = service.store.get_source_content(
            source_url
        )

        if not source_content:
            raise ValueError(
                "Evidence rejected: fetched source content is missing."
            )

        clean_excerpt = excerpt.strip()

        if len(clean_excerpt) < 20:
            raise ValueError(
                "Evidence rejected: excerpt is too short."
            )

        normalized_source = _normalize_text(source_content)
        normalized_excerpt = _normalize_text(clean_excerpt)

        if normalized_excerpt not in normalized_source:
            raise ValueError(
                "Evidence rejected: excerpt does not exist "
                "in stored fetched content."
            )

        source = service.store.get_source(source_url) or {}

        source_context = service.store.derive_source_context(
            url=source_url,
            excerpt=clean_excerpt,
        )

        claim_id = f"C-{uuid4().hex[:12]}"
        evidence_id = f"E-{uuid4().hex[:12]}"

        claim = Claim(
            claim_id=claim_id,
            text=claim_text.strip(),
            topic=topic.strip(),
            importance=importance,
        )

        evidence = Evidence(
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_url=source_url,
            status=EvidenceStatus(assessment),
            excerpt=clean_excerpt,
            reasoning=reasoning.strip(),
            source_title=source.get("title"),
            publisher=source.get("publisher"),
            published_at=source.get("published_at"),
            retrieved_at=source.get("retrieved_at"),
            section_heading=source_context.get(
                "section_heading"
            ),
            context_excerpt=source_context.get(
                "context_excerpt"
            ),
        )

        service.store.add_claim(claim)
        service.store.add_evidence(evidence)

        usage["new_evidence"] += 1

        return json.dumps(
            {
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "assessment": assessment,
                "source_url": source_url,
                "human_verified": False,
                "canonical_ready": False,
            },
            ensure_ascii=False,
        )

    return [
        search_web,
        fetch_web_page,
        record_claim_evidence,
    ]
