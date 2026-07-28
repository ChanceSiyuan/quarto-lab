# Zulip bridge for AutoQEC — connects to the QEC-automated search stream
# on qec-harness.zulipchat.com. Archive lands under .zulip/ in the repo and
# is gitignored locally so it never round-trips to GitHub.
#
# On a fresh clone the credential dir does not exist. The onboard skill
# creates it after the user downloads zuliprc from the Zulip site. Override
# ZULIP_CONFIG_DIR only if you keep that private API key file somewhere else.

ZULIP_SITE               := https://qec-harness.zulipchat.com
ZULIP_STREAM             := QEC-automated search
ZULIP_CONFIG_DIR_DEFAULT := $(HOME)/zulip-workspaces//qec-harness
ZULIP_CONFIG_DIR         ?= $(ZULIP_CONFIG_DIR_DEFAULT)
ZULIP_LOCAL              := $(CURDIR)/.zulip

export ZULIP_CONFIG_FILE := $(ZULIP_CONFIG_DIR)/zuliprc
export ZLP_ARCHIVE_ROOT  := $(ZULIP_LOCAL)
export ZLP_RUN_ROOT      := $(ZULIP_LOCAL)/.run

ZLP := zlp

.PHONY: zulip-config zulip-whoami zulip-pull zulip-send zulip-topics zulip-messages zoo-build tensorqec-setup eczoo-fetch eczoo-build eczoo-update

# Stable KEY=VALUE contract consumed by the zlp-harness plugin's zlp-onboard skill.
# Add new keys at will — the skill ignores ones it doesn't know.
zulip-config:
	@echo 'ZULIP_SITE=$(ZULIP_SITE)'
	@echo 'ZULIP_STREAM=$(ZULIP_STREAM)'
	@echo 'ZULIP_CONFIG_DIR_DEFAULT=$(ZULIP_CONFIG_DIR_DEFAULT)'

zulip-whoami:
	$(ZLP) whoami

zulip-topics:
	$(ZLP) topics --stream "$(ZULIP_STREAM)"

zulip-messages:
	$(ZLP) messages --stream "$(ZULIP_STREAM)" $(if $(TOPIC),--topic "$(TOPIC)") --limit "$(or $(LIMIT),50)" --format "$(or $(FORMAT),md)"

zulip-pull:
	$(ZLP) pull --stream "$(ZULIP_STREAM)" $(if $(TOPIC),--topic "$(TOPIC)") $(if $(IMPORT_HISTORY),--import-history)

zulip-send:
	@test -n "$(TOPIC)" || { echo "TOPIC=... required"; exit 1; }
	@test -n "$(MSG)$(MSG_FILE)" || { echo "MSG=... or MSG_FILE=... required"; exit 1; }
	$(ZLP) send --stream "$(ZULIP_STREAM)" --topic "$(TOPIC)" \
	  $(if $(MSG),--msg "$(MSG)") $(if $(MSG_FILE),--msg-file "$(MSG_FILE)")

zoo-build:
	python3 -m autoqec_zoo.cli build --root zoo

tensorqec-setup:
	julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/setup.jl

eczoo-fetch:
	bash scripts/fetch_eczoo.sh $(REF)

eczoo-build:
	python3 -m autoqec_zoo.cli eczoo --root zoo

eczoo-update: eczoo-fetch eczoo-build
