# G3.9 Natural Joint Confirmation and Closure Prequalification

## Disposition

**G3.9 passes deterministic component prequalification.** It replays the four
remaining closure failures from the frozen G3.8 batch and closes them through
public, authorized speech without weakening the prohibition on requests,
conditional statements, unsupported execution, or invented tool results. It
has not yet passed a database-backed matched RoomMind/Baseline run and is not
evidence of improved realism by itself.

## Frozen G3.8 counterexamples

1. Negotiation participants publicly agreed price, delivery, and quality, but
   only the NPC half of each joint confirmation policy reached the ledger.
2. The CFO approved a phased launch and the player recorded joint approval,
   but the launch decision remained proposed.
3. The interviewee had no further questions and the Product VP marked that
   portion complete, but the interview continued for six unnecessary turns.
4. Incident participants scheduled the next review and the Communications Lead
   said that she was the owner, but the time remained disputed and the owner
   string remained unknown.
5. The G3.8 closure probe returned true for every stalled run because it only
   checked a lock when completion already existed.

## Architecture changes

### 1. Fair shared-player confirmation behavior

The comparison player now uses only the public task specification and public
transcript to determine whether it owes its own half of a joint confirmation.
When an authorized counterpart has already accepted a concrete value and the
player genuinely agrees, it must explicitly voice that acceptance rather than
asking the counterpart to repeat it. The rule is identical for RoomMind and
Baseline generation and exposes no RoomMind private memory or coordinator
state.

### 2. Bounded natural confirmation normalization

Quote-level projection accepts ordinary closure forms including joint approval,
mark/record/declare complete, no further questions, authorized assignment and
scheduling, and imperative meeting decisions such as `Lock` or `Set`. It still
rejects questions, `please/could you/can you/would you` requests, negation,
pending or conditional statements, unauthorized actors, and executable fields
without registered simulated-tool evidence.

### 3. Typed value and identity grounding

Underscore enum values are matched to their spoken space-separated forms, unit
matching accepts safe singular/plural variants such as `30-day` for a `days`
field, and hyphenated field phrases are normalized. An authorized role saying
`I'm the owner` may bind only to that role's registered display name; it cannot
create an arbitrary assignee.

### 4. Full-quote evidence matching

Public-ledger evidence matching no longer truncates a quote to its first twelve
tokens. This fixes the incident statement in which the decisive
`customer-communication owner` phrase occurred near the end of a longer but
single atomic decision.

### 5. Non-vacuous G3.9 integrity gates

Three new deterministic checks apply to G3.9 RoomMind runs:

- the configured task must not end `stalled`;
- a completed task must contain a locked closure record;
- when accepted ledger actors satisfy a configured confirmation policy, the
  aggregate field must atomically contain the same value, `confirmed` status,
  and confirming actors.

The last check derives authorized counterparts from the frozen speaker
directory and task schema. It does not use an LLM realism judgment.

## Deterministic replay evidence

The regression suite now covers:

- a three-field 84 RMB / 30-day / joint-quality negotiation summary confirmed
  by the player, supplier CEO, and quality director;
- CFO phased-launch approval followed by the player's natural record of joint
  approval;
- the exact G3.8 interview forms `I have no further questions` and
  `mark ... complete`;
- a 30-minute review decision and first-person Communications Lead ownership;
- a negative control proving that `Please confirm ...` does not mutate state.

All positive replays reach configured `confirmed` state, complete, and install
the closure lock. The negative request remains `unknown`. The following checks
pass under the isolated Python 3.12 environment:

```text
PYTHONPATH=server .venv312/bin/python server/tests/smoke_speech_safety.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_public_ledger.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_research_protocol.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_llm_resilience.py
.venv312/bin/python -m compileall -q server/app server/tests
git diff --check
```

The research-protocol regression also proves that the new probes pass for a
consistent completed run and fail for a stalled run whose accepted ledger field
remains proposed in the aggregate read model.

### Frozen G3.8 transcript replay

All four frozen RoomMind transcripts were also replayed turn by turn through
the G3.9 deterministic quote projector with no semantic-evaluator updates. This
is a counterfactual reducer check, not a new dialogue experiment:

- product launch changes from `stalled` to `completed` with a closure lock;
- incident command now confirms both the 30-minute review and Sofia Martinez as
  customer-communication owner, while unsupported executable containment stays
  unknown;
- negotiation still lacks the player's side of price and quality acceptance;
- interview still lacks the player's side of candidate-question closure and an
  accepted leadership-evidence utterance.

The latter two are expected and important: a reducer cannot manufacture speech
that never occurred. They can only be tested by generating new dialogues with
the fair shared-player confirmation behavior enabled.

## Remaining qualification boundary

The local checkout has no `.env` or running local PostgreSQL experiment stack,
so a database-backed matched model run cannot be performed without introducing
a new local deployment configuration and model credentials. Before promotion:

1. deploy only after preserving and committing the G3.8 frozen evidence;
2. run four matched RoomMind/Baseline scenario pairs with the fixed model and
   protocol;
3. require 8/8 frozen dialogues, no technical failure or degraded dialogue
   fallback, and valid transcript hashes;
4. require all G3.9 integrity checks to pass for every RoomMind run;
5. inspect whether quote-confirmation commits and closure locks activate in the
   scenarios that publicly reach agreement;
6. independently evaluate, then manually read all pairs before considering
   external human review.
