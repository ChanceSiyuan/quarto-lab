# AutoQEC Harness Design

## Goal

Initialize `/Users/nzy/mcode/AutoQEC` as a discussion harness modeled on `qec.harness`, with a project-local `onboard` skill that bootstraps both the `zlp-harness` and `sci-brain` plugins, and a Zulip bridge pointed at the `QEC automated search` stream on `https://qec-harness.zulipchat.com`.

## Scope

This repository is intentionally a collaboration shell, not an implementation repo. It should contain:

- a root `Makefile` exposing the standard `zulip-config` contract and `zulip-*` commands
- root docs (`README.md`, `CLAUDE.md`, `AGENTS.md`) written in discussion-harness style
- `.knowledge/INDEX.md` as the initial knowledge-base placeholder
- `.claude/skills/onboard/SKILL.md` as a thin bootstrap layer that installs required plugins globally and then delegates Zulip setup to `zlp-harness:zlp-onboard`
- `.gitignore` covering local Zulip archives, local knowledge-base raw assets, local Claude settings, and future LaTeX outputs

No code implementation, no GitHub repo creation, and no automatic onboarding execution are part of this initialization.

## Repository Identity

- Topic slug: `autoqec`
- Display/project name in prose: `AutoQEC`
- Role: reference / discussion harness for automated QEC literature search, reading, and collaboration

The root docs should state clearly that implementation code lives elsewhere or is not yet part of this repo.

## Zulip Integration

The root `Makefile` should follow the established harness contract and bind:

- `ZULIP_SITE := https://qec-harness.zulipchat.com`
- `ZULIP_STREAM := QEC automated search`
- `ZULIP_CONFIG_DIR_DEFAULT := $(HOME)/zulip-workspaces/qec-harness`

The repository must expose:

- `zulip-config`
- `zulip-whoami`
- `zulip-topics`
- `zulip-messages`
- `zulip-pull`
- `zulip-send`

`zulip-config` is the compatibility boundary that `zlp-harness:zlp-onboard` depends on. It must print stable `KEY=VALUE` lines for site, stream, and default credential directory.

## Onboard Flow

The bundled project-local `onboard` skill should stay thin and keep the same two-phase structure as the template:

1. Detect whether the required plugins are already enabled in `~/.claude/settings.json`.
2. If not, show the exact JSON additions and ask for confirmation.
3. Merge the plugin marketplace entries and enabled flags without clobbering unrelated settings.
4. Stop and require a Claude Code restart.
5. On the next run, verify the plugin skill is loaded and delegate to `zlp-harness:zlp-onboard`.

Unlike the stock template, this repo's `onboard` must configure both plugins:

- `zlp-harness` from `GiggleLiu/zlp-harness`
- `sci-brain` from `QuantumBFS/sci-brain`

The actual Zulip credential setup remains delegated to `zlp-harness:zlp-onboard`; the local skill must not duplicate that logic.

## Documentation

`README.md` should stay brief and tell a collaborator to clone the repo and invoke `onboard`.

`CLAUDE.md` should cover:

- repository purpose
- first-time setup
- Zulip commands
- knowledge-base expectations
- recommended `sci-brain` workflows such as `survey`, `download-ref`, `review-writer`, and `ideas`
- `zlp-advisor` style reliable-source guidance tailored to AutoQEC topics

It is acceptable for the reliable-source section to contain a concrete first pass rather than placeholders.

## Verification

Initialization is complete when:

- `Makefile` exists and `make zulip-config` prints the correct values
- no unresolved `<<...>>` placeholders remain in generated files
- `.claude/skills/onboard/SKILL.md` exists and mentions both plugin names
- `.knowledge/INDEX.md` exists with the AutoQEC title

