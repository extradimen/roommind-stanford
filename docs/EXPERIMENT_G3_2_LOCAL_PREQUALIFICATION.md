# G3.2 Local Public-Speech Entailment Prequalification

Date: 2026-09-02

Status: local engineering milestone; not a realism result and not a server
qualification.

## Why G3.2 was required

G3.1 made the public ledger authoritative for state transitions, but a real
local stress run exposed a remaining split between the approved structured
intent and the final words heard by participants. The ledger truthfully kept
all interview evidence fields unknown while public dialogue still said:

- `The engineering director has confirmed ... ready to move forward`;
- `I am confident that ... and I will proceed ...`.

The first fixed-revision counterexample is retained locally at
`/tmp/roommind-g3.1-real-interview/matched-pair.json`; its RoomMind public
transcript SHA-256 is
`dc9c73b899171dbb6ca5084e990eb18afe31a79167b2ccbb559673644181503f`.
The deterministic integrity probes all passed because they verified the ledger,
not whether final natural-language wording entailed the approved lifecycle.
This is therefore a real implementation-integrity gap rather than an evaluator
score disagreement.

A second local counterexample showed that retrospective evidence policy could
act as a blanket exemption. A current fallback line was labelled retrospective
even though it contained no historical context. A third counterexample used
future passive closure: `Engineering evidence will be accepted ...` while the
validated intent remained only `proposed`.

## G3.2 architecture change

G3.2 adds a public-speech lifecycle entailment boundary after intent validation
and before transcript persistence:

1. first-, third-person and passive lifecycle assertions are mapped to the
   minimum lifecycle they imply;
2. final wording cannot assert a stronger lifecycle than the validated intent;
3. deterministic future passive terminal claims such as `will be accepted` are
   treated as closure claims, while conditional language such as `could be
   accepted if ...` remains valid;
4. retrospective policy is grounded per utterance by explicit historical
   anchors, rather than inherited as an exemption by every line in an interview;
5. forced plan-fallback speech now carries a validated conservative public
   intent, receives the current task ledger, and passes through the same speech
   boundary as ordinary NPC decisions;
6. when two renderer attempts remain unsafe, only the existing neutral public
   clarification fallback is emitted.

This boundary is scenario-independent. It does not encode interview fields,
negotiation prices, incident states or launch decisions.

## Local evidence

### Deterministic regression cases

The boundary rejects:

- `The engineering director has confirmed ...` under `proposed`;
- `The engineering team is aligned and ready to move forward` under `proposed`;
- `Engineering evidence will be accepted ...` under `proposed`;
- a current action falsely labelled as retrospective.

It permits:

- `We need to confirm whether ...`;
- `We will review ... before deciding` under `committed`;
- `could be accepted if the authorized reviewer confirms it`;
- an explicitly historical statement beginning `In my previous role ...`.

Direct renderer failure injection forced each unsafe candidate twice. In all
three cases the model wording was rejected and the emitted line was the neutral
clarification `Please clarify the highest-priority open issue before I commit.`

### Real-model output-boundary stress

Three direct `qwen3.5:0.8b` generations, each under a `proposed` intent, were
accepted only when they stated that evidence and authorized confirmation were
still needed before proceeding. This small model remains a failure-injection
tool only; its dialogue quality is not comparable to the fixed GPT-OSS 120B
generational studies.

### Cross-scenario wiring

Four isolated scripted matched pairs covered supply-chain negotiation, product
launch, incident command and retrospective candidate interview. All eight
dialogues reached `dialogue_completed`. Every RoomMind full export passed all
applicable deterministic integrity probes. Each RoomMind run stopped as
`stalled` with unresolved work rather than manufacturing completion.

Local artifacts are retained outside the repository under:

- `/tmp/roommind-g3.2-cross-supply/`;
- `/tmp/roommind-g3.2-cross-launch/`;
- `/tmp/roommind-g3.2-cross-incident/`;
- `/tmp/roommind-g3.2-cross-interview/`;
- `/tmp/roommind-g3.2-real-interview/` (intermediate counterexample);
- `/tmp/roommind-g3.2-final-real-interview/` (future-passive counterexample).

## Limits and next gate

The lifecycle detector is a deterministic safety boundary, not a substitute for
human realism judgment. It deliberately covers auditable closure semantics and
may still miss paraphrases without lifecycle language. Before staging, G3.2
requires the full smoke suite and a clean source revision. Server qualification
must then use the fixed production-capable model and a new batch; no G1-G3.1
artifact may be overwritten. Independent AI evaluation and later bilingual
human blind review remain downstream processes and must not be started during
dialogue generation.

