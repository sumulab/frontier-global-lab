from __future__ import annotations

import json
import re
import subprocess

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_TOP_LEVEL = {
    ".env.example",
    ".github",
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "10_Harness",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSE.md",
    "PUBLICATION_POLICY.md",
    "README.md",
    "SECURITY.md",
    "docs",
    "harness",
    "pyproject.toml",
    "scripts",
    "tests",
    "uv.lock",
    "workspace.json",
}

PROHIBITED_TOP_LEVEL = {
    "00_MASTER_PLAN.md",
    "01_Strategy",
    "02_Learning",
    "03_Energy_Research",
    "04_International_Outreach",
    "05_Projects",
    "06_Content_IP",
    "07_Reviews",
    "08_Databases",
    "09_Templates",
}

SECRET_PATTERNS = {
    "OpenAI-style key": re.compile(
        rb"sk-[A-Za-z0-9_-]{16,}"
    ),
    "GitHub token": re.compile(
        rb"gh[pousr]_[A-Za-z0-9]{20,}"
    ),
    "AWS access key": re.compile(
        rb"AKIA[0-9A-Z]{16}"
    ),
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?"
        rb"PRIVATE KEY-----"
    ),
}


def _publication_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    issues: list[str] = []
    files = _publication_files()

    for path in files:
        relative = _relative(path)
        top = relative.split("/", 1)[0]

        if top in PROHIBITED_TOP_LEVEL:
            issues.append(
                f"prohibited private path: {relative}"
            )
        elif top not in ALLOWED_TOP_LEVEL:
            issues.append(
                f"path is outside public allowlist: {relative}"
            )

        if path.name == ".env":
            issues.append(
                f"credential file is prohibited: {relative}"
            )

        if path.suffix.lower() in {
            ".sqlite",
            ".sqlite3",
            ".db",
        }:
            issues.append(
                f"database file is prohibited: {relative}"
            )

        if relative.startswith(
            "10_Harness/runtime/"
        ) and path.name != ".gitkeep":
            issues.append(
                f"runtime artifact is prohibited: {relative}"
            )

        if not path.is_file():
            continue

        data = path.read_bytes()

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                issues.append(
                    f"{label} signature found: {relative}"
                )

        local_home_marker = b"/" + b"Users/"
        if local_home_marker in data:
            issues.append(
                f"local absolute path found: {relative}"
            )

    for relative in (
        "10_Harness/temporal/canonical_claims.jsonl",
        "10_Harness/temporal/claim_relationships.jsonl",
    ):
        path = ROOT / relative
        if not path.is_file():
            issues.append(
                f"public empty ledger missing: {relative}"
            )
        elif path.read_text(
            encoding="utf-8"
        ).strip():
            issues.append(
                f"operational ledger data is prohibited: {relative}"
            )

    manifest_path = ROOT / "workspace.json"
    if manifest_path.is_file():
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        if manifest.get("visibility") != (
            "public-example"
        ):
            issues.append(
                "workspace.json must declare "
                "visibility=public-example"
            )

    if issues:
        print("Public boundary check failed:")
        for issue in sorted(set(issues)):
            print(f"- {issue}")
        return 1

    print(
        "Public boundary check passed: "
        f"{len(files)} publishable files reviewed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
