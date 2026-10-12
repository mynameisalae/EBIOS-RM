"""Environment-driven settings and the single model factory (conception §3.2, §13.1).

OpenRouter is the sole model provider in every environment; only MODEL_ID changes
between test and production. This is the only place in the codebase that knows a
model name — no agent, workshop, service, or toolkit references a provider or
model directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal, dependency-free .env loader (KEY=VALUE lines).

    Values already present in the environment win, so an explicit export always
    overrides the file. Missing file is a no-op.
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    # utf-8-sig: strips a leading BOM if present (e.g. a .env saved by Notepad on
    # Windows) and behaves exactly like utf-8 otherwise. Without this, a BOM'd
    # first line becomes "﻿KEY=value" and the resulting environment variable
    # is silently named wrong, with os.environ.get("KEY") always returning None.
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

# Dev/test default: the free NVIDIA Nemotron model on OpenRouter, chosen for this
# project's dev testing. Always an explicit, pinned model id — never a floating
# router alias like `openrouter/free`, whose selection changes run to run and
# would break the reproducibility of the fiches de test (§3.2, §13.1).
# Empirically verified (2026-07-22) as the free OpenRouter model that reliably
# returns our exact pydantic schemas: native structured output, respects field
# names, 262k context. Larger free "reasoning" models leak chain-of-thought and
# fail to parse; gpt-oss returns JSON with the wrong field names. Production swaps
# this for a pinned paid model via MODEL_ID (e.g. anthropic/claude-sonnet-5, §3.2).
DEFAULT_DEV_MODEL_ID = "google/gemma-4-26b-a4b-it:free"

# Production example (pinned): "anthropic/claude-sonnet-5", still via OpenRouter.


@dataclass(frozen=True)
class Settings:
    model_id: str
    openrouter_api_key: str | None
    reference_db_path: str
    mission_db_path: str
    attack_db_path: str
    max_output_tokens: int


def load_settings() -> Settings:
    load_dotenv()  # pick up a local .env if present (no-op in Docker, where vars are injected)
    return Settings(
        model_id=os.environ.get("MODEL_ID", DEFAULT_DEV_MODEL_ID),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        reference_db_path=os.environ.get("REFERENCE_DB_PATH", "data/reference/reference.db"),
        mission_db_path=os.environ.get("MISSION_DB_PATH", "data/mission/mission.db"),
        attack_db_path=os.environ.get("ATTACK_DB_PATH", "mitre_attack_complete.db"),
        max_output_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS", "8000")),
    )


def fix_openrouter_errors(response):
    """Intercept OpenRouter fake 200 OK responses that contain 5xx errors."""
    if response.status_code == 200:
        response.read()
        try:
            data = response.json()
            if 'error' in data and isinstance(data['error'], dict):
                code = data['error'].get('code')
                if code in [502, 503, 504, 522]:
                    response.status_code = code
        except Exception:
            pass

def get_model():
    """Return the single Agno model instance — the only code that names a model (conception §3.2).

    Imported lazily so the deterministic core (Fact model, validation, priority
    matrix, mission context) can be used and tested without Agno installed.

    Under MANUAL_LLM there is no model: run_structured answers from files and never
    builds an agent. Every runner resolves its model in __init__, so without this
    the manual mode — the one meant to work with no API access at all — could not
    start unless the provider stack imported cleanly.
    """
    if os.environ.get("MANUAL_LLM"):
        return None

    from agno.models.openrouter import OpenRouter  # noqa: PLC0415 — lazy on purpose
    import httpx

    settings = load_settings()
    # api_key defaults to OPENROUTER_API_KEY from the environment when omitted.
    # max_tokens raised well above the provider default so structured JSON outputs
    # (asset lists, batched extractions) are never truncated mid-object.
    # We use a custom http_client to translate OpenRouter's 200 OK + JSON error body 
    # into a real HTTP error so the OpenAI SDK can properly retry it automatically.
    client = httpx.Client(event_hooks={'response': [fix_openrouter_errors]}, timeout=60.0)
    
    return OpenRouter(
        id=settings.model_id,
        api_key=settings.openrouter_api_key,
        max_tokens=settings.max_output_tokens,
        http_client=client,
    )
