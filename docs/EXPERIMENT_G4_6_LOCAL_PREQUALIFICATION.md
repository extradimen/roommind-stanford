# G4.6 Clause-Grounded Recovery Governance Local Prequalification

## Research status

G4.6 is a narrow exploratory successor to G4.5. It is not yet deployed and does
not establish a realism advantage. G4.5 and all earlier frozen dialogues remain
unchanged. A new fixed-model matched batch is required after deployment.

## Evidence motivating this iteration

The frozen G4.5 qualification completed reliably and showed directional
improvement, but its incident-command run exposed a distinct repair-path gap:

1. a valid price confirmation followed by a question was treated as if the
   entire utterance were only a request, causing a false duplicate diagnostic;
2. unsupported current-world claims used uncovered forms such as placing logs
   in a bucket, matching hash signatures and reporting newly changed metrics;
3. a blocking task could be assigned with the form “assign the check to Name”
   or “Name will handle it”, bypassing the registered-participant guard;
4. safe player recovery rotated among semantically equivalent closeout
   sentences, creating a visible loop;
5. an NPC clause repair could become a duplicate only after the unsafe clause
   was removed, without receiving a second repetition check.

## Architecture changes

1. **Clause-local quote grounding.** A material transition is accepted when its
   own declarative clause is grounded, even if a separate clause asks a
   follow-up question. Pure requests remain non-committing. The accepted intent
   records `quote_grounding=material_clause`, and telemetry counts these cases.
2. **Expanded source-typed evidence boundary.** Current quantitative service
   metrics, bucket/store placement, received live logs and hash-signature
   matching require a registered simulated-tool result. The rule is based on
   visible language, not the model's chosen intent label.
3. **Registered in-session ownership grammar.** Post-object assignment
   (“assign this to Name”) and future execution (“Name will verify/handle”) are
   checked against the public participant directory. Explicit external
   follow-up remains allowed only when both metadata and wording mark it as
   outside the meeting.
4. **Single bounded player recovery.** A no-evidence recovery statement may be
   used once. A second attempt requests truthful bounded closure rather than
   rotating through paraphrases.
5. **Repair-path parity.** Repaired NPC clauses and configured public fallbacks
   receive the same same-speaker and cross-role obligation duplicate checks as
   ordinary drafts and rendered candidates.

Independent role memories, perceive–retrieve–plan–reflect–act loops, meeting
obligation graph, scenarios, Baseline architecture, fixed model and six realism
dimensions remain unchanged. The candidate therefore isolates recovery and
public-evidence governance.

## Local verification evidence

- `smoke_public_ledger.py`: pass, including mixed confirmation-plus-question
  grounding and the material-clause audit marker;
- `smoke_speech_safety.py`: pass, including frozen G4.5 evidence and ownership
  counterexamples plus bounded player recovery;
- `smoke_llm_resilience.py`: pass;
- `smoke_research_protocol.py`: pass;
- database-backed `smoke_modes.py`: pass against the isolated local PostgreSQL
  test database;
- Python `compileall`: pass;
- client and admin production builds: pass (existing bundle-size warnings only);
- `git diff --check`: pass.

A counterfactual replay of the frozen G4.5 public transcripts produced no new
rejection in negotiation, launch or interview. It identified eight problematic
incident-command utterances: three unsupported live metric/containment claims,
two unsupported log/hash artifact claims and three unregistered-owner claims.
Re-grounding negotiation sequence 11 preserves the valid 84 RMB confirmation,
records `material_clause`, and changes the cross-role-obligation repetition
probe from fail to pass. This replay is deterministic mechanism evidence only;
it is not a replacement for newly generated dialogue.

## Qualification gates for a new batch

Use the same four scenarios, paired conditions, seed policy, player policy,
turn limits, concurrency one and `ollama/gpt-oss:120b` model. Freeze all eight
dialogues before evaluation. The candidate passes only if:

1. all dialogues complete without degraded output and all transcript hashes
   recompute;
2. all applicable G2–G4.6 integrity probes pass, with no unsupported visible
   current-world evidence or unregistered in-session owner;
3. a mixed confirmation-plus-question produces a material transition rather
   than a false repetition when it occurs;
4. no repair/fallback path creates a repeated closeout or obligation request;
5. incident command ends with internally consistent evidence and ownership,
   whether completed or truthfully conditional;
6. independent evaluation is complete and manual reading of all four matched
   pairs finds no material regression.

Do not start external human review automatically. G4.6 remains development
evidence until these gates pass on a new frozen batch.
