# Require transitive trust closure

Trusted Knowledge must be transitively closed: a page under `theory/` may not link to `drafts/` or `conference/`, whether directly or through a moved former path. Stale navigational links are removed; when a trusted page substantively relies on a draft claim, theorem, proof, or procedure, the dependant page also moves to `drafts/` unless the dependency is made self-contained and promoted first.
