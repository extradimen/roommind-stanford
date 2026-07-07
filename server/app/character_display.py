"""Compose and parse character display names from name + job title."""

from __future__ import annotations

import re


def compose_display_name(character_name: str, job_title: str) -> str:
    name = (character_name or "").strip()
    title = (job_title or "").strip()
    if name and title:
        return f"{name} ({title})"
    return name or title or "NPC"


def split_display_name(display_name: str) -> tuple[str, str]:
    text = (display_name or "").strip()
    if not text:
        return "", ""

    # English: "Mr. Wang (Supplier CEO)"
    en = re.match(r"^(.+?)\s*\((.+)\)\s*$", text)
    if en:
        return en.group(1).strip(), en.group(2).strip()

    # Chinese legacy: "王总（供应商 CEO）"
    zh = re.match(r"^(.+?)（(.+)）\s*$", text)
    if zh:
        return zh.group(1).strip(), zh.group(2).strip()

    return text, ""


def normalize_character_fields(
    *,
    character_name: str | None,
    job_title: str | None,
    display_name: str | None,
) -> tuple[str, str, str]:
    name = (character_name or "").strip()
    title = (job_title or "").strip()
    legacy = (display_name or "").strip()

    if not name and not title and legacy:
        name, title = split_display_name(legacy)

    composed = compose_display_name(name, title)
    return name, title, composed
