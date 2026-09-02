# G3.3 Contextual Speech Boundary Local Prequalification

Date: 2026-09-02

Status: local engineering candidate; not pushed, deployed or qualified on the
staging comparison system.

## Trigger

The frozen G3.2 batch showed that the lifecycle entailment guard protected the
ledger but damaged conversation. Its historical-anchor detector recognized
phrases such as `In my previous role ...` but rejected ordinary interview
answers beginning `I led ...`, `I managed ...`, or `One project ...`. Questions
mislabelled by structured output as retrospective were also rejected even
though they asserted no historical fact. After two failures, both the shared
player and NPC renderer emitted a single generic clarification sentence, which
became a multi-turn loop.

## G3.3 change

G3.3 keeps the G3/G3.2 authoritative ledger, permissions, lifecycle ordering,
external-action restrictions, artifact/link/hash checks and final wording
entailment boundary. It changes only contextual interpretation and recovery:

1. normal first-person past-action constructions are accepted as retrospective
   anchors;
2. a question carrying a mistaken retrospective scope is not rejected unless
   its actual wording asserts a lifecycle stronger than the validated intent;
3. current/future assertions such as `I am verifying it now and will proceed`
   remain rejected;
4. the shared comparison player uses rotating, task-preserving fallbacks:
   retrospective interviews receive an anchored answer, while live tasks ask
   the responsible participant for specific evidence;
5. NPC renderer failure uses the validated public subject and the role's public
   job title instead of one universal clarification sentence; the fallback is
   itself checked by the same speech boundary.

Because the shared player is identical in both conditions, the player recovery
change is applied symmetrically. RoomMind alone continues to use its governed
NPC renderer and contextual NPC fallback, which is part of the treatment.

## Local evidence

The complete smoke suite passes under an isolated Python 3.12 environment:

- `smoke_public_ledger.py`;
- `smoke_speech_safety.py`;
- `smoke_research_protocol.py`;
- `smoke_llm_resilience.py`;
- application import, compileall and `git diff --check`.

Focused deterministic cases now accept `I led ...` and a non-assertive
interview question, while still rejecting a current live verification falsely
labelled retrospective. Fallback tests verify three distinct retrospective
player variants, targeted live evidence requests and role/subject-specific NPC
wording.

A reusable real-model engineering probe is retained at
`server/tests/g3_3_local_behavior_probe.py`. With the production-model family
through local Ollama (`gpt-oss:120b-cloud`), four interview questions produced
specific, past-grounded examples and three incident questions explicitly
refused to claim that rollback, recovery or evidence verification had
completed. The run used zero fallbacks. Artifact:
`/tmp/roommind-g3.3-gpt-oss-full-behavior-probe.json`.

The local `qwen3.5:0.8b` attempt was stopped after prolonged invisible
reasoning and is retained only as evidence that this weak model remains
unsuitable for naturalness qualification.

## Next gate

Before push or deployment, review the source diff and rerun the smoke suite.
The next staging batch must be newly created and frozen as G3.3. It should use
the same four scenarios, fixed GPT-OSS 120B, one sequential matched pair per
scenario, and no human review during generation. Qualification requires both
ledger integrity and a material reduction in repeated/fallback turns; technical
completion alone is insufficient.
