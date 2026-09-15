"""Generic participant relationship and goal helpers."""

from __future__ import annotations

from app.models.db import CharacterTemplate, ScenarioTemplate

SIDE_OPPONENT = "opponent"
SIDE_PLAYER_ALLY = "player_ally"
VALID_SIDES = {SIDE_OPPONENT, SIDE_PLAYER_ALLY}

def normalize_side(side: str | None) -> str:
    if side in VALID_SIDES:
        return side
    return SIDE_OPPONENT


def is_player_ally(character: CharacterTemplate) -> bool:
    return character.relationship_to_player in {"ally", "advisor", "teammate"} or normalize_side(character.side) == SIDE_PLAYER_ALLY


def resolve_player_side_goal(scenario: ScenarioTemplate) -> str:
    return str((scenario.task_config or {}).get("player_objective") or scenario.player_side_goal or scenario.business_goal or "")


def resolve_opponent_side_goal(scenario: ScenarioTemplate) -> str:
    return str((scenario.task_config or {}).get("counterpart_objective") or scenario.opponent_side_goal or "")


def sync_legacy_business_goal(scenario: ScenarioTemplate) -> None:
    """Keep legacy column aligned for older clients."""
    player = resolve_player_side_goal(scenario)
    if player:
        scenario.business_goal = player


def goal_seed_text(character: CharacterTemplate, scenario: ScenarioTemplate) -> str:
    player_goal = resolve_player_side_goal(scenario)
    opponent_goal = resolve_opponent_side_goal(scenario)
    own_goal = str((character.private_state or {}).get("goal") or (player_goal if is_player_ally(character) else opponent_goal) or "(not set)")
    lines = [f"My task goal: {own_goal}", f"My relationship to the player: {character.relationship_to_player}"]
    if player_goal:
        lines.append(f"Player objective: {player_goal}")
    return ". ".join(lines)


def initial_plan_goal_block(character: CharacterTemplate, scenario: ScenarioTemplate) -> str:
    player_goal = resolve_player_side_goal(scenario)
    opponent_goal = resolve_opponent_side_goal(scenario)
    if is_player_ally(character):
        block = f"Your task goal: {(character.private_state or {}).get('goal') or player_goal or '(not set)'}"
        if opponent_goal:
            block += f"\nOther participant objective: {opponent_goal}"
        block += "\nCoordinate with the player according to your configured relationship."
        return block
    block = f"Your task goal: {(character.private_state or {}).get('goal') or opponent_goal or '(not set)'}"
    if player_goal:
        block += f"\nPlayer objective: {player_goal}"
    block += f"\nYour configured relationship to the player is: {character.relationship_to_player}."
    return block


def user_speaker_label(character: CharacterTemplate) -> str:
    return "The player just said"
