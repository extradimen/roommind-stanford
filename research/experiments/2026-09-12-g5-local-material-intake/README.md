# G5 local material intake audit

Synthetic engineering evidence only. No real labels, external model calls, human review, push, deployment or online experiment.

`panel.json` preserves the prior calibration panel's file-byte hash, complete source/manifest/annotation plan, registry snapshots, 24 unlabelled review tasks and replay verification. Content hash: `8900dd011c3e76c121b0135354061361d7cc9ae500575bd28cc12bc45f05fe91`.

The new registry is an illustrative local registry, NOT a complete historical exposure inventory. Its initially empty exposure list does not establish that these old development fixtures were unseen. The intake durably records calibration exposure before returning tasks. Existing annotations are neither copied as fresh labels nor overwritten.

Family-parent links and exact snapshot matches propagate recorded exposure across connected families. Undeclared paraphrases, missing historical exposure and real human identity cannot be independently detected by this registry. Snapshot pinning requires re-audit after any append. These checks are not yet a mandatory launch gate in the legacy factorial runner.

The full audit bundle contains arm metadata and private role/world facts. It is not a blinded reviewer distribution file. Only individual task objects omit explicit arm identifiers and reference labels; visible content can still reveal conditions. No distribution is authorized by this artifact.

Reproduce into a NEW directory:

```sh
PYTHONPATH=server:server/tests .venv312/bin/python server/tests/test_g5_family_registry.py --output-dir NEW_DIRECTORY
```

SQLite triggers and hash-chain replay protect cooperative append-only use and detect inconsistent mutation. They do not authenticate provenance or resist an administrator rewriting a complete database and its hashes.
