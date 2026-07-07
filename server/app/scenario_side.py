"""Helpers for player/opponent sides and dual negotiation goals."""

from __future__ import annotations

from app.models.db import CharacterTemplate, ScenarioTemplate

SIDE_OPPONENT = "opponent"
SIDE_PLAYER_ALLY = "player_ally"
VALID_SIDES = {SIDE_OPPONENT, SIDE_PLAYER_ALLY}

DEFAULT_OPPONENT_GOAL_SUPPLY_CHAIN = (
    "Keep unit price at 88 RMB or above, secure favorable payment terms, "
    "and lock in an annual purchase framework agreement"
)


def normalize_side(side: str | None) -> str:
    if side in VALID_SIDES:
        return side
    return SIDE_OPPONENT


def is_player_ally(character: CharacterTemplate) -> bool:
    return normalize_side(character.side) == SIDE_PLAYER_ALLY


def resolve_player_side_goal(scenario: ScenarioTemplate) -> str:
    if scenario.player_side_goal:
        return scenario.player_side_goal
    return scenario.business_goal or ""


def resolve_opponent_side_goal(scenario: ScenarioTemplate) -> str:
    return scenario.opponent_side_goal or ""


def sync_legacy_business_goal(scenario: ScenarioTemplate) -> None:
    """Keep legacy column aligned for older clients."""
    player = resolve_player_side_goal(scenario)
    if player:
        scenario.business_goal = player


def goal_seed_text(character: CharacterTemplate, scenario: ScenarioTemplate) -> str:
    player_goal = resolve_player_side_goal(scenario)
    opponent_goal = resolve_opponent_side_goal(scenario)
    if is_player_ally(character):
        lines = [f"Our side's goal: {player_goal or '(not set)'}"]
        if opponent_goal:
            lines.append(f"Opponent goal to guard against: {opponent_goal}")
        return ". ".join(lines)
    lines = [f"Our side's goal: {opponent_goal or '(not set)'}"]
    if player_goal:
        lines.append(f"Buyer lead's goal: {player_goal}")
    return ". ".join(lines)


def initial_plan_goal_block(character: CharacterTemplate, scenario: ScenarioTemplate) -> str:
    player_goal = resolve_player_side_goal(scenario)
    opponent_goal = resolve_opponent_side_goal(scenario)
    if is_player_ally(character):
        block = f"Our side's goal: {player_goal or '(not set)'}"
        if opponent_goal:
            block += f"\nOpponent goal to guard against: {opponent_goal}"
        block += "\nYou and the user are on the same side; coordinate to advance your shared goal."
        return block
    block = f"Our side's goal: {opponent_goal or '(not set)'}"
    if player_goal:
        block += f"\nBuyer lead's goal: {player_goal}"
    block += "\nThe user is the buyer lead; your position is opposite theirs."
    return block


def user_speaker_label(character: CharacterTemplate) -> str:
    if is_player_ally(character):
        return "Our lead (user) just said"
    return "Buyer lead (user) just said"
