from __future__ import annotations

import json

from pathlib import Path

import pytest

from harness.project_root import (
    PROJECT_ROOT_ENV,
    resolve_project_root,
)


def _workspace(root: Path) -> Path:
    harness_root = root / "10_Harness"
    harness_root.mkdir(parents=True)
    (harness_root / "config.json").write_text(
        json.dumps({"version": "0.5.0"}),
        encoding="utf-8",
    )
    return root


def test_explicit_project_root_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    explicit = _workspace(tmp_path / "explicit")
    configured = _workspace(
        tmp_path / "configured"
    )
    monkeypatch.setenv(
        PROJECT_ROOT_ENV,
        str(configured),
    )

    assert resolve_project_root(explicit) == explicit


def test_project_root_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    configured = _workspace(
        tmp_path / "configured"
    )
    monkeypatch.setenv(
        PROJECT_ROOT_ENV,
        str(configured),
    )

    assert resolve_project_root(
        cwd=tmp_path / "missing"
    ) == configured


def test_missing_project_root_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(
        PROJECT_ROOT_ENV,
        raising=False,
    )

    with pytest.raises(
        FileNotFoundError,
        match="10_Harness/config.json",
    ):
        resolve_project_root(
            tmp_path / "missing"
        )
