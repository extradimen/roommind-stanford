# RoomMind generational exploration and evidence governance

## Purpose

RoomMind is developed as an evidence-driven simulation architecture rather
than as a sequence of untraceable prompt edits. A **version** is a candidate
configuration or implementation within one architecture generation. A new
**generation** is created only when the causal architecture changes materially,
for example when the system introduces a turn coordinator, a fact registry, or
a different agent decision model.

## Evidence stages

Every new batch is explicitly labeled as one of three stages and the label is
frozen in its research manifest.

1. **Exploration**: diagnose failures, compare candidate versions, and generate
   hypotheses. These data are development evidence and cannot be reported as
   confirmatory results.
2. **Screening**: select a candidate using predeclared gates and a fixed scenario
   panel. These data are selection evidence only.
3. **Confirmation**: evaluate one frozen candidate on held-out scenarios or
   seeds. These data may support the paper. They must not be used to tune that
   same candidate.

The manifest records the generation, architecture version, source revision,
stage, random seed, and its own SHA-256. Failed and partial runs remain part of
the archive; they are never silently deleted from the denominator.

## Four independent evidence layers

1. **Deterministic probes** test objective invariants such as authority,
   dispatch, information visibility, agreement retention, and stop semantics.
2. **Autonomous matched experiments** compare RoomMind and the conventional
   independent-agent baseline with the same scenario, player policy, model,
   maximum turns, and seed schedule.
3. **Agentic UX audits** use the real web interface to inspect responsiveness,
   recovery, phase synchronization, and whether a complete session feels like a
   plausible meeting. UX observations are not substituted for realism ratings.
4. **External expert blind review** is collected later and independently. The
   reviewer sees the case, role/authority reference, and an anonymous real
   transcript, but never the treatment condition, generation, model, internal
   memories, or automatic scores.

## Authentic transcript rule

Expert packets are generated only from persisted `session_messages`. Dialogue
text is exported verbatim in sequence order. It is not translated, summarized,
rewritten, or regenerated for presentation. A SHA-256 of the canonical public
transcript is displayed to the reviewer and submitted with the rating. The API
recomputes the hash before accepting the review. Finalized reviews are
immutable.

The interface and rubric are bilingual. The source dialogue remains in its
original language; a future optional translation may be shown only alongside
the original and must never replace the evidence text.

## Expert review instrument

The six realism dimensions are kept separate. Each dimension contains three
1–7 indicators:

- role and strategic fidelity;
- information-boundary (epistemic) fidelity;
- temporal coherence;
- interaction-structure fidelity;
- multi-party dynamics fidelity;
- procedural fidelity.

The dimension score is the arithmetic mean of its three registered indicators.
Reviewers also give an independent overall-believability rating and cite public
sequence numbers. AI ratings, deterministic metrics, and human ratings remain
separate in reporting; RoomMind does not manufacture a single total score.

For formal collection, assign at least three experts per transcript using
server-side stratified randomization, report ICC or Krippendorff's alpha, and
record expertise and experience. The current development page accepts reviewer
codes. Production deployment must replace that identity layer with verified
email magic links or institutional SSO while preserving the same anonymous
packet and immutable-review contract.

## Current generation

`G1 / g1-governed-independent-agents` is the first generation registered under
this protocol. Earlier iterations remain documented as historical development
evidence (`G0`) and must not be mixed with G1 confirmation results. The canonical
machine-readable registry is `config/research-generations.json`.

