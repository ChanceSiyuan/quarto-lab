from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = (
    REPO_ROOT / "campaigns" / "examples" / "css-distance-autoresearch"
)


def test_css_distance_autoresearch_baseline_pin_and_research_brief() -> None:
    source = json.loads((CAMPAIGN_ROOT / "source.json").read_text())

    assert source == {
        "schema_version": 1,
        "repository": "https://github.com/m-webster/codeDistancePYPI",
        "commit": "a4afe9c09bbf5790da9ecc05b65c5b62343979ad",
        "license": "MIT",
        "license_evidence": {
            "license_file": "MIT",
            "package_metadata": "GNUv3",
            "status": "conflict",
            "review": "operator-required",
        },
        "package_name": "codedistance",
        "objective": "upper-bound",
        "baseline_methods": ["QDistEvol", "QDistRndMW", "decoderDist"],
        "baseline_configuration": {
            "decoderDist": {
                "method_id": "decoderDist",
                "params": {"decoder": "bposd"},
            }
        },
    }

    brief = " ".join(
        (CAMPAIGN_ROOT / "research-brief.md").read_text().split()
    )
    for required_text in (
        "QDistEvol",
        "QDistRnd",
        "decoder residual",
        "BP-OSD",
        "connected/linked cluster",
        "APM",
        "quotient",
        "lift",
        "fiber",
        "upper-bound",
        "exact SAT/MaxSAT is out of scope",
        "CSS kernel",
        "non-stabilizer row-space",
        "LICENSE file declares MIT",
        "package metadata declares GNUv3",
        "operator review",
        "`decoderDist`",
        "`bposd`",
    ):
        assert required_text in brief


def test_css_distance_autoresearch_brief_citations_exist_in_bibliography() -> None:
    brief = (CAMPAIGN_ROOT / "research-brief.md").read_text()
    bibliography = (REPO_ROOT / "ref.bib").read_text()

    citation_groups = re.findall(r"\[([^\]]*@[^\]]+)\]", brief)
    cited_keys = {
        key
        for group in citation_groups
        for key in re.findall(r"@([A-Za-z0-9_:-]+)", group)
    }
    bibliography_keys = set(
        re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bibliography)
    )

    assert cited_keys
    assert cited_keys <= bibliography_keys


def test_css_distance_proposal_prompt_is_public_only() -> None:
    prompt = (CAMPAIGN_ROOT / "proposal-prompt.txt").read_text()

    assert "randomized upper-bound CSS distance" in prompt
    assert "candidate.py" in prompt
    assert "https://github.com/m-webster/codeDistancePYPI" in prompt
    assert "a4afe9c09bbf5790da9ecc05b65c5b62343979ad" in prompt
    for forbidden in (
        "surface-rotated-d21",
        "toric-d17",
        "toric-d21",
        "bb72",
        "bb144",
        "bb288-same-shifts",
        "bb432-same-shifts",
        "apm-kasai-p96",
        "apm-kasai-p192",
        "quantum-tanner-toric-d8",
        "case-000",
        "answers.json",
        "expected_distance",
    ):
        assert forbidden not in prompt


def test_css_distance_readme_documents_container_workflow_without_holdout_leak() -> None:
    readme = (CAMPAIGN_ROOT / "README.md").read_text()

    for required_text in (
        "docker build",
        "proposal.Dockerfile",
        "evaluator.Dockerfile",
        "prepare-css-distance-proposal",
        "materialize-css-distance-holdout",
        "prepare-css-distance-algorithm",
        "run-css-distance-candidate",
        "--timeout-seconds 300",
        "run_proposal_canary",
    ):
        assert required_text in readme
    for forbidden in (
        "surface-rotated-d21",
        "toric-d17",
        "toric-d21",
        "bb72",
        "bb144",
        "bb288-same-shifts",
        "bb432-same-shifts",
        "apm-kasai-p96",
        "apm-kasai-p192",
        "quantum-tanner-toric-d8",
        "case-000",
        "answers.json",
        "expected_distance",
    ):
        assert forbidden not in readme


def test_css_distance_proposal_image_pins_supported_codex_cli() -> None:
    dockerfile = (
        REPO_ROOT / "containers" / "css-distance-autoresearch" / "proposal.Dockerfile"
    ).read_text()

    assert "ARG CODEX_CLI_VERSION=0.144.6" in dockerfile
