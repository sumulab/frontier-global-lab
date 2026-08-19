from __future__ import annotations

import re
import sqlite3

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    actual: str
    requirement: str


@dataclass(frozen=True)
class SemanticWarning:
    name: str
    evidence_ids: list[str]
    detail: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    checks: list[QualityCheck]
    warnings: list[SemanticWarning] = field(
        default_factory=list
    )


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()

    if host.startswith("www."):
        host = host[4:]

    return host


def _is_generic_homepage(
    url: str,
) -> bool:
    parsed = urlparse(url)

    return (
        parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def _claim_tokens(
    text: str,
) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        if len(token) >= 3
    }


def _claim_similarity(
    left: str,
    right: str,
) -> float:
    a = _claim_tokens(left)
    b = _claim_tokens(right)

    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def _looks_non_standalone(
    claim: str,
) -> bool:
    text = claim.strip().lower()

    patterns = (
        r"^in the same\b",
        r"^the same\b",
        r"^same study\b",
        r"^same report\b",
        r"^same source\b",
        r"^as noted above\b",
        r"^as mentioned above\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def _looks_multi_proposition(
    claim: str,
) -> bool:
    """
    Conservative heuristic only.

    Long claims containing several independent
    conjunctions or clause separators are candidates
    for atomicity review.
    """
    text = claim.strip()

    if len(text) < 180:
        return False

    markers = (
        text.lower().count(" and ")
        + text.lower().count(" while ")
        + text.lower().count(" whereas ")
        + text.count(";")
    )

    return markers >= 2


_SECONDARY_NEWS_DOMAINS = {
    "guardian.ng",
    "reuters.com",
    "bloomberg.com",
    "bbc.com",
    "cnn.com",
    "cnbc.com",
    "forbes.com",
    "businessday.ng",
    "thisdaylive.com",
    "punchng.com",
    "esi-africa.com",
}


def _semantic_warnings(
    rows: list[sqlite3.Row],
) -> list[SemanticWarning]:
    warnings: list[SemanticWarning] = []

    # -------------------------------------------
    # 1. Generic homepage provenance
    # -------------------------------------------

    for row in rows:
        url = row["source_url"] or ""

        if (
            url
            and _is_generic_homepage(url)
        ):
            warnings.append(
                SemanticWarning(
                    name="generic_source_url",
                    evidence_ids=[
                        row["evidence_id"]
                    ],
                    detail=(
                        "Evidence uses an institution "
                        "homepage or domain root. Prefer "
                        "an article-, report-, dataset-, "
                        "or document-level URL when one "
                        "exists."
                    ),
                )
            )

    # -------------------------------------------
    # 2. Secondary-source upgrade
    # -------------------------------------------

    for row in rows:
        url = row["source_url"] or ""
        domain = _domain(url)

        if domain in _SECONDARY_NEWS_DOMAINS:
            warnings.append(
                SemanticWarning(
                    name="primary_source_upgrade",
                    evidence_ids=[
                        row["evidence_id"]
                    ],
                    detail=(
                        f"Source domain {domain} appears "
                        "to be a secondary/news source. "
                        "Check whether the underlying "
                        "original report, dataset, filing, "
                        "regulator, or company source can "
                        "replace or strengthen it."
                    ),
                )
            )

    # -------------------------------------------
    # 3. Standalone claim discipline
    # -------------------------------------------

    for row in rows:
        claim = row["claim_text"] or ""

        if _looks_non_standalone(claim):
            warnings.append(
                SemanticWarning(
                    name="non_standalone_claim",
                    evidence_ids=[
                        row["evidence_id"]
                    ],
                    detail=(
                        "Claim depends on surrounding "
                        "list context such as 'the same "
                        "study/report'. Rewrite it so the "
                        "claim remains understandable "
                        "when viewed independently."
                    ),
                )
            )

    # -------------------------------------------
    # 4. Atomicity heuristic
    # -------------------------------------------

    for row in rows:
        claim = row["claim_text"] or ""

        if _looks_multi_proposition(claim):
            warnings.append(
                SemanticWarning(
                    name="possible_multi_proposition_claim",
                    evidence_ids=[
                        row["evidence_id"]
                    ],
                    detail=(
                        "Claim may contain multiple "
                        "independently assessable facts. "
                        "Consider splitting it into "
                        "atomic claims."
                    ),
                )
            )

    # -------------------------------------------
    # 5. Near-duplicate claims
    # -------------------------------------------

    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            left_claim = (
                left["claim_text"]
                or ""
            )

            right_claim = (
                right["claim_text"]
                or ""
            )

            similarity = _claim_similarity(
                left_claim,
                right_claim,
            )

            if similarity >= 0.78:
                warnings.append(
                    SemanticWarning(
                        name="near_duplicate_claim",
                        evidence_ids=[
                            left["evidence_id"],
                            right["evidence_id"],
                        ],
                        detail=(
                            "Claims have high token "
                            f"similarity ({similarity:.0%}). "
                            "Check whether they represent "
                            "the same conceptual fact."
                        ),
                    )
                )

    return warnings


def evaluate_country_scan(
    evidence_db: str | Path,
) -> QualityReport:
    db = Path(evidence_db)

    if not db.exists():
        raise FileNotFoundError(
            f"Evidence DB not found: {db}"
        )

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            e.evidence_id,
            e.source_url,
            c.text AS claim_text,
            c.topic
        FROM evidence e
        JOIN claims c
          ON c.claim_id = e.claim_id
        WHERE e.status = 'supported'
        """
    ).fetchall()

    conn.close()

    evidence_count = len(rows)

    urls = {
        row["source_url"]
        for row in rows
        if row["source_url"]
    }

    domains = [
        _domain(row["source_url"])
        for row in rows
        if row["source_url"]
    ]

    distinct_domains = set(domains)

    topics = {
        row["topic"].strip()
        for row in rows
        if row["topic"]
        and row["topic"].strip()
    }

    domain_counts = Counter(domains)

    max_domain_share = (
        max(domain_counts.values())
        / evidence_count
        if evidence_count
        else 0.0
    )

    checks = [
        QualityCheck(
            name="supported_evidence",
            passed=evidence_count >= 6,
            actual=str(evidence_count),
            requirement=">= 6",
        ),
        QualityCheck(
            name="unique_source_urls",
            passed=len(urls) >= 5,
            actual=str(len(urls)),
            requirement=">= 5",
        ),
        QualityCheck(
            name="independent_domains",
            passed=len(distinct_domains) >= 4,
            actual=str(len(distinct_domains)),
            requirement=">= 4",
        ),
        QualityCheck(
            name="research_topics",
            passed=len(topics) >= 4,
            actual=str(len(topics)),
            requirement=">= 4",
        ),
        QualityCheck(
            name="source_concentration",
            passed=max_domain_share <= 0.60,
            actual=f"{max_domain_share:.0%}",
            requirement="<= 60%",
        ),
    ]

    warnings = _semantic_warnings(
        rows
    )

    return QualityReport(
        passed=all(
            check.passed
            for check in checks
        ),
        checks=checks,
        warnings=warnings,
    )
