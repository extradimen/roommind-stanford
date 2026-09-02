# G2.1 grounded coordination qualification protocol

## Purpose

Test whether the G2.1 candidate repairs the specific G2 qualification failures without
changing the conventional independent-memory Baseline or the shared public-only player.
This remains development-only exploratory evidence.

## Frozen candidate

- Generation: `G2.1`
- Architecture: `g2.1-grounded-coordinated-independent-agents`
- Fixed provider/model: `ollama/gpt-oss:120b`
- Same two scenarios, two conditions, two repetitions, seed policy, 20-turn safety limit,
  six-turn stagnation limit, and concurrency 1 as the G2 qualification
- Dialogue generation, AI evaluation, and later human review remain separate

## Candidate changes

1. Copy generation manifest and architecture version into every archived session.
2. Activate G2/G2.1 integrity probes from frozen session metadata.
3. Normalize `player`/`user` aliases and never select player-only work as a private NPC
   coordinator focus.
4. Prioritize routable commitments by due state and promise age rather than lexical key.
5. Prevent a public claim of completion from overriding unmet evidence-backed conditions;
   reconcile it to conditional or deferred closure with explicit unresolved fields.
6. Require agents and the evaluator to avoid fabricated links, attachments, hashes,
   measurements, approvals, cross-role facts, and unsupported live-system actions.

## Qualification gates

The deterministic and progression gates from `EXPERIMENT_G2_QUALIFICATION.md` remain
unchanged. In addition:

- all four RoomMind sessions must show applicable, passing G2.1 coordination-history,
  monotonically increasing turn, registered-focus-owner, and memory-partition probes;
- no terminal `completed` result may retain an unmet configured completion condition;
- no public message may use a fabricated link/hash/attachment as the sole evidence of
  submitted work or completed action.

Only if every deterministic gate and every progression gate passes may G2.1 advance to a
new 24-cell exploration. Scores from G2 are diagnostic inputs, not pooled observations.
