# AutoQEC Harness Initialization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the empty `AutoQEC` directory as a `qec.harness`-style discussion harness with Zulip wiring and a dual-plugin `onboard` bootstrap.

**Architecture:** Start from the `init-harness` template set to preserve the established harness contract, then patch the generated files for the AutoQEC-specific Zulip site, stream, credential path, and `sci-brain` onboarding requirements. Keep the repository thin: docs, Makefile, knowledge-base placeholder, and one project-local skill.

**Tech Stack:** Markdown, Makefile, project-local Claude skill markdown, Python-based scaffold helper for template generation

---

### Task 1: Generate the baseline harness skeleton

**Files:**
- Create: `Makefile`
- Create: `CLAUDE.md`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: `.knowledge/INDEX.md`
- Create: `.claude/skills/onboard/SKILL.md`

- [ ] **Step 1: Run the bundled scaffold helper into the current directory**

```bash
python3 /Users/nzy/.codex/skills/init-harness/helpers/scaffold.py \
  --topic autoqec \
  --target-dir /Users/nzy/mcode/AutoQEC \
  --zulip-stream "QEC automated search" \
  --zulip-site "https://qec-harness.zulipchat.com" \
  --config-label "qec-harness" \
  --github-remote "CodingThrust/AutoQEC" \
  --topic-blurb "Reference / discussion harness for automated quantum error-correction search, literature tracking, and Zulip-based collaboration."
```

- [ ] **Step 2: Verify the scaffold command succeeded**

Run: `find /Users/nzy/mcode/AutoQEC -maxdepth 4 -type f | sort`
Expected: the root docs, `Makefile`, `.gitignore`, `.knowledge/INDEX.md`, and `.claude/skills/onboard/SKILL.md` all exist

- [ ] **Step 3: Confirm there are no unresolved template placeholders in the generated baseline**

Run: `rg '<<TOPIC>>|<<ZULIP_STREAM>>|<<ZULIP_SITE>>|<<CONFIG_LABEL>>|<<WORKSPACE_LABEL>>|<<GITHUB_REMOTE>>|<<TOPIC_BLURB>>' /Users/nzy/mcode/AutoQEC`
Expected: no matches

### Task 2: Adapt the generated files to AutoQEC conventions

**Files:**
- Modify: `Makefile`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Update the Makefile credential directory to the desired path**

Edit `Makefile` so the assignment is:

```make
ZULIP_CONFIG_DIR_DEFAULT := $(HOME)/zulip-workspaces/qec-harness
```

- [ ] **Step 2: Rewrite `README.md` for the AutoQEC harness identity**

The file should describe AutoQEC as a reference / discussion harness for automated QEC search and keep the onboarding instructions to a short clone-and-run-`onboard` flow.

- [ ] **Step 3: Rewrite `CLAUDE.md` to replace template placeholders and dormant sections with AutoQEC-specific guidance**

Include concrete text for:

- repository purpose
- first-time setup with both `zlp-harness` and `sci-brain`
- knowledge-base usage
- Zulip usage
- `sci-brain` workflows
- reliable update sources for automated QEC search

- [ ] **Step 4: Tighten `.gitignore` only if the generated template does not already cover local harness state**

Run: `sed -n '1,240p' /Users/nzy/mcode/AutoQEC/.gitignore`
Expected: ignores `.zulip/`, `.knowledge/.raw/`, `.knowledge/.figures/`, `.claude/settings.local.json`, and future LaTeX artifacts

### Task 3: Upgrade the onboard skill to enable both plugins

**Files:**
- Modify: `.claude/skills/onboard/SKILL.md`

- [ ] **Step 1: Update the description and prose to mention both `zlp-harness` and `sci-brain`**

The opening description and Phase A explanation must describe enabling both plugins globally.

- [ ] **Step 2: Change the phase-detection code so Phase B requires both plugins to be configured**

The Python check should confirm:

```python
data.get("enabledPlugins", {}).get("zlp-harness@zlp-harness") is True
data.get("enabledPlugins", {}).get("sci-brain@sci-brain") is True
"zlp-harness" in data.get("extraKnownMarketplaces", {})
"sci-brain" in data.get("extraKnownMarketplaces", {})
```

- [ ] **Step 3: Update the JSON diff shown to the user and the merge snippet**

The file should merge:

```json
"extraKnownMarketplaces": {
  "zlp-harness": {
    "source": { "source": "github", "repo": "GiggleLiu/zlp-harness" }
  },
  "sci-brain": {
    "source": { "source": "github", "repo": "QuantumBFS/sci-brain" }
  }
},
"enabledPlugins": {
  "zlp-harness@zlp-harness": true,
  "sci-brain@sci-brain": true
}
```

- [ ] **Step 4: Update the post-restart expectations**

The done checklist should mention the loaded `zlp-harness:*` and `sci-brain:*` skills relevant to this repo.

### Task 4: Verify the initialized harness

**Files:**
- Verify: `Makefile`
- Verify: `CLAUDE.md`
- Verify: `.claude/skills/onboard/SKILL.md`
- Verify: `.knowledge/INDEX.md`

- [ ] **Step 1: Run the config contract**

Run: `make -C /Users/nzy/mcode/AutoQEC zulip-config`
Expected:

```text
ZULIP_SITE=https://qec-harness.zulipchat.com
ZULIP_STREAM=QEC automated search
ZULIP_CONFIG_DIR_DEFAULT=/Users/nzy/zulip-workspaces/qec-harness
```

- [ ] **Step 2: Verify the onboard skill mentions both plugin identifiers**

Run: `rg -n 'zlp-harness|sci-brain' /Users/nzy/mcode/AutoQEC/.claude/skills/onboard/SKILL.md`
Expected: matches for both plugin names and repo identifiers

- [ ] **Step 3: Verify the knowledge-base placeholder title**

Run: `sed -n '1,20p' /Users/nzy/mcode/AutoQEC/.knowledge/INDEX.md`
Expected: first line is `# autoqec — references` or equivalent AutoQEC title

- [ ] **Step 4: Do a final unresolved-placeholder sweep**

Run: `rg '<<[A-Z_]+>>' /Users/nzy/mcode/AutoQEC`
Expected: no matches
