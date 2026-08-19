from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillProfile:
    skill_id: str
    version: str
    content: str
    path: str


def _parse_skill_file(
    root: Path,
    path: Path,
) -> SkillProfile:
    text = path.read_text(
        encoding="utf-8"
    )

    skill_id = path.stem
    version = "unversioned"
    content = text

    if text.startswith("---\n"):
        end = text.find(
            "\n---\n",
            4,
        )

        if end != -1:
            header = text[4:end]
            content = text[end + 5:]

            metadata = {}

            for line in header.splitlines():
                if ":" not in line:
                    continue

                key, value = line.split(
                    ":",
                    1,
                )

                metadata[
                    key.strip()
                ] = value.strip()

            skill_id = metadata.get(
                "id",
                skill_id,
            )

            version = metadata.get(
                "version",
                version,
            )

    return SkillProfile(
        skill_id=skill_id,
        version=version,
        content=content.strip(),
        path=path.relative_to(root).as_posix(),
    )


def load_skill_profile(
    root: Path,
    skill_id: str,
) -> SkillProfile:
    path = (
        root
        / "10_Harness"
        / "skills"
        / f"{skill_id}.md"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Unknown skill profile: {skill_id}"
        )

    return _parse_skill_file(
        root,
        path,
    )


def resolve_skill_ids(
    config: dict,
    workflow: dict,
    task_class: str,
) -> tuple[list[str], str | None]:
    policy = config.get(
        "skill_policy",
        {},
    )

    resolved: list[str] = []

    def extend(
        items: list[str] | None,
    ) -> None:
        for item in items or []:
            if item not in resolved:
                resolved.append(item)

    extend(
        policy.get(
            "base_skills",
            [],
        )
    )

    extend(
        policy.get(
            "task_classes",
            {},
        ).get(
            task_class,
            [],
        )
    )

    extend(
        workflow.get(
            "skill_profiles",
            [],
        )
    )

    return (
        resolved,
        policy.get("version"),
    )


def compose_skill_profiles(
    root: Path,
    skill_ids: list[str],
) -> tuple[str, list[dict]]:
    profiles = [
        load_skill_profile(
            root,
            skill_id,
        )
        for skill_id in skill_ids
    ]

    instructions = "\n\n".join(
        profile.content
        for profile in profiles
    )

    manifest = [
        {
            "id": profile.skill_id,
            "version": profile.version,
            "path": profile.path,
        }
        for profile in profiles
    ]

    return instructions, manifest
