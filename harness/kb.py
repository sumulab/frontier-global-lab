from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_PARTS = {".git", ".venv", "__pycache__", "runtime"}

@dataclass
class SearchHit:
    path: str
    title: str
    snippet: str
    score: float


def _title_from_text(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ")


def _read_csv(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)


def _iter_docs(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.suffix.lower() not in {".md", ".csv", ".txt"}:
            continue
        try:
            if path.suffix.lower() == ".csv":
                text = _read_csv(path)
            else:
                text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield rel.as_posix(), _title_from_text(path, text), text, path.stat().st_mtime


def build_index(root: Path, db_path: Path) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS docs")
        conn.execute("DROP TABLE IF EXISTS docs_fts")
        conn.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, path TEXT UNIQUE, title TEXT, body TEXT, mtime REAL)")
        conn.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(title, body, content='docs', content_rowid='id')")
        count = 0
        for rel, title, body, mtime in _iter_docs(root):
            cur = conn.execute(
                "INSERT INTO docs(path, title, body, mtime) VALUES (?, ?, ?, ?)",
                (rel, title, body, mtime),
            )
            rowid = cur.lastrowid
            conn.execute("INSERT INTO docs_fts(rowid, title, body) VALUES (?, ?, ?)", (rowid, title, body))
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def _fts_query(query: str) -> str:
    terms = [t for t in re.split(r"\s+", query.strip()) if t]
    safe = []
    for term in terms:
        term = term.replace('"', '""')
        safe.append(f'"{term}"')
    return " OR ".join(safe) or '""'


def search(db_path: Path, query: str, limit: int = 8) -> list[SearchHit]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT d.path, d.title,
                   snippet(docs_fts, 1, '[', ']', ' … ', 18) AS snippet,
                   bm25(docs_fts) AS score
            FROM docs_fts
            JOIN docs d ON d.id = docs_fts.rowid
            WHERE docs_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (_fts_query(query), limit),
        ).fetchall()
        return [SearchHit(*row) for row in rows]
    finally:
        conn.close()
