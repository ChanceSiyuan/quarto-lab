# AutoQEC Zoo

This directory stores structured code knowledge derived from papers.

## Source of truth

- `codes/**/card.json`: canonical code cards
- `evidence/**/*.json`: paper-level evidence

## Derived artifacts

- `codes/**/card.md`
- `views/*.json`
- `views/browse.md`
- `views/site/**`

Do not hand-edit derived artifacts. Rebuild them with:

```bash
python3 -m autoqec_zoo.cli build --root zoo
```

## External reference layer: Error Correction Zoo mirror

`external/eczoo/` is a committed, full mirror of The Error Correction Zoo
(`errorcorrectionzoo/eczoo_data`), used as a read-only reference. It is
**separate** from the curated source-of-truth above and is licensed CC-BY-SA 4.0
(see `external/eczoo/NOTICE.md`).

- `external/eczoo/raw/` — vendored upstream YAML (do not hand-edit)
- `external/eczoo/index/eczoo-codes.json`, `eczoo-relations.json` — derived index
- `external/eczoo/views/browse.md`, `views/site/` — derived browse artifacts

Refresh and rebuild:

```bash
make eczoo-update     # fetch upstream snapshot, then rebuild index + views
make eczoo-build      # rebuild from the existing raw/ snapshot only
```

Curated cards may point at an eczoo entry via the optional `eczoo_ref` field
(an eczoo `code_id`).
