# G4.1 Floor and Speech-Act Ownership Prequalification

## Research status

G4.1 is a local exploratory candidate derived from the failed G4.0
qualification. It must not be promoted or described as more realistic until a
new frozen matched experiment and complete paired reading are finished.

## Changes from G4.0

1. **Player-floor handoff.** When an NPC directly asks the player/candidate a
   question, the orchestrator stops selecting additional NPC speakers in that
   turn. Explicit validated targets take precedence over text heuristics.
2. **Speech-act consistency.** If private decision reasoning says to ask or
   prompt the player, a public first-person answer is rejected unless it is
   visibly phrased as a question or request.
3. **Fallback parity.** Configured NPC replies and deterministic AI-player
   recovery lines now pass through the same near-duplicate guard as ordinary
   model output. Exhausted player recovery variants cause a truthful bounded
   close instead of another repetition.
4. **Observability.** Batch traces retain all `dialogue.*`, `task_state.*`, and
   `public_ledger.*` events. Exports count player-floor handoffs and speech-act
   mismatch rejections.
5. **Frozen integrity probe.** G4.1 recomputes whether another NPC spoke in the
   same turn after a player-directed question.

The Stanford-style core is unchanged: each RoomMind role still has independent
memory, plan, perception, retrieval, reflection and action. The new mechanism
governs only public turn ownership.

## Local prequalification gates

1. Existing speech-safety, public-ledger, research-protocol and LLM-resilience
   suites pass.
2. A decision to prompt a candidate cannot publish a first-person candidate
   answer.
3. An NPC-to-NPC question does not incorrectly hand the floor to the player.
4. A player-directed question prevents later NPC speech in the same turn.
5. Exhausted deterministic fallback variants end rather than repeat.
6. Compile and whitespace checks pass.

## Next frozen experiment

After local gates pass, run the same four matched scenarios with the same fixed
provider/model, seed policy, concurrency, and turn limits used for G4.0. Keep
dialogue generation, independent AI evaluation and external human review as
separate stages. External review remains disabled during qualification.

## Local result (2026-09-04)

All four pure-Python regression suites, `compileall`, and `git diff --check`
passed. The PostgreSQL-backed `smoke_modes.py` was not counted as a pass: this
Mac checkout has no local `.env` or reachable local test database. No remote
service was used to conceal that missing integration environment. Frozen G4.0
artifacts were also reprocessed with the new diagnostic: it found 13 same-turn
player-floor violations in the RoomMind interview and one in incident command,
including the manually identified Engineering Director substitution. This is
retrospective detector validation, not evidence that G4.1 generation is fixed.
