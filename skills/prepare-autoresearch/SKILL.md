---
name: prepare-autoresearch
description: Use when an autoresearch campaign needs a host-staged candidate contract before execution.
---

# Prepare an autoresearch campaign

Run only inside the host-provided autoresearch staging directory. Write only
staging files. Never edit `problems/`, `knowledge/`, `drafts/`, `literature/`,
or repository configuration. Never create a batch or attempt.

Build the candidate contract, public checks, independent verifier, scoring,
baseline, dataset manifests, resource policy, environment lock, and focused
anti-gaming tests. Never fabricate a domain-valid metric, correctness rule, or
private dataset. When one material decision is missing, return `needs_input`
with exactly one blocking question.

For every prepared infrastructure manifest, set `runtime.image` to an immutable
OCI digest reference. The selected runtime must already exist locally and must
never use a mutable tag.

Raw development and blind cases remain outside the candidate workspace. Store
only safe manifests and digests in staging; keep private material outside the
candidate tree. When invoked with the structured output schema, return exactly
one matching JSON object.

For `prepared`, return a non-empty summary, `manifestPath` exactly
`"infrastructure.json"`, and `question` as `null`. Write every preparation
artifact only beneath the supplied staging root. For `needs_input`, return a
non-empty summary, `manifestPath` as `null`, and one question with a lowercase
hyphenated ID, non-empty prompt, and either text input with no choices or a
choice input with 2–8 distinct non-empty choices.
