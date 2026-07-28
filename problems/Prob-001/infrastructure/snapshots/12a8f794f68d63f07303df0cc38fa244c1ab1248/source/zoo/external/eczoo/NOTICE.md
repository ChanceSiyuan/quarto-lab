# Attribution — Error Correction Zoo data

The contents of this directory (`zoo/external/eczoo/`), including the vendored
YAML under `raw/` and all derived artifacts under `index/` and `views/`, are
adapted from **The Error Correction Zoo** (V. V. Albert and P. Faist, editors),
https://errorcorrectionzoo.org.

- Source repository: https://github.com/errorcorrectionzoo/eczoo_data
- Snapshot commit: see `SNAPSHOT.md`
- License: Creative Commons Attribution-ShareAlike 4.0 International
  (CC-BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

- Selected the `codes/` YAML tree only (other upstream assets omitted).
- Derived `index/eczoo-codes.json` and `index/eczoo-relations.json` by parsing,
  filtering, and reshaping the YAML; computed inverse relation edges.
- Generated `views/browse.md` and `views/site/` from the derived index.

These derived artifacts remain licensed CC-BY-SA 4.0. This obligation applies
only to the eczoo-derived material in this directory; the rest of this
repository (the importer code, JSON schemas, and original curated cards) is
licensed under the repository's own terms.
