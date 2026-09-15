# G4.14 Publication Owner and Live-Artifact Grounding

G4.14 is a narrow exploratory successor to G4.13. It changes only the response
ownership and publication-boundary failures observed in the frozen G4.13
qualification batch. It does not change the scenarios, Baseline, fixed model,
seed policy, evaluator, or transcript-freezing contract.

## Frozen motivating evidence

- Run 542 sequence 15 addressed Samir, but the player relayed the question at
  sequence 16 and Samir answered only at sequence 17.
- Run 544 sequence 38 addressed Avery / the product VP, but other roles spoke
  and the target did not answer before the next player message.
- Run 546 sequence 17 directed a question from SRE to Security, but the player
  inserted an administrative relay before Security answered.
- Manual review found unsupported present-world claims that newly uploaded
  material had been reviewed, that a roadmap was available in Confluence, and
  that logs had been copied to an archive bucket with a manifest generated.

## Mechanisms under test

1. The current player message's structured public target supplements visible
   addressee parsing, and both sources feed one ordered response-owner lock.
2. A required-response flag reaches every decision and rendering path. If the
   ordinary and contextual candidates fail publication checks, the owner may
   emit one role-local, noncommittal answer with no ledger transition.
3. NPC-to-NPC questions can form a bounded same-turn chain. The budget is the
   number of present NPCs, and each target can be rescheduled at most once per
   autonomous turn, preventing cycles.
4. Public grounding rejects present-world claims that uploaded material was
   reviewed, shared-repository or Confluence artifacts are available, logs or
   snapshots were copied to an archive bucket, or a manifest was generated,
   unless backed by a registered simulated-tool result.
5. The G4.14 composite integrity gate requires convergence of ordered player
   responses, direct NPC responses, routing-language absence, public evidence,
   and visible current-world actions.

## Preserved controls

- fixed provider/model: `ollama/gpt-oss:120b`;
- dialogue and evaluation concurrency: 1;
- four matched scenarios and one repetition;
- Stanford-style independent memories and cognitive loop;
- shared autonomous player and unchanged Baseline;
- unchanged six-dimension evaluation contract;
- frozen transcript hashes and independent post-generation evaluation;
- all applicable legacy integrity probes through G4.13.

## Local prequalification gates

- all server smoke tests and Python compilation pass;
- PostgreSQL dual-mode integration and closeout regression pass;
- client and admin production builds pass;
- structured `public_intent.target_id` survives conservative text parsing;
- required-response fallback is safe, nonempty, role-local, and cannot commit a
  public-ledger transition;
- a direct A-to-B-to-C response chain is possible but cyclic rescheduling is
  bounded to one addition per target in a turn;
- the exact G4.13 routing failures are retained as frozen counterexamples;
- the exact G4.13 live-artifact claims are rejected by deterministic probes;
- no scenario, Baseline, model, evaluator, or prior research artifact changes.

## Local result

PASS. Python compilation; public-ledger, speech-safety, LLM-resilience, and
research-protocol smoke tests; frozen G4.6 through G4.13 replay checks;
PostgreSQL dual-mode and closeout integration; and client/admin production
builds all passed. The frontend builds retain only the existing large-chunk
warnings. This result establishes implementation coverage only and does not
authorize a push, staging deployment, or live qualification batch.

## Live qualification gates

- deployment and batch creation require separate explicit authorization;
- deployed revision and frozen manifest must match the authorized G4.14 commit;
- 8/8 dialogues must freeze with zero dialogue failures and no degraded output;
- all transcript hashes must recompute before and after evaluation;
- every G4.14 and applicable legacy probe must pass on every RoomMind run;
- manual review must find no player relay, missing addressed response,
  unsupported live-artifact claim, routing prompt, or post-terminal speech;
- all 48 independent run-dimension evaluations must complete without replacing
  previously completed dimensions;
- all four RoomMind/Baseline pairs must be manually reviewed before disposition.

G4.14 remains exploratory. Passing local and live gates does not authorize
external human review and does not support a confirmatory claim.
