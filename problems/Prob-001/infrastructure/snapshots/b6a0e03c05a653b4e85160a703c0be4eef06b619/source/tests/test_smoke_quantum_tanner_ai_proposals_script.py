from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "repo"

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {".git", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"}
        ignored.update(name for name in names if name.endswith(".pyc"))
        return ignored & set(names)

    shutil.copytree(REPO_ROOT, work_root, ignore=ignore)
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "autoqec@example.com"],
        ["git", "config", "user.name", "AutoQEC"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "initial"],
    ):
        subprocess.run(command, cwd=work_root, check=True, capture_output=True, text=True)
    return work_root


def _write_fake_qec_code(bin_dir: Path) -> Path:
    executable = bin_dir / "qec-code"
    executable.write_text(
        f"""#!{sys.executable}
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
call_log_value = os.environ.get("FAKE_TOOL_CALL_LOG")
if call_log_value:
    with Path(call_log_value).open("a", encoding="utf-8") as handle:
        handle.write("qec-code " + " ".join(args) + "\\n")
if args == ["--version"]:
    print("error: unexpected argument '--version' found", file=sys.stderr)
    raise SystemExit(2)
if args == ["--help"]:
    if os.environ.get("FAKE_QEC_CODE_PROBE_FAIL") == "1":
        print("intentional qec-code help failure")
        raise SystemExit(9)
    print("Usage: qec-code <COMMAND>")
    raise SystemExit(0)
if args[:5] == ["code", "css", "quantum-tanner", "--spec", args[4]]:
    matrix = args[5]
    if matrix == "hx":
        payload = {{"format": "sparse_rows", "num_cols": 18, "rows": [[i] for i in range(2, 17)]}}
    elif matrix == "hz":
        payload = {{"format": "sparse_rows", "num_cols": 18, "rows": [[17]]}}
    else:
        raise SystemExit(f"unexpected matrix {{matrix}}")
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(0)
if args[:3] == ["code", "css-distance", "random-window-upper-bound"]:
    if os.environ.get("FAKE_QEC_CODE_WITNESS_FAIL") == "1":
        print("intentional witness backend failure", file=sys.stderr)
        raise SystemExit(23)
    hx_path = Path(args[args.index("--hx") + 1])
    hx = json.loads(hx_path.read_text())
    n = int(hx["num_cols"])
    payload = {{
        "status": "completed",
        "method": "random-window-upper-bound",
        "bound_type": "upper",
        "upper_bound": 1,
        "logical_class": "x_like",
        "witness": {{"x": [1] + [0] * (n - 1), "z": [0] * n, "weight": 1}},
        "options": {{"iterations": 32, "restarts": 1, "seed": 12345}},
        "provenance": {{"tool": "fake-qec-code"}},
    }}
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(0)
raise SystemExit(f"unexpected qec-code args: {{args!r}}")
"""
    )
    executable.chmod(0o755)
    return executable


def _write_fake_rsinter(bin_dir: Path, *, name: str = "rsinter") -> Path:
    executable = bin_dir / name
    executable.write_text(
        f"""#!{sys.executable}
import json
import os
import sys
from pathlib import Path
import tomllib

call_log_value = os.environ.get("FAKE_TOOL_CALL_LOG")
if call_log_value:
    with Path(call_log_value).open("a", encoding="utf-8") as handle:
        handle.write("rsinter " + " ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["--version"]:
    print("rsinter git main fake-ai-smoke")
    raise SystemExit(0)

args = sys.argv[1:]
if args[:2] != ["bench", "run"] or "--spec" not in args or "--out" not in args:
    raise SystemExit(2)
spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    if runner["name"] != "rbposd-osd10-v1":
        raise SystemExit(f"unexpected runner: {{runner['name']!r}}")
    params = dict(runner["params"])
    if params.get("p") != [0.001]:
        raise SystemExit(f"unexpected p sweep: {{params.get('p')!r}}")
    row_params = dict(params)
    row_params["p"] = 0.001
    observables_path = spec_path.parent / row_params["observables"]
    observables = json.loads(observables_path.read_text())
    observable_count = len(observables["rows"])
    if observable_count != 2:
        raise SystemExit(f"expected two explicit observables, got {{observable_count}}")
    row_params.update({{
        "logical_failure_aggregation": "any_logical",
        "logical_observable_basis": "x",
        "logical_observable_count": observable_count,
        "logical_observable_source": "explicit",
        "seed": 12345,
        "decoder_impl": "rbposd",
    }})
    results_dir = out_dir / runner["name"] / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    record = {{
        "benchmark": spec["name"],
        "runner": runner["name"],
        "language": runner["language"],
        "status": "ok",
        "params": row_params,
        "case_summary": {{"num_dets": 8, "num_obs": observable_count, "num_shots_generated": 64}},
        "metrics": {{"shots_used": 64, "logical_errors": 0, "logical_error_rate": 0.0, "decode_us_per_shot": 10.0}},
        "artifacts": {{}},
        "error": None,
    }}
    (results_dir / "results.jsonl").write_text(json.dumps(record, sort_keys=True) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return executable


def _write_poison_rsinter(bin_dir: Path) -> Path:
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys

print("poison rsinter basename was used", file=sys.stderr)
raise SystemExit(99)
"""
    )
    executable.chmod(0o755)
    return executable


def _write_fake_tools(tmp_path: Path, *, rsinter_name: str = "rsinter") -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_qec_code(bin_dir)
    _write_fake_rsinter(bin_dir, name=rsinter_name)
    return bin_dir


def _write_fake_codex(bin_dir: Path, repo: Path) -> Path:
    executable = bin_dir / "codex"
    executable.write_text(
        f'''#!{sys.executable}
import json
import os
import re
import sys
import time
from pathlib import Path

args = sys.argv[1:]
tool_call_log_value = os.environ.get("FAKE_TOOL_CALL_LOG")
if tool_call_log_value:
    with Path(tool_call_log_value).open("a", encoding="utf-8") as handle:
        handle.write("codex " + " ".join(args) + "\\n")
if args == ["--version"]:
    print("fake-codex 1.0")
    raise SystemExit(0)
if not args or args[0] != "exec":
    raise SystemExit(f"unexpected Codex args: {{args!r}}")
if "--ephemeral" not in args:
    raise SystemExit("missing --ephemeral")
if "--sandbox" not in args or args[args.index("--sandbox") + 1] != "read-only":
    raise SystemExit("missing --sandbox read-only")
if "--output-schema" not in args:
    raise SystemExit("missing --output-schema")
if "--output-last-message" not in args:
    raise SystemExit("missing --output-last-message")
if args[-1] != "-":
    raise SystemExit("Codex prompt must be stdin")
prompt = sys.stdin.read()
round_match = re.search(r"## round ([0-9]+) requirements", prompt)
if round_match is None:
    raise SystemExit("prompt is missing round requirements")
round_number = int(round_match.group(1))
for required in (
    f"round {{round_number}}",
    "non-toric",
    "inverse-closed",
    "bipartite",
    "local parity-check",
):
    if required not in prompt:
        raise SystemExit(f"prompt is missing {{required!r}}")

call_log_value = os.environ.get("CODEX_CALL_LOG")
if call_log_value:
    call_log = Path(call_log_value)
    call_log.mkdir(parents=True, exist_ok=True)
    call_number = len(list(call_log.glob("*.prompt"))) + 1
    (call_log / f"{{call_number:03d}}.prompt").write_text(prompt)
else:
    call_number = 1
if os.environ.get("FAKE_CODEX_FAIL_ON_CALL") == str(call_number):
    raise SystemExit(f"intentional fake Codex failure on call {{call_number}}")

wait_dir_value = os.environ.get("FAKE_CODEX_WAIT_DIR")
if wait_dir_value:
    wait_dir = Path(wait_dir_value)
    wait_dir.mkdir(parents=True, exist_ok=True)
    (wait_dir / "ready").write_text(str(call_number))
    while not (wait_dir / "release").exists():
        time.sleep(0.02)

fixture_name = (
    "invalid-nonsymmetric-generators.json"
    if os.environ.get("FAKE_CODEX_INVALID_ONLY") == "1"
    else "valid-dihedral-d3.json"
)
proposal = json.loads(
    (Path({str(repo)!r}) / "tests/fixtures/quantum_tanner_proposals" / fixture_name).read_text()
)

def cyclic_proposal(order, proposal_id):
    candidate = json.loads(json.dumps(proposal))
    candidate["proposal_id"] = proposal_id
    candidate["base_group"] = {{
        "name": f"C{{order}}",
        "element_order": f"id = x for x in Z{{order}}",
        "order": order,
        "identity": 0,
        "multiplication_table": [
            [(left + right) % order for right in range(order)]
            for left in range(order)
        ],
    }}
    candidate["a_generator_indices"] = [1, order - 1]
    candidate["b_generator_indices"] = [3, order - 3]
    candidate["search_hints"]["max_group_order"] = 64
    candidate["provenance"]["prompt_summary"] = (
        f"Fake cyclic C{{order}} proposal."
    )
    return candidate

if (
    fixture_name == "valid-dihedral-d3.json"
    and round_number == 2
    and os.environ.get("FAKE_CODEX_REPEAT") != "1"
):
    order = 10
    proposal["proposal_id"] = "valid-cyclic-c10"
    proposal["base_group"] = {{
        "name": "C10",
        "element_order": "id = x for x in Z10",
        "order": order,
        "identity": 0,
        "multiplication_table": [
            [(left + right) % order for right in range(order)]
            for left in range(order)
        ],
    }}
    proposal["a_generator_indices"] = [1, 9]
    proposal["b_generator_indices"] = [3, 7]
    proposal["search_hints"]["max_group_order"] = 32
    proposal["provenance"]["prompt_summary"] = "Second-round cyclic C10 proposal."

if os.environ.get("FAKE_CODEX_ORDER_34") == "1":
    proposals = [cyclic_proposal(34, "valid-cyclic-c34")]
elif os.environ.get("FAKE_CODEX_FOUR_VALID") == "1":
    proposals = [
        cyclic_proposal(order, f"valid-cyclic-c{{order}}")
        for order in (8, 10, 12, 14)
    ]
else:
    proposals = [proposal]
response = {{
    "response_metadata": {{
        "source": "fake-codex",
        "model": "fake-codex",
        "generated_at": "2026-07-10T00:00:00Z",
    }},
    "proposals": proposals,
}}
output_path = Path(args[args.index("--output-last-message") + 1])
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(response, indent=2, sort_keys=True) + "\\n")
'''
    )
    executable.chmod(0o755)
    return executable


def _script_env(bin_dir: Path, *, rsinter_name: str = "rsinter") -> dict[str, str]:
    return {
        **os.environ,
        "QEC_CODE_BIN": str(bin_dir / "qec-code"),
        "RSINTER_BIN": str(bin_dir / rsinter_name),
    }


def _run_long_launcher(
    repo: Path,
    *,
    bin_dir: Path,
    codex_bin: Path,
    work_root: Path,
    rounds: int,
    extra_env: dict[str, str] | None = None,
    max_group_order: int = 32,
    max_physical_qubits: int = 64,
    proposals_per_round: int = 1,
    resume: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
        "--work-root", str(work_root),
        "--rounds", str(rounds),
        "--proposals-per-round", str(proposals_per_round),
        "--max-group-order", str(max_group_order),
        "--max-physical-qubits", str(max_physical_qubits),
        "--run-wall-clock", "90s",
    ]
    if resume:
        command.append("--resume")
    env = {
        **_script_env(bin_dir, rsinter_name="custom-rsinter"),
        "CODEX_BIN": str(codex_bin),
        **(extra_env or {}),
    }
    return subprocess.run(
        command,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def _git_status(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit_without_non_toric_tag(repo: Path) -> None:
    response_path = (
        repo / "tests" / "fixtures" / "quantum_tanner_ai_responses" / "mixed-valid-invalid.json"
    )
    response = json.loads(response_path.read_text())
    tags = response["proposals"][0]["search_hints"]["tags"]
    response["proposals"][0]["search_hints"]["tags"] = [
        tag for tag in tags if tag != "non-toric"
    ]
    response_path.write_text(json.dumps(response, indent=2) + "\n")
    for command in (
        ["git", "add", str(response_path.relative_to(repo))],
        ["git", "commit", "-m", "remove fixture non-toric tag"],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)


def test_ai_proposal_smoke_script_passes_with_fake_backends(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    _commit_without_non_toric_tag(repo)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    _write_poison_rsinter(bin_dir)
    assert _git_status(repo) == ""

    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_ai_proposals.sh"),
            "--work-root",
            str(tmp_path / "smoke"),
        ],
        cwd=repo,
        env=_script_env(bin_dir, rsinter_name="custom-rsinter"),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "poison rsinter basename was used" not in result.stdout + result.stderr
    run_root = (
        tmp_path
        / "smoke"
        / "checkout"
        / ".worktrees"
        / "qt-ai-proposal-smoke"
        / "results"
        / "search"
        / "quantum-tanner-autoresearch"
        / "qt-ai-proposal-smoke"
    )
    assert "PASS quantum_tanner_ai_proposal_smoke" in result.stdout
    assert "proposal_accepted=1" in result.stdout
    assert "proposal_rejected=1" in result.stdout
    assert "non_toric_candidates=1" in result.stdout
    assert "p=0.001" in result.stdout
    assert "surface_copy_status=ok" in result.stdout
    assert "feedback_status=ok" in result.stdout
    assert f"run_root={run_root}" in result.stdout
    assert (
        f"surface_copy_json={run_root / 'surface-copy-comparison.json'}" in result.stdout
    )
    assert f"surface_copy_html={run_root / 'surface-copy-comparison.html'}" in result.stdout
    assert f"feedback_json={run_root / 'quantum-tanner-ai-feedback.json'}" in result.stdout
    assert f"feedback_html={run_root / 'quantum-tanner-ai-feedback.html'}" in result.stdout

    ingest_summary = (
        tmp_path
        / "smoke"
        / "checkout"
        / ".worktrees"
        / "qt-ai-proposal-smoke"
        / "ai-batch"
        / "ingested"
        / "summary.json"
    )
    summary = json.loads(ingest_summary.read_text())
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["accepted_records"][0]["proposal_id"] == "ai-valid-dihedral-d3"
    assert summary["rejected_records"][0]["proposal_id"] == "ai-invalid-nonsymmetric-generators"
    assert summary["response_path"].endswith(
        "tests/fixtures/quantum_tanner_ai_responses/mixed-valid-invalid.json"
    )

    search_space = json.loads(
        (
            tmp_path
            / "smoke"
            / "checkout"
            / "campaigns"
            / "examples"
            / "quantum-tanner-autoresearch"
            / "search_space.json"
        ).read_text()
    )
    assert len(search_space["candidate_specs"]) == 1
    assert search_space["candidate_specs"][0]["candidate_id"] == "ai-valid-dihedral-d3"
    assert (
        search_space["candidate_specs"][0]["provenance"]["kind"] == "proposal-derived"
    )

    instance_dir = (
        tmp_path
        / "smoke"
        / "checkout"
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "proposal-instances"
        / "ai-valid-dihedral-d3"
    )
    hx_payload = json.loads((instance_dir / "hx.json").read_text())
    hz_payload = json.loads((instance_dir / "hz.json").read_text())
    assert hx_payload == {
        "format": "sparse_rows",
        "num_cols": 18,
        "rows": [[i] for i in range(2, 17)],
    }
    assert hz_payload == {"format": "sparse_rows", "num_cols": 18, "rows": [[17]]}

    run_root = (
        tmp_path
        / "smoke"
        / "checkout"
        / ".worktrees"
        / "qt-ai-proposal-smoke"
        / "results"
        / "search"
        / "quantum-tanner-autoresearch"
        / "qt-ai-proposal-smoke"
    )
    assert json.loads((run_root / "run_status.json").read_text())["status"] == "finalized"
    assert json.loads((run_root / "surface-copy-comparison.json").read_text())["status"] == "ok"
    feedback = json.loads((run_root / "quantum-tanner-ai-feedback.json").read_text())
    assert feedback["counts"]["p001_ler_rows"] == 1
    assert feedback["counts"]["rejected_proposals"] == 1
    assert "ai-valid-dihedral-d3" in feedback["next_prompt_context"][
        "candidate_ids_with_p001_ler"
    ]
    assert feedback["rejected_proposals"][0]["proposal_id"] == "ai-invalid-nonsymmetric-generators"
    assert _git_status(repo) == ""


def test_ai_proposal_smoke_script_rejects_work_root_inside_checkout(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path)

    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_ai_proposals.sh"),
            "--work-root",
            str(repo / "smoke"),
        ],
        cwd=repo,
        env=_script_env(bin_dir),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "outside the caller checkout" in result.stderr
    assert not (repo / "smoke").exists()
    assert _git_status(repo) == ""


def test_ai_proposal_smoke_script_rejects_toric_only_response(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path)

    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_ai_proposals.sh"),
            "--work-root",
            str(tmp_path / "toric-only"),
            "--check-toric-only-response",
        ],
        cwd=repo,
        env=_script_env(bin_dir),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "KnownToricTemplateDuplicate" in result.stdout + result.stderr
    ingest_summary = (
        tmp_path
        / "toric-only"
        / "checkout"
        / ".worktrees"
        / "qt-ai-proposal-smoke"
        / "ai-batch"
        / "ingested"
        / "summary.json"
    )
    summary = json.loads(ingest_summary.read_text())
    assert summary["accepted"] == 0
    assert summary["rejected"] == 1
    assert summary["rejected_records"][0]["error_kind"] == "KnownToricTemplateDuplicate"
    assert _git_status(repo) == ""


def test_ai_proposal_smoke_script_toric_only_mode_does_not_require_backends(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    missing_env = {
        **os.environ,
        "QEC_CODE_BIN": str(tmp_path / "missing-qec-code"),
        "RSINTER_BIN": str(tmp_path / "missing-rsinter"),
    }

    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_ai_proposals.sh"),
            "--work-root",
            str(tmp_path / "toric-only-no-backends"),
            "--check-toric-only-response",
        ],
        cwd=repo,
        env=missing_env,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "KnownToricTemplateDuplicate" in output
    assert "executable is not executable" not in output
    assert "executable not found" not in output
    assert _git_status(repo) == ""


def test_long_run_launcher_completes_one_round_with_fake_tools(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    (repo / "uncommitted-operator-note.txt").write_text("not part of the run\n")
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    tool_call_log = tmp_path / "tool-calls.log"
    result = subprocess.run(
        [
            str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
            "--work-root", str(work_root),
            "--rounds", "1",
            "--proposals-per-round", "1",
            "--max-group-order", "32",
            "--max-physical-qubits", "64",
            "--run-wall-clock", "90s",
        ],
        cwd=repo,
        env={
            **_script_env(bin_dir, rsinter_name="custom-rsinter"),
            "CODEX_BIN": str(codex_bin),
            "FAKE_TOOL_CALL_LOG": str(tool_call_log),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source checkout is dirty; uncommitted changes are excluded" in result.stderr
    state = json.loads((work_root / "state.json").read_text())
    assert state["status"] == "completed"
    assert state["next_round"] == 2
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    status = json.loads((attempt / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["accepted"] == 1
    assert Path(status["feedback_json"]).is_file()
    assert Path(status["surface_copy_json"]).is_file()
    proposal_fingerprint = json.loads(
        (attempt / "ingested" / "summary.json").read_text()
    )["accepted_fingerprints"][0]
    assert state["accepted_fingerprints"] == [proposal_fingerprint]
    cumulative_feedback = json.loads(
        (work_root / "cumulative-feedback.json").read_text()
    )
    assert cumulative_feedback["accepted_fingerprints"] == [proposal_fingerprint]
    aggregate = work_root / "aggregate"
    records = [
        json.loads(line)
        for line in (aggregate / "results.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["status"] == "evaluated"
    assert records[0]["benchmark"]["shots"] == 64
    assert (aggregate / "report.html").read_text().count(
        'data-candidate-row="true"'
    ) == 1
    assert state["aggregate_ledger"] == str(aggregate / "results.jsonl")
    assert state["aggregate_report"] == str(aggregate / "report.html")
    assert f"aggregate_report={aggregate / 'report.html'}" in result.stdout
    assert not (attempt / "checkout" / "uncommitted-operator-note.txt").exists()
    tool_calls = tool_call_log.read_text().splitlines()
    assert tool_calls[:3] == [
        "codex --version",
        "qec-code --help",
        "rsinter --version",
    ]


def test_long_run_propagates_order_34_limit_through_materialization(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-order-34"

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        max_group_order=64,
        max_physical_qubits=64,
        extra_env={"FAKE_CODEX_ORDER_34": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    summary = json.loads((attempt / "ingested" / "summary.json").read_text())
    assert summary["accepted"] == 1
    accepted_path = attempt / "ingested" / summary["accepted_records"][0]["path"]
    assert json.loads(accepted_path.read_text())["base_group"]["order"] == 34
    materialized = (
        attempt
        / "checkout"
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "proposal-instances"
        / "valid-cyclic-c34"
        / "instance.json"
    )
    assert materialized.is_file()
    assert json.loads((attempt / "status.json").read_text())["status"] == "completed"


def test_long_run_evaluates_all_four_accepted_proposals(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-four"

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        proposals_per_round=4,
        max_group_order=64,
        extra_env={"FAKE_CODEX_FOUR_VALID": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    summary = json.loads((attempt / "ingested" / "summary.json").read_text())
    accepted_fingerprints = set(summary["accepted_fingerprints"])
    assert summary["accepted"] == 4
    assert len(accepted_fingerprints) == 4

    attempt_campaign = json.loads(
        (
            attempt
            / "checkout"
            / "campaigns"
            / "examples"
            / "quantum-tanner-autoresearch"
            / "campaign.json"
        ).read_text()
    )
    assert attempt_campaign["budget"]["max_candidates"] == 4
    assert attempt_campaign["stop_conditions"]["max_candidates"] == 4
    committed_campaign = json.loads(
        (
            repo
            / "campaigns"
            / "examples"
            / "quantum-tanner-autoresearch"
            / "campaign.json"
        ).read_text()
    )
    assert committed_campaign["budget"]["max_candidates"] == 3
    assert committed_campaign["stop_conditions"]["max_candidates"] == 3

    status = json.loads((attempt / "status.json").read_text())
    run_root = Path(status["run_root"])
    feedback = json.loads(
        (run_root / "quantum-tanner-ai-feedback.json").read_text()
    )
    assert {
        candidate["proposal_fingerprint"]
        for candidate in feedback["candidates"]
    } == accepted_fingerprints
    for accepted_record in summary["accepted_records"]:
        candidate_id = accepted_record["proposal_id"]
        candidate_root = run_root / "candidates" / candidate_id
        assert json.loads((candidate_root / "candidate.json").read_text())["status"] == "evaluated"
        manifest = json.loads(
            (
                candidate_root
                / "evaluations"
                / "quantum-tanner-css-memory-x-rbposd-p001-v1"
                / "rbposd-osd10-v1"
                / "manifest.json"
            ).read_text()
        )
        assert manifest["status"] == "completed"


def test_long_run_uses_clean_head_orchestrator_and_cleans_bootstrap(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    launcher_module = repo / "src" / "autoqec_search" / "quantum_tanner_long_run.py"
    launcher_module.write_text(
        launcher_module.read_text().replace(
            "from collections.abc import Iterator",
            'raise RuntimeError("dirty live launcher was imported")\n\n'
            "from collections.abc import Iterator",
            1,
        )
    )
    bootstrap_tmp = tmp_path / "bootstrap-tmp"
    bootstrap_tmp.mkdir()

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=tmp_path / "long-run-clean-head",
        rounds=1,
        extra_env={"TMPDIR": str(bootstrap_tmp)},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "source checkout is dirty; uncommitted changes are excluded" in result.stderr
    assert "dirty live launcher was imported" not in result.stdout + result.stderr
    leaked_bootstraps = [
        path for path in bootstrap_tmp.iterdir()
        if path.name.startswith("autoqec-quantum-tanner.")
    ]
    assert leaked_bootstraps == []


def test_long_run_resume_rejects_moved_source_head_before_tools(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-moved-head"
    tool_call_log = tmp_path / "tool-calls.log"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"FAKE_TOOL_CALL_LOG": str(tool_call_log)},
    )
    assert first.returncode == 0, first.stdout + first.stderr
    calls_before_resume = tool_call_log.read_text()
    (repo / "moved-head-marker.txt").write_text("move source HEAD\n")
    subprocess.run(
        ["git", "add", "moved-head-marker.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "move source head"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"FAKE_TOOL_CALL_LOG": str(tool_call_log)},
        resume=True,
    )

    assert resumed.returncode != 0
    assert "source HEAD differs from pinned source_commit" in resumed.stderr
    assert tool_call_log.read_text() == calls_before_resume
    assert not (
        work_root / "rounds" / "round-0001" / "attempt-002"
    ).exists()


def test_long_run_all_invalid_response_completes_without_numerical_run(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-invalid"
    result = subprocess.run(
        [
            str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
            "--work-root", str(work_root),
            "--rounds", "1",
            "--proposals-per-round", "1",
            "--max-group-order", "32",
            "--max-physical-qubits", "64",
            "--run-wall-clock", "90s",
        ],
        cwd=repo,
        env={
            **_script_env(bin_dir, rsinter_name="custom-rsinter"),
            "CODEX_BIN": str(codex_bin),
            "FAKE_CODEX_INVALID_ONLY": "1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    status = json.loads((attempt / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["accepted"] == 0
    assert status["run_root"] is None
    assert not (attempt / "checkout" / ".worktrees").exists()


def test_long_run_launcher_uses_fresh_codex_rounds_and_cumulative_feedback(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=2,
        extra_env={"CODEX_CALL_LOG": str(call_log)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((work_root / "state.json").read_text())
    first_prompt = (call_log / "001.prompt").read_text()
    second_prompt = (call_log / "002.prompt").read_text()
    first_fingerprint = state["completed_rounds"][0]["accepted_fingerprints"][0]
    assert 'accepted_fingerprints": []' in first_prompt
    assert "accepted_fingerprints" in second_prompt
    assert first_fingerprint in second_prompt
    assert "Quantum Tanner aggregate candidate history" in second_prompt
    aggregate_records = [
        json.loads(line)
        for line in (work_root / "aggregate" / "results.jsonl").read_text().splitlines()
    ]
    assert [record["round"] for record in aggregate_records] == [1, 2]
    assert [
        record["proposal_fingerprint"] for record in aggregate_records
    ] == state["accepted_fingerprints"]
    assert (work_root / "rounds" / "round-0002" / "attempt-001").is_dir()
    assert len(state["completed_rounds"]) == 2
    assert set(state["completed_rounds"][0]) == {
        "accepted",
        "accepted_fingerprints",
        "attempt",
        "feedback_json",
        "proposal_summary_path",
        "rejected",
        "round",
        "run_root",
        "surface_copy_json",
    }


def test_resume_preserves_failed_attempt_and_creates_next_attempt(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "FAKE_CODEX_FAIL_ON_CALL": "1",
            "CODEX_CALL_LOG": str(call_log),
        },
    )
    assert first.returncode != 0
    round_root = work_root / "rounds" / "round-0001"
    failed_status = json.loads(
        (round_root / "attempt-001" / "status.json").read_text()
    )
    assert failed_status["status"] == "failed"
    assert failed_status["failed_stage"] == "prompted"
    assert failed_status["error_kind"] == "SearchIntegrityError"
    assert "command failed" in failed_status["message"]
    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"CODEX_CALL_LOG": str(call_log)},
        resume=True,
    )
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert (round_root / "attempt-001" / "status.json").is_file()
    assert (round_root / "attempt-002" / "status.json").is_file()
    assert json.loads(
        (round_root / "attempt-002" / "status.json").read_text()
    )["status"] == "completed"


def test_historical_duplicate_stops_before_qec_code(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=2,
        extra_env={
            "FAKE_CODEX_REPEAT": "1",
            "CODEX_CALL_LOG": str(tmp_path / "codex-calls"),
        },
    )
    assert result.returncode != 0
    assert "historical proposal fingerprint" in result.stderr
    second_checkout = (
        work_root
        / "rounds"
        / "round-0002"
        / "attempt-001"
        / "checkout"
    )
    assert not (
        second_checkout
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "proposal-instances"
    ).exists()


def test_long_run_appends_witness_failed_code_before_returning_nonzero(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "failed-aggregate"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"FAKE_QEC_CODE_WITNESS_FAIL": "1"},
    )

    assert result.returncode != 0
    records = [
        json.loads(line)
        for line in (work_root / "aggregate" / "results.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["candidate_id"] == "valid-dihedral-d3"
    assert records[0]["status"] == "failed"
    assert "witness" in records[0]["reason"]
    assert 'class="badge failed"' in (
        work_root / "aggregate" / "report.html"
    ).read_text()


def test_long_run_new_run_rejects_non_empty_work_root(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    work_root.mkdir()
    marker = work_root / "operator-note.txt"
    marker.write_text("preserve me\n")

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
    )

    assert result.returncode != 0
    assert "work root must be empty for a new run" in result.stderr
    assert marker.read_text() == "preserve me\n"
    assert not (work_root / "state.json").exists()


def test_long_run_retries_same_root_after_tool_probe_failure(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-preflight-retry"

    failed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"FAKE_QEC_CODE_PROBE_FAIL": "1"},
    )

    assert failed.returncode != 0
    assert "command failed (9)" in failed.stderr
    assert not (work_root / "state.json").exists()
    assert not (work_root / "rounds").exists()
    prestate_entries = {path.name for path in work_root.iterdir()}
    assert "toolchain" in prestate_entries
    assert prestate_entries <= {".launcher.lock", "toolchain"}

    retried = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
    )

    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert json.loads((work_root / "state.json").read_text())["status"] == "completed"
    assert (
        work_root / "rounds" / "round-0001" / "attempt-001" / "status.json"
    ).is_file()


@pytest.mark.parametrize(
    "alias_kind",
    [
        "lock-symlink",
        "lock-hardlink",
        "toolchain-symlink",
        "version-log-symlink",
        "version-log-hardlink",
        "tool-shims-symlink",
    ],
)
def test_long_run_rejects_prestate_aliases_without_touching_external_target(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-unsafe-prestate"
    work_root.mkdir()
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_target = tmp_path / "external-target.txt"
    external_target.write_bytes(b"external-bytes-must-survive\n")

    if alias_kind in {"lock-symlink", "lock-hardlink"}:
        lock_path = work_root / ".launcher.lock"
        if alias_kind == "lock-symlink":
            lock_path.symlink_to(external_target)
        else:
            os.link(external_target, lock_path)
    elif alias_kind == "toolchain-symlink":
        (external_dir / "codex-version.log").write_bytes(
            external_target.read_bytes()
        )
        external_target = external_dir / "codex-version.log"
        (work_root / "toolchain").symlink_to(
            external_dir,
            target_is_directory=True,
        )
    elif alias_kind in {"version-log-symlink", "version-log-hardlink"}:
        toolchain_dir = work_root / "toolchain"
        toolchain_dir.mkdir()
        version_log = toolchain_dir / "codex-version.log"
        if alias_kind == "version-log-symlink":
            version_log.symlink_to(external_target)
        else:
            os.link(external_target, version_log)
    elif alias_kind == "tool-shims-symlink":
        (external_dir / "rsinter").symlink_to(external_target)
        (work_root / "tool-shims").symlink_to(
            external_dir,
            target_is_directory=True,
        )
    else:  # pragma: no cover - parameter list is exhaustive
        raise AssertionError(alias_kind)
    external_bytes = external_target.read_bytes()

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
    )

    assert result.returncode != 0
    assert external_target.read_bytes() == external_bytes
    assert not (work_root / "state.json").exists()
    assert not (work_root / "rounds").exists()


def test_long_run_work_root_lock_rejects_concurrent_resume(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-locked"
    wait_dir = tmp_path / "codex-wait"
    command = [
        str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
        "--work-root", str(work_root),
        "--rounds", "1",
        "--proposals-per-round", "1",
        "--max-group-order", "32",
        "--max-physical-qubits", "64",
        "--run-wall-clock", "90s",
    ]
    first = subprocess.Popen(
        command,
        cwd=repo,
        env={
            **_script_env(bin_dir, rsinter_name="custom-rsinter"),
            "CODEX_BIN": str(codex_bin),
            "FAKE_CODEX_WAIT_DIR": str(wait_dir),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_stdout = ""
    first_stderr = ""
    try:
        deadline = time.monotonic() + 20
        while not (wait_dir / "ready").is_file():
            if first.poll() is not None:
                first_stdout, first_stderr = first.communicate()
                raise AssertionError(
                    "first launcher exited before reaching fake Codex: "
                    + first_stdout
                    + first_stderr
                )
            if time.monotonic() >= deadline:
                raise AssertionError("first launcher did not reach fake Codex")
            time.sleep(0.02)

        second = _run_long_launcher(
            repo,
            bin_dir=bin_dir,
            codex_bin=codex_bin,
            work_root=work_root,
            rounds=1,
            resume=True,
        )
    finally:
        wait_dir.mkdir(parents=True, exist_ok=True)
        (wait_dir / "release").write_text("release\n")
        if first.poll() is None:
            first_stdout, first_stderr = first.communicate(timeout=30)

    assert second.returncode != 0
    assert "work root is locked by another launcher" in second.stderr
    assert first.returncode == 0, first_stdout + first_stderr
    round_root = work_root / "rounds" / "round-0001"
    assert sorted(path.name for path in round_root.glob("attempt-*")) == [
        "attempt-001"
    ]


def test_long_run_resume_requires_state_json(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"

    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        resume=True,
    )

    assert result.returncode != 0
    assert "resume requires existing state.json" in result.stderr
    assert {path.name for path in work_root.iterdir()} == {".launcher.lock"}


def test_resume_reconciles_completed_attempt_without_rerunning_round(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    tool_call_log = tmp_path / "tool-calls.log"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "CODEX_CALL_LOG": str(call_log),
            "FAKE_TOOL_CALL_LOG": str(tool_call_log),
        },
    )
    assert first.returncode == 0, first.stdout + first.stderr
    completed_state = json.loads((work_root / "state.json").read_text())
    first_fingerprint = completed_state["accepted_fingerprints"][0]
    stale_state = {
        **completed_state,
        "accepted_fingerprints": [],
        "completed_rounds": [],
        "next_round": 1,
        "rejection_kinds": {},
        "status": "running",
    }
    (work_root / "state.json").write_text(json.dumps(stale_state))
    (work_root / "cumulative-feedback.json").write_text(
        json.dumps({"accepted_fingerprints": [], "rejection_kinds": {}})
    )
    status_path = (
        work_root
        / "rounds"
        / "round-0001"
        / "attempt-001"
        / "status.json"
    )
    feedback_complete_status = json.loads(status_path.read_text())
    feedback_complete_status["stage"] = "feedback_completed"
    feedback_complete_status["status"] = "running"
    status_path.write_text(json.dumps(feedback_complete_status))
    tool_calls_before_resume = tool_call_log.read_text()

    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "CODEX_CALL_LOG": str(call_log),
            "FAKE_TOOL_CALL_LOG": str(tool_call_log),
        },
        resume=True,
    )

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert sorted(path.name for path in call_log.glob("*.prompt")) == ["001.prompt"]
    assert tool_call_log.read_text() == tool_calls_before_resume
    round_root = work_root / "rounds" / "round-0001"
    assert not (round_root / "attempt-002").exists()
    reconciled_state = json.loads((work_root / "state.json").read_text())
    assert reconciled_state["next_round"] == 2
    assert reconciled_state["accepted_fingerprints"] == [first_fingerprint]
    assert reconciled_state["completed_rounds"][0]["attempt"] == 1
    assert json.loads(status_path.read_text())["status"] == "completed"


def test_resume_rebuilds_missing_aggregate_without_rerunning_tools(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    tool_call_log = tmp_path / "tool-calls.log"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "CODEX_CALL_LOG": str(call_log),
            "FAKE_TOOL_CALL_LOG": str(tool_call_log),
        },
    )
    assert first.returncode == 0, first.stdout + first.stderr
    codex_calls_before = sorted(path.read_text() for path in call_log.glob("*.prompt"))
    tool_calls_before = tool_call_log.read_text()

    shutil.rmtree(work_root / "aggregate")
    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "CODEX_CALL_LOG": str(call_log),
            "FAKE_TOOL_CALL_LOG": str(tool_call_log),
        },
        resume=True,
    )

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    records = [
        json.loads(line)
        for line in (work_root / "aggregate" / "results.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["status"] == "evaluated"
    assert (
        work_root / "aggregate" / "report.html"
    ).read_text().count('data-candidate-row="true"') == 1
    assert sorted(path.read_text() for path in call_log.glob("*.prompt")) == (
        codex_calls_before
    )
    assert tool_call_log.read_text() == tool_calls_before


def test_cumulative_feedback_ahead_of_state_blocks_historical_duplicate(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"CODEX_CALL_LOG": str(call_log)},
    )
    assert first.returncode == 0, first.stdout + first.stderr
    stale_state = json.loads((work_root / "state.json").read_text())
    stale_state["accepted_fingerprints"] = []
    (work_root / "state.json").write_text(json.dumps(stale_state))
    (work_root / "cumulative-feedback.json").write_text(
        json.dumps(
            {
                "accepted_fingerprints": [],
                "completed_attempts": [],
                "rejection_kinds": {},
            }
        )
    )
    aggregate_ledger = work_root / "aggregate" / "results.jsonl"
    ledger_before = aggregate_ledger.read_text()

    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=2,
        extra_env={
            "CODEX_CALL_LOG": str(call_log),
            "FAKE_CODEX_REPEAT": "1",
        },
        resume=True,
    )

    assert resumed.returncode != 0
    assert "historical proposal fingerprint" in resumed.stderr
    assert sorted(path.name for path in call_log.glob("*.prompt")) == [
        "001.prompt",
        "002.prompt",
    ]
    second_checkout = (
        work_root
        / "rounds"
        / "round-0002"
        / "attempt-001"
        / "checkout"
    )
    assert not (
        second_checkout
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "proposal-instances"
    ).exists()
    assert aggregate_ledger.read_text() == ledger_before
