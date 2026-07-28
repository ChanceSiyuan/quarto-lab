from __future__ import annotations

import re
from pathlib import Path

from autoqec_search.quantum_tanner_generator import load_quantum_tanner_sweep_config


REPO_ROOT = Path(__file__).resolve().parents[1]
QT_WORKFLOW_DOC = (
    REPO_ROOT / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "README.md"
)
CSS_DISTANCE_AUTORESEARCH_DOC = (
    REPO_ROOT / "campaigns" / "examples" / "css-distance-autoresearch" / "README.md"
)
LONG_RUN_SCRIPT = REPO_ROOT / "scripts" / "run_quantum_tanner_autoresearch.sh"
QT_GENERATOR_CONFIG = (
    REPO_ROOT
    / "campaigns"
    / "examples"
    / "quantum-tanner-autoresearch"
    / "generator.json"
)


def _bash_blocks(document: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", document, flags=re.DOTALL)


def _attach_witness_blocks(document: str) -> list[str]:
    return [
        block
        for block in _bash_blocks(document)
        if "attach-quantum-tanner-witnesses" in block
    ]


def _assert_quantum_tanner_guardrails(document: str) -> None:
    assert "p=0.001" in document
    assert "1 - (1 - P_single)^k" in document
    assert "upper-bound distances must not be promoted as exact Zoo distances" in document
    assert "upper-bound witnesses are screening evidence only" in document
    assert "must not be promoted as exact Zoo distance evidence" in document
    assert "requires generated witnesses to be X-like" in document
    assert "Z-like witnesses can remain valid generic CSS witnesses" in document
    assert "incompatible with this memory-X screening task" in document
    assert "witness_finder_summary.json" in document
    assert "screening.json" in document


def test_repo_docs_reference_search_layer() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "campaigns/" in readme
    assert "benchmarks/" in readme
    assert "autoqec-search" in readme
    assert "results/search/" in claude
    assert "autoqec-search" in claude


def test_docs_mention_single_candidate_eval_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search eval" in readme
    assert "--decoder rmatching-default-v1 --p 0.01" in readme
    assert "strictly requires `rsinter`" in readme

    assert "autoqec-search eval" in claude
    assert "copies recorded distance" in claude
    assert "strictly requires `rsinter`" in claude


def test_docs_mention_exact_first_distance_registry() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "registry is exact-first" in document
        assert "default `copied-zoo-exact` method records Zoo" in document
        assert "guarded `rstim-ilp-exact` method" in document
        assert "rstim exact CSS distance backend is not available" in document
        assert "Randomized upper bounds live in rstim" in document
        assert "must never treat an upper bound as Zoo" in document


def test_css_distance_autoresearch_docs_describe_packaged_quotient_coset_finder() -> None:
    document = CSS_DISTANCE_AUTORESEARCH_DOC.read_text()
    assert "autoqec-search find-quotient-coset-upper-bound" in document
    assert "quotient-coset-upper-bound" in document
    assert "upper bound" in document.lower()
    assert "not an exact-distance method" in document


def test_css_distance_paper_suite_docs_describe_operator_boundary() -> None:
    campaign = CSS_DISTANCE_AUTORESEARCH_DOC.read_text()
    pool = (
        REPO_ROOT / "benchmarks" / "css_distance_paper_validation" / "README.md"
    ).read_text()

    for document in (campaign, pool):
        assert "prepare-css-distance-paper-suite" in document
        assert "validate-css-distance-paper-suite" in document
        assert "freeze-css-distance-paper-candidate" in document
        assert "outside Git worktrees" in document
        assert "proposal agents" in document
        assert "commitment.json" in document
        assert "20 committed seeds" in document
        assert "300 seconds" in document
    assert "Do not mount" in campaign
    assert "sealed final" in campaign
    assert "candidate freeze" in pool


def test_docs_mention_autoresearch_run_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search run" in readme
    assert "autoresearch/<tag>" in readme
    assert "--resume" in readme
    assert "--cleanup-worktree" in readme

    assert "autoqec-search run" in claude
    assert "experiment-log.tsv" in claude
    assert "run-summary.html" in claude
    assert "--cleanup-worktree" in claude


def test_quantum_tanner_docs_describe_long_running_codex_launcher() -> None:
    root_readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()
    workflow = QT_WORKFLOW_DOC.read_text()
    assert LONG_RUN_SCRIPT.is_file()
    assert "scripts/run_quantum_tanner_autoresearch.sh" in root_readme
    assert "--work-root /tmp/autoqec-qt-long" in workflow
    assert "--rounds 20" in workflow
    assert "--proposals-per-round 4" in workflow
    assert "--run-wall-clock 30m" in workflow
    assert "--resume" in workflow
    assert "state.json.source_commit" in workflow
    assert "git switch --detach" in workflow
    assert "Advancing HEAD" in workflow
    assert "resume fails before Codex, qec-code, or rsinter" in workflow
    assert "codex exec --ephemeral" in workflow
    assert "fresh Codex context" in workflow
    assert "proposal-generation invocation can consume Codex/model tokens" in workflow
    assert re.search(
        r"local qec-code/rsinter backend\s+wait time does not consume additional Codex tokens",
        workflow,
    )
    assert "upper-bound screening evidence" in workflow
    assert "state.json" in workflow
    assert "cumulative-feedback.json" in workflow
    assert "`status.json` contains an absolute `run_root` field" in workflow
    assert "report.html" in workflow
    assert "surface-copy-comparison.html" in workflow
    assert "quantum-tanner-ai-feedback.html" in workflow
    for document in (workflow, root_readme, claude):
        assert "aggregate/report.html" in document
    assert "aggregate/results.jsonl" in workflow
    assert "one finite code per row" in workflow
    assert "evaluated, skipped, failed, and interrupted" in workflow
    assert "before the next Codex proposal" in workflow
    assert "--resume" in workflow
    assert "python3 -c" in workflow
    assert "json.load(open" in workflow
    assert '[\"run_root\"]' in workflow


def test_docs_mention_search_report_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search report" in readme
    assert "report.html" in readme
    assert "self-contained" in readme
    assert "offline" in readme

    assert "autoqec-search report" in claude
    assert "report.html" in claude
    assert "run-summary.html" in claude
    assert "offline" in claude


def test_docs_mention_zoo_promotion_command_and_rules() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search promote" in readme
    assert "promote_rules.json" in readme
    assert "--force" in readme
    assert "promotion_summary.json" in readme
    assert "zoo/views/instance-index.json" in readme

    assert "autoqec-search promote" in claude
    assert "promote_rules.json" in claude
    assert "promotion_summary.json" in claude
    assert "auto-copy accepted instance into the curated Zoo" in claude


def test_docs_mention_m1_showcase_result_and_verification() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "skills/search-campaign/" in document
        assert "m1-demo" in document
        assert "d=3/5/7" in document
        assert "0.008, 0.009, 0.01, 0.011, 0.012" in document
        assert "rotated_memory_z" in document
        assert "rounds=3*d" in document
        assert "results/search/rotated-surface-baseline/m1-demo/report.html" in document
        assert "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/" in document
        assert "PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py -q" in document
        assert "PYTHONPATH=src python3 -m autoqec_search.cli validate --root ." in document
        assert "--run-id local-m1-demo --allow-dirty-root" in document


def test_docs_mention_search_strategy_registry() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "search_space.strategy" in document
        assert "autoqec-search compare-strategies" in document
        assert "strategy_trace.json" in document
        assert "rotated-surface-strategy-fixture" in document
        assert "benchmarks/fixtures/strategy-comparison/rotated-surface.json" in document


def test_docs_mention_general_css_eval_path() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "--general-css" in document
        assert "hx/hz -> rstim CSS -> DEM -> decoder" in document
        assert "rotated-surface-css-fixture" in document
        assert "upstream rstim #46/#51" in document
        assert "BB/qLDPC campaigns remain issue #18" in document


def test_issue19_benchmark_skills_and_compare_candidates_are_documented() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "benchmark-code" in document
        assert "bench-runner-distance" in document
        assert "bench-runner-mc-ler" in document
        assert "compare-candidates" in document
        assert "autoqec-search compare-candidates" in document
        assert "task/decoder/p" in document
        assert "Overall winner reporting is strong-only" in document
        assert "BB72 OSD1 smoke" in document
        assert "OSD10" in document


def test_quantum_tanner_autoresearch_workflow_has_runnable_command_blocks() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    blocks = _bash_blocks(document)
    commands = "\n".join(blocks)

    assert "autoqec-search preflight" in document
    assert "python3 -m autoqec_search.cli preflight --root ." in commands
    assert "python3 -m autoqec_search.cli validate --root ." in commands
    assert "python3 -m autoqec_search.cli run --root ." in commands
    assert "--campaign quantum-tanner-autoresearch" in commands
    assert "python3 -m autoqec_search.cli report --root .worktrees/local-qt-p001" in commands
    assert "construction-definitions.html" in document
    assert "python3 -m autoqec_search.cli compare-surface-copy --root .worktrees/local-qt-p001" in commands
    assert "--baseline benchmarks/baselines/rotated-surface-single-logical-p001.json" in commands

    for block in blocks:
        assert "<" not in block
        assert ">" not in block


def test_quantum_tanner_autoresearch_docs_describe_candidate_generator() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    blocks = _bash_blocks(document)
    commands = "\n".join(blocks)

    assert "generate-quantum-tanner-candidates" in document
    assert "campaigns/examples/quantum-tanner-autoresearch/generator.json" in document
    assert QT_GENERATOR_CONFIG.is_file()
    config = load_quantum_tanner_sweep_config(QT_GENERATOR_CONFIG)
    assert config.campaign_id == "quantum-tanner-autoresearch"
    assert config.distances == (4, 6)
    assert (
        "python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root ."
        in commands
    )
    assert "--dry-run" in commands
    assert "--qec-code-bin /path/to/qec-code" in commands
    assert "--force" in commands
    assert "PYTHONPATH=src python3 -m autoqec_search.cli validate --root ." in commands
    assert (
        "does not write specs, matrix artifacts, the distance-ladder manifest, "
        "the fixture catalog, or the search space." in document
    )
    assert "witness finding is a separate later step" in document

    for block in blocks:
        assert "<" not in block
        assert ">" not in block


def test_quantum_tanner_autoresearch_docs_describe_witness_finder_to_autoresearch_path() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    commands = "\n".join(_bash_blocks(document))
    attach_blocks = _attach_witness_blocks(document)
    batch_attach_blocks = [
        block
        for block in attach_blocks
        if "--iterations 1000" in block and "--restarts 8" in block
    ]

    assert "autoqec-search generate-quantum-tanner-candidates" in document
    assert "autoqec-search find-upper-bound-witness" in document
    assert "autoqec-search attach-quantum-tanner-witnesses" in document
    assert "autoqec-search run" in document
    assert "autoqec-search compare-surface-copy" in document
    assert "python3 -m autoqec_search.cli find-upper-bound-witness" in commands
    assert "--basis x" in commands
    assert "--iterations 1000" in commands
    assert "--restarts 8" in commands
    assert "--seed 12345" in commands
    assert batch_attach_blocks
    assert any("--timeout-seconds 300" in block for block in batch_attach_blocks)
    assert any("--require-all" in block for block in attach_blocks)
    assert any("--fail-on-skipped" in block for block in attach_blocks)
    assert "witness_finder_summary.json" in document
    assert "screening.json" in document


def test_quantum_tanner_autoresearch_workflow_states_scientific_guardrails() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    _assert_quantum_tanner_guardrails(document)

    for corrupted in (
        document.replace("p=0.001", "p=0.01"),
        document.replace("1 - (1 - P_single)^k", ""),
        document.replace(
            "upper-bound distances must not be promoted as exact Zoo distances",
            "",
        ),
        document.replace("upper-bound witnesses are screening evidence only", ""),
        document.replace("must not be promoted as exact Zoo distance evidence", ""),
        document.replace("requires generated witnesses to be X-like", ""),
        document.replace("Z-like witnesses can remain valid generic CSS witnesses", ""),
        document.replace("incompatible with this memory-X screening task", ""),
        document.replace("witness_finder_summary.json", ""),
        document.replace("screening.json", ""),
    ):
        try:
            _assert_quantum_tanner_guardrails(corrupted)
        except AssertionError:
            pass
        else:
            raise AssertionError("negative-control mutation unexpectedly passed")
