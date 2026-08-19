from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptProfile:
    prompt_id: str
    version: str
    content: str
    path: str


def _parse_prompt_file(
    root: Path,
    path: Path,
) -> PromptProfile:
    text = path.read_text(
        encoding="utf-8"
    )

    prompt_id = path.stem
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

            prompt_id = metadata.get(
                "id",
                prompt_id,
            )

            version = metadata.get(
                "version",
                version,
            )

    return PromptProfile(
        prompt_id=prompt_id,
        version=version,
        content=content.strip(),
        path=path.relative_to(root).as_posix(),
    )


def load_prompt_profile(
    root: Path,
    prompt_id: str,
) -> PromptProfile:
    path = (
        root
        / "10_Harness"
        / "prompts"
        / f"{prompt_id}.md"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Unknown prompt profile: "
            f"{prompt_id}"
        )

    return _parse_prompt_file(
        root,
        path,
    )


def compose_prompt_profiles(
    root: Path,
    prompt_ids: list[str],
) -> tuple[str, list[dict]]:
    profiles = [
        load_prompt_profile(
            root,
            prompt_id,
        )
        for prompt_id in prompt_ids
    ]

    instructions = "\n\n".join(
        profile.content
        for profile in profiles
    )

    manifest = [
        {
            "id": profile.prompt_id,
            "version": profile.version,
            "path": profile.path,
        }
        for profile in profiles
    ]

    return instructions, manifest


def resolve_prompt_ids(
    config: dict,
    workflow: dict,
    task_class: str,
) -> tuple[list[str], str | None]:
    """
    Resolve prompt profiles in priority/composition order:

        config base profiles
        -> task-class profiles
        -> workflow-specific profiles

    Duplicate profile IDs are removed while preserving order.
    """
    policy = config.get(
        "prompt_policy",
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
            "base_profiles",
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
            "prompt_profiles",
            [],
        )
    )

    return (
        resolved,
        policy.get("version"),
    )
