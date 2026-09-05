"""Atomically align platform and active DB model for a controlled experiment."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.platform_config import load_platform_json_raw, write_platform_json


async def _update_database(provider: str, model: str) -> int:
    # Import after platform.json is updated so the runtime resolves the same DB
    # and provider settings the API will use.
    from app.database import async_session_factory
    from app.models.db import LLMConfig

    async with async_session_factory() as db:
        rows = list(
            (await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)))).scalars()
        )
        for row in rows:
            row.provider = provider
            row.model = model
        await db.commit()
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ollama", "siliconflow"], required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    raw = load_platform_json_raw()
    raw.setdefault("llm", {})["provider"] = args.provider
    provider_section = "ollama" if args.provider == "ollama" else "siliconflow"
    raw.setdefault(provider_section, {})["modelId"] = args.model
    write_platform_json(raw)
    updated = asyncio.run(_update_database(args.provider, args.model))
    if updated < 1:
        raise RuntimeError("No active llm_configs row was updated")
    print(f"provider={args.provider} model={args.model} active_rows={updated}")


if __name__ == "__main__":
    main()
