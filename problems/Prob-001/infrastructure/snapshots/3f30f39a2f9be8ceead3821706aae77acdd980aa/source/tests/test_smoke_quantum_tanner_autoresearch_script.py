from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "repo"

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {".git", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"}
        ignored.update(name for name in names if name.endswith(".pyc"))
        return ignored & set(names)

    shutil.copytree(REPO_ROOT, work_root, ignore=ignore)
    subprocess.run(
        ["git", "init"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "autoqec@example.com"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AutoQEC"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=work_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return work_root


def _write_fake_distance_ladder(bin_dir: Path) -> Path:
    executable = bin_dir / "autoqec-distance-ladder"
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path

args = sys.argv[1:]
manifest_path = Path(args[args.index("--manifest") + 1])
repo_root = manifest_path.parents[2]
manifest = json.loads(manifest_path.read_text())
artifact_root = (manifest_path.parent / manifest["artifact_root"]).resolve()
for entry in manifest["entries"]:
    candidate_id = entry["instance_id"]
    n = int(entry["n"])
    d = int(entry["expected_distance"])
    instance_dir = artifact_root / candidate_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    spec_path = (manifest_path.parent / entry["quantum_tanner_spec"]).resolve()
    instance = {{
        "instance_id": candidate_id,
        "id": candidate_id,
        "code_id": entry["code_id"],
        "n": n,
        "k": 2,
        "expected_distance": d,
        "expected_bound_type": "exact",
        "qec_code_spec": entry["qec_code_spec"],
        "quantum_tanner_spec": str(spec_path.relative_to(repo_root)),
        "derived_properties": {{"distance": d}},
        "parameters": {{"distance": d}},
        "artifacts": {{"hx": "hx.json", "hz": "hz.json"}},
        "generator": {{"tool": "qec-code"}},
    }}
    hx = {{"format": "sparse_rows", "num_cols": n, "rows": [[i] for i in range(2, n)]}}
    hz = {{"format": "sparse_rows", "num_cols": n, "rows": []}}
    (instance_dir / "instance.json").write_text(json.dumps(instance, indent=2) + "\\n")
    (instance_dir / "hx.json").write_text(json.dumps(hx, indent=2) + "\\n")
    (instance_dir / "hz.json").write_text(json.dumps(hz, indent=2) + "\\n")
print("fake distance ladder export")
"""
    )
    executable.chmod(0o755)
    return executable


def _write_fake_qec_code(bin_dir: Path) -> Path:
    executable = bin_dir / "qec-code"
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path

args = sys.argv[1:]
hx_path = Path(args[args.index("--hx") + 1])
hx = json.loads(hx_path.read_text())
n = int(hx["num_cols"])
weight = 4 if n == 16 else 6
x = [0] * n
x[0] = 1
for index in range(2, 2 + weight - 1):
    x[index] = 1
payload = {{
    "status": "completed",
    "method": "random-window-upper-bound",
    "bound_type": "upper",
    "upper_bound": weight,
    "logical_class": "x_like",
    "witness": {{"x": x, "z": [0] * n, "weight": weight}},
    "options": {{"iterations": 1000, "restarts": 8, "seed": 12345}},
    "provenance": {{"tool": "fake-qec-code"}},
}}
print(json.dumps(payload, sort_keys=True))
"""
    )
    executable.chmod(0o755)
    return executable


def _write_fake_rsinter(bin_dir: Path) -> Path:
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path
import tomllib

if sys.argv[1:] == ["--version"]:
    print("rsinter git main fake-smoke")
    raise SystemExit(0)

args = sys.argv[1:]
if args[:2] != ["bench", "run"] or "--spec" not in args or "--out" not in args:
    raise SystemExit(2)

spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    params = dict(runner["params"])
    p_values = params.get("p")
    if p_values != [0.001]:
        raise SystemExit(f"unexpected p sweep: {{p_values!r}}")
    row_params = dict(params)
    row_params["p"] = 0.001
    observable_count = 0
    if "observables" in row_params:
        observables_path = spec_path.parent / row_params["observables"]
        observables = json.loads(observables_path.read_text())
        observable_count = len(observables["rows"])
        if observable_count != 2:
            raise SystemExit(f"expected two explicit observables, got {{observable_count}}")
        row_params.update(
            {{
                "logical_failure_aggregation": "any_logical",
                "logical_observable_basis": "x",
                "logical_observable_count": observable_count,
                "logical_observable_source": "explicit",
                "seed": 12345,
                "decoder_impl": "rbposd",
            }}
        )
    results_dir = out_dir / runner["name"] / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    record = {{
        "benchmark": spec["name"],
        "runner": runner["name"],
        "language": runner["language"],
        "status": "ok",
        "params": row_params,
        "case_summary": {{
            "num_dets": 8,
            "num_obs": observable_count,
            "num_shots_generated": 64,
            "logical_observable_count": observable_count,
        }},
        "metrics": {{
            "shots_used": 64,
            "logical_errors": 0,
            "logical_error_rate": 0.0,
            "decode_us_per_shot": 10.0,
        }},
        "artifacts": {{}},
        "error": None,
    }}
    (results_dir / "results.jsonl").write_text(json.dumps(record, sort_keys=True) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return executable


def _write_fake_tools(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_fake_distance_ladder(bin_dir)
    _write_fake_qec_code(bin_dir)
    _write_fake_rsinter(bin_dir)
    return bin_dir


def _script_env(bin_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "QEC_CODE_BIN": str(bin_dir / "qec-code"),
        "RSINTER_BIN": str(bin_dir / "rsinter"),
    }


def test_smoke_quantum_tanner_autoresearch_script_prints_pass_summary(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path)
    work_root = tmp_path / "smoke"
    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_autoresearch.sh"),
            "--work-root",
            str(work_root),
        ],
        cwd=repo,
        env=_script_env(bin_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for expected in (
        "PASS quantum_tanner_autoresearch_smoke",
        "frontier_size=2",
        "crashes=0",
        "quantum-tanner-toric-d4 p=0.001 ler=0",
        "quantum-tanner-toric-d6 p=0.001 ler=0",
        "surface_copy_status=ok",
        "surface_copy_rows=2",
        "surface_copy_accepted=1",
        "surface_copy_rejected=1",
    ):
        assert expected in result.stdout
    run_root = (
        work_root
        / "checkout"
        / ".worktrees"
        / "qt-smoke"
        / "results"
        / "search"
        / "quantum-tanner-autoresearch"
        / "qt-smoke"
    )
    assert json.loads((run_root / "run_status.json").read_text())["status"] == "finalized"
    assert json.loads((run_root / "surface-copy-comparison.json").read_text())[
        "status"
    ] == "ok"
    report_html = (run_root / "report.html").read_text()
    definitions_html = (run_root / "construction-definitions.html").read_text()
    assert "Quantum Tanner Benchmark Summary" in report_html
    assert report_html.count('data-candidate-row="true"') == 2
    assert "Quantum Tanner Candidate Construction Definitions" in definitions_html
    assert "Construction metadata unavailable" not in definitions_html


def test_smoke_quantum_tanner_bad_observables_check_prints_negative_control(
    tmp_path: Path,
) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path)
    result = subprocess.run(
        [
            str(repo / "scripts" / "smoke_quantum_tanner_autoresearch.sh"),
            "--work-root",
            str(tmp_path / "bad-observables"),
            "--check-bad-observables",
        ],
        cwd=repo,
        env=_script_env(bin_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "negative_control=ok" in result.stdout
    assert "explicit X observables define 1 rows, expected k = 2" in result.stdout
