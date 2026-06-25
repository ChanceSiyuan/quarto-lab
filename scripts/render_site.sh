#!/usr/bin/env bash
set -euo pipefail

.venv/bin/python scripts/update_theory_nav.py
quarto render "$@"
