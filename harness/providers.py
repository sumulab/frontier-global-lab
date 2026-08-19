from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx2
from openai import AsyncOpenAI
from agents import (
    OpenAIChatCompletionsModel,
    OpenAIResponsesModel,
    set_tracing_disabled,
)


@dataclass(frozen=True)
class ProviderRuntime:
    task_class: str
    provider: str
    model_name: str
    transport: str
    model: Any


def _build_client(
    provider: str,
    provider_config: dict,
) -> AsyncOpenAI:
    base_url = os.getenv(
        f"{provider.upper()}_BASE_URL",
        provider_config.get("base_url"),
    )

    if not base_url:
        raise RuntimeError(
            f"No base_url configured for provider: {provider}"
        )

    if provider == "ollama":
        api_key = os.getenv(
            "OLLAMA_API_KEY",
            "ollama",
        )

        # Local Ollama must bypass shell/system proxy settings.
        http_client = httpx2.AsyncClient(
            trust_env=False,
            timeout=120.0,
        )

        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
            max_retries=0,
        )

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")

        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set."
            )

        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set."
            )

        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    raise RuntimeError(
        f"Provider adapter not implemented: {provider}"
    )


def resolve_task_runtime(
    config: dict,
    task_class: str | None = None,
) -> ProviderRuntime:
    task_class = os.getenv(
        "LAB_TASK_CLASS",
        task_class or "local_light",
    )

    task_classes = config.get(
        "task_classes",
        {},
    )

    if task_class not in task_classes:
        raise RuntimeError(
            f"Unknown task_class={task_class!r}. "
            f"Available: {', '.join(task_classes)}"
        )

    route = task_classes[task_class]

    provider = os.getenv(
        "LAB_PROVIDER",
        route["provider"],
    )

    model_name = os.getenv(
        "LAB_MODEL",
        route["model"],
    )

    transport = os.getenv(
        "LAB_TRANSPORT",
        route.get(
            "transport",
            "responses",
        ),
    )

    providers = config.get(
        "providers",
        {},
    )

    if provider not in providers:
        raise RuntimeError(
            f"Unknown provider={provider!r}. "
            f"Available: {', '.join(providers)}"
        )

    client = _build_client(
        provider,
        providers[provider],
    )

    set_tracing_disabled(True)

    if transport == "responses":
        model = OpenAIResponsesModel(
            model=model_name,
            openai_client=client,
        )

    elif transport == "chat_completions":
        model = OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=client,
        )

    else:
        raise RuntimeError(
            f"Unsupported transport={transport!r}"
        )

    return ProviderRuntime(
        task_class=task_class,
        provider=provider,
        model_name=model_name,
        transport=transport,
        model=model,
    )
