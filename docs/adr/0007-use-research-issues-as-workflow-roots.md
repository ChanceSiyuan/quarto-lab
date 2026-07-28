# Use research issues as workflow roots

**Status: deferred architecture; no autonomous runner exists in this phase.**

When autonomous investigation is implemented, every run will be rooted in a
durable Research Issue, with each attempt captured as an immutable Research
Run containing its inputs, Evidence, methods, results, failures, and Research
Drafts. Notes, papers, and chats are inputs or outputs rather than hidden
workflow state; agents may create and investigate Issues or request review,
but only the user may mark an Issue resolved, rejected, or abandoned.
