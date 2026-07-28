from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.upper_bound_witness_finder import (
    convert_qec_code_random_window_upper_bound_result,
    run_qec_code_random_window_upper_bound_css_witness,
    run_qec_code_random_window_upper_bound,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "benchmarks" / "fixtures" / "upper-bound-witness"
QEC_CODE_FIXTURE_ROOT = FIXTURE_ROOT / "qec-code"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_fake_qec_code(path: Path) -> Path:
    script = """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

args_path = os.environ.get("AUTOQEC_FAKE_QEC_CODE_ARGS")
if args_path:
    Path(args_path).write_text(json.dumps(sys.argv[1:]) + "\\n")

sleep_seconds = os.environ.get("AUTOQEC_FAKE_QEC_CODE_SLEEP")
if sleep_seconds:
    time.sleep(float(sleep_seconds))

stderr_text = os.environ.get("AUTOQEC_FAKE_QEC_CODE_STDERR", "")
if stderr_text:
    sys.stderr.write(stderr_text)

stdout_text = os.environ.get("AUTOQEC_FAKE_QEC_CODE_STDOUT")
payload_path = os.environ.get("AUTOQEC_FAKE_QEC_CODE_PAYLOAD")
if stdout_text is not None:
    sys.stdout.write(stdout_text)
elif payload_path:
    sys.stdout.write(Path(payload_path).read_text())

sys.exit(int(os.environ.get("AUTOQEC_FAKE_QEC_CODE_EXIT", "0")))
"""
    path.write_text(script)
    path.chmod(0o755)
    return path


def test_run_qec_code_random_window_upper_bound_converts_completed_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    args_path = tmp_path / "args.json"
    hx_path = FIXTURE_ROOT / "hx.json"
    hz_path = FIXTURE_ROOT / "hz.json"

    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_ARGS", str(args_path))
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )

    result = run_qec_code_random_window_upper_bound(
        hx_path,
        hz_path,
        qec_code_bin=str(fake_qec_code),
        iterations=16,
        restarts=3,
        seed=61,
        target_weight=2,
        timeout_seconds=5,
    )

    assert result["method"] == "random-window-upper-bound"
    assert result["bound_type"] == "upper"
    assert result["status"] == "completed"
    assert result["upper_bound"] == 2
    assert result["logical_class"] == "x_like"
    assert isinstance(result["witness"], dict)
    assert result["witness"]
    assert isinstance(result["options"], dict)
    assert isinstance(result["provenance"], dict)
    assert json.loads(args_path.read_text()) == [
        "code",
        "css-distance",
        "random-window-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--iterations",
        "16",
        "--restarts",
        "3",
        "--seed",
        "61",
        "--target-weight",
        "2",
        "--json",
    ]


def test_run_qec_code_random_window_upper_bound_preserves_search_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["search_stats"] = {
        "attempts": 4,
        "frontier_size": 2,
        "notes": {"accepted": True, "label": "contract-check"},
    }
    payload_path = tmp_path / "completed-with-search-stats.json"
    payload_path.write_text(json.dumps(payload) + "\n")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_PAYLOAD", str(payload_path))

    result = run_qec_code_random_window_upper_bound(
        FIXTURE_ROOT / "hx.json",
        FIXTURE_ROOT / "hz.json",
        qec_code_bin=str(fake_qec_code),
        iterations=16,
        restarts=3,
        seed=61,
        target_weight=2,
        timeout_seconds=5,
    )

    assert result["search_stats"] == payload["search_stats"]


def test_convert_qec_code_random_window_upper_bound_result_converts_x_like_fixture() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    assert result["status"] == "completed"
    assert result["witness_payload"] == {"basis": "x", "vector": [0, 0, 1, 1]}
    assert result["distance_payload"] == {
        "status": "completed",
        "method": "css-upper-bound-witness",
        "bound_type": "upper",
        "upper_bound": 2,
        "basis": "x",
    }
    assert result["verification"]["status"] == "pass"
    assert result["qec_code_result"] == payload


def test_convert_qec_code_random_window_upper_bound_result_converts_z_like_fixture() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-z-completed.json")
    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    assert result["witness_payload"] == {"basis": "z", "vector": [1, 1, 0, 0]}
    assert result["distance_payload"]["upper_bound"] == 2
    assert result["distance_payload"]["basis"] == "z"


def test_convert_qec_code_random_window_upper_bound_result_copies_qec_code_result_sidecar() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    payload["witness"]["x"][0] = 1
    payload["options"]["seed"] = 999
    payload["provenance"]["generated_by"] = "mutated-tool"

    assert result["qec_code_result"]["witness"]["x"] == [0, 0, 1, 1]
    assert result["qec_code_result"]["options"]["seed"] != 999
    assert result["qec_code_result"]["provenance"]["generated_by"] != "mutated-tool"


@pytest.mark.parametrize(
    ("fixture_name", "expected_error"),
    [
        ("mixed-logical-class.json", "unsupported_logical_class"),
        ("upper-bound-weight-mismatch.json", "upper_bound_weight_mismatch"),
        ("x-z-width-mismatch.json", "x_z_width_mismatch"),
        ("non-binary-witness-entry.json", "non_binary_witness_entry"),
        ("malformed-missing-witness.json", "missing_witness"),
    ],
)
def test_convert_qec_code_random_window_upper_bound_result_rejects_invalid_fixtures(
    fixture_name: str,
    expected_error: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match=expected_error):
        convert_qec_code_random_window_upper_bound_result(
            _load_json(QEC_CODE_FIXTURE_ROOT / fixture_name),
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_legacy_logical_class() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["logical_class"] = "x"

    with pytest.raises(SearchIntegrityError, match="unsupported_logical_class"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_nonzero_complement() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["z"] = [1, 0, 0, 0]
    payload["witness"]["weight"] = 3
    payload["upper_bound"] = 3

    with pytest.raises(SearchIntegrityError, match="nonzero_complementary_pauli_support"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_zero_selected_vector() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["x"] = [0, 0, 0, 0]
    payload["witness"]["z"] = [1, 1, 0, 0]

    with pytest.raises(SearchIntegrityError, match="selected_witness_vector_zero"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_css_verifier_failure() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["x"] = [1, 1, 0, 0]

    with pytest.raises(
        SearchIntegrityError,
        match="invalid_css_upper_bound_witness: in_stabilizer_row_space",
    ):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_run_qec_code_random_window_upper_bound_css_witness_converts_completed_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )

    result = run_qec_code_random_window_upper_bound_css_witness(
        FIXTURE_ROOT / "hx.json",
        FIXTURE_ROOT / "hz.json",
        hx_payload=_load_json(FIXTURE_ROOT / "hx.json"),
        hz_payload=_load_json(FIXTURE_ROOT / "hz.json"),
        qec_code_bin=str(fake_qec_code),
        iterations=16,
        restarts=3,
        seed=61,
        target_weight=2,
        timeout_seconds=5,
    )

    assert result["witness_payload"] == {"basis": "x", "vector": [0, 0, 1, 1]}
    assert result["distance_payload"]["method"] == "css-upper-bound-witness"
    assert result["qec_code_result"]["method"] == "random-window-upper-bound"


def test_run_qec_code_random_window_upper_bound_css_witness_rejects_matrix_payload_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    mismatched_hx_payload = _load_json(FIXTURE_ROOT / "hx.json")
    mismatched_hx_payload["data"] = [[1, 0, 0, 0]]

    with pytest.raises(SearchIntegrityError, match="hx_payload_path_mismatch"):
        run_qec_code_random_window_upper_bound_css_witness(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            hx_payload=mismatched_hx_payload,
            hz_payload=_load_json(FIXTURE_ROOT / "hz.json"),
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )


def test_run_qec_code_random_window_upper_bound_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_STDOUT", "{not-json}\n")

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message


def test_run_qec_code_random_window_upper_bound_rejects_wrong_method(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["method"] = "some-other-method"
    payload_path = tmp_path / "wrong-method.json"
    payload_path.write_text(json.dumps(payload) + "\n")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_PAYLOAD", str(payload_path))

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "method" in message
    assert "random-window-upper-bound" in message or "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message or "stderr:" in message


def test_run_qec_code_random_window_upper_bound_rejects_non_completed_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-z-completed.json")
    payload["status"] = "running"
    payload_path = tmp_path / "not-completed.json"
    payload_path.write_text(json.dumps(payload) + "\n")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_PAYLOAD", str(payload_path))

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "status" in message
    assert "completed" in message or "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message or "stderr:" in message


def test_run_qec_code_random_window_upper_bound_rejects_non_upper_bound_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["bound_type"] = "lower"
    payload_path = tmp_path / "non-upper-bound-type.json"
    payload_path.write_text(json.dumps(payload) + "\n")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_PAYLOAD", str(payload_path))

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "bound_type" in message
    assert "upper" in message or "qec-code" in message
    assert "qec-code" in message or "command:" in message
    assert "stdout:" in message or "stderr:" in message


def test_run_qec_code_random_window_upper_bound_rejects_missing_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "malformed-missing-witness.json"),
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "witness" in message
    assert "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message
    assert "stderr:" in message


@pytest.mark.parametrize(
    ("fixture_name", "expected_error"),
    [
        ("mixed-logical-class.json", "unsupported_logical_class"),
        ("upper-bound-weight-mismatch.json", "upper_bound_weight_mismatch"),
        ("x-z-width-mismatch.json", "x_z_width_mismatch"),
        ("non-binary-witness-entry.json", "non_binary_witness_entry"),
    ],
)
def test_run_qec_code_random_window_upper_bound_rejects_fixture_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_name: str,
    expected_error: str,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / fixture_name),
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert expected_error in message
    assert "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message
    assert "stderr:" in message


@pytest.mark.parametrize(
    ("removed_keys", "expected_error"),
    [
        (("options",), "missing_required_key: options"),
        (("options", "provenance"), "missing_required_keys: options, provenance"),
    ],
)
def test_validate_qec_code_random_window_upper_bound_reports_missing_required_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    removed_keys: tuple[str, ...],
    expected_error: str,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    for key in removed_keys:
        del payload[key]
    payload_path = tmp_path / "missing-required-keys.json"
    payload_path.write_text(json.dumps(payload) + "\n")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_PAYLOAD", str(payload_path))

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert expected_error in message
    assert "qec-code" in message
    assert "command:" in message
    assert "stdout:" in message
    assert "stderr:" in message


def test_run_qec_code_random_window_upper_bound_rejects_subprocess_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_EXIT", "7")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_STDERR", "simulated failure\n")

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=5,
        )

    message = str(excinfo.value)
    assert "command:" in message
    assert "stderr:" in message or "stdout:" in message
    assert "qec-code" in message


def test_run_qec_code_random_window_upper_bound_rejects_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv("AUTOQEC_FAKE_QEC_CODE_SLEEP", "2")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        run_qec_code_random_window_upper_bound(
            FIXTURE_ROOT / "hx.json",
            FIXTURE_ROOT / "hz.json",
            qec_code_bin=str(fake_qec_code),
            iterations=16,
            restarts=3,
            seed=61,
            target_weight=2,
            timeout_seconds=0.1,
        )

    message = str(excinfo.value)
    assert "timeout" in message or "timed out" in message
    assert "command:" in message
    assert "qec-code" in message
