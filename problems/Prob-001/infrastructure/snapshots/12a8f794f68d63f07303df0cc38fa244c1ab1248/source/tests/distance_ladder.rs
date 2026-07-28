use std::fs;
use std::path::Path;

use autoqec_tools::distance_ladder::{
    css_dimension, export_distance_ladder, load_distance_ladder, ExportOptions, SparseRowsMatrix,
};

fn fake_qec_code_script(path: &Path) {
    fs::write(
        path,
        r#"#!/bin/sh
set -eu
spec="$4"
matrix="$5"
case "$spec:$matrix" in
  surface_rotated:d=5:hx)
    printf '%s\n' '{"format":"sparse_rows","num_cols":25,"rows":[[0,1,5,6]]}'
    ;;
  surface_rotated:d=5:hz)
    printf '%s\n' '{"format":"sparse_rows","num_cols":25,"rows":[[0,5]]}'
    ;;
  *)
    echo "unexpected qec-code args: $*" >&2
    exit 9
    ;;
esac
"#,
    )
    .unwrap();

    let mut permissions = fs::metadata(path).unwrap().permissions();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        permissions.set_mode(0o755);
        fs::set_permissions(path, permissions).unwrap();
    }
}

#[test]
fn load_distance_ladder_manifest_records_qec_code_specs() {
    let manifest = load_distance_ladder(
        r#"{
          "id": "unit-ladder",
          "title": "Unit Ladder",
          "artifact_root": "benchmarks/distance_ladders/unit/instances",
          "results_table": "benchmarks/distance_ladders/unit/distance-results.csv",
          "entries": [
            {
              "instance_id": "surface-rotated-d5",
              "code_id": "rotated-surface-code",
              "qec_code_spec": "surface_rotated:d=5",
              "n": 25,
              "k": 1,
              "expected_distance": 5,
              "expected_bound_type": "exact"
            }
          ]
        }"#,
    )
    .unwrap();

    assert_eq!(manifest.id, "unit-ladder");
    assert_eq!(manifest.entries[0].qec_code_spec, "surface_rotated:d=5");
    assert_eq!(manifest.entries[0].k, Some(1));
    assert_eq!(manifest.entries[0].expected_distance, 5);
}

#[test]
fn sparse_rows_matrix_rejects_wrong_width() {
    let matrix: SparseRowsMatrix =
        serde_json::from_str(r#"{"format":"sparse_rows","num_cols":24,"rows":[[0]]}"#).unwrap();

    let error = matrix.validate_expected_width(25).unwrap_err();

    assert!(error.contains("expected num_cols=25, got 24"));
}

#[test]
fn export_distance_ladder_materializes_instances_and_results_table() {
    let temp = tempfile::tempdir().unwrap();
    let qec_code = temp.path().join("qec-code");
    fake_qec_code_script(&qec_code);

    let manifest_path = temp.path().join("ladder.json");
    fs::write(
        &manifest_path,
        r#"{
          "id": "unit-ladder",
          "title": "Unit Ladder",
          "artifact_root": "instances",
          "results_table": "distance-results.csv",
          "entries": [
            {
              "instance_id": "surface-rotated-d5",
              "code_id": "rotated-surface-code",
              "qec_code_spec": "surface_rotated:d=5",
              "n": 25,
              "expected_distance": 5,
              "expected_bound_type": "exact"
            }
          ]
        }"#,
    )
    .unwrap();

    let summary = export_distance_ladder(ExportOptions {
        manifest_path: manifest_path.clone(),
        qec_code_bin: qec_code,
        force: false,
    })
    .unwrap();

    assert_eq!(summary.instances_written, 1);
    assert_eq!(summary.results_table_rows, 1);

    let root = manifest_path.parent().unwrap();
    let instance_root = root.join("instances/surface-rotated-d5");
    let instance = fs::read_to_string(instance_root.join("instance.json")).unwrap();
    assert!(instance.contains(r#""qec_code_spec": "surface_rotated:d=5""#));
    assert!(instance.contains(r#""k": 23"#));
    assert!(instance.contains(r#""expected_distance": 5"#));
    assert_eq!(
        fs::read_to_string(instance_root.join("hx.json")).unwrap(),
        "{\n  \"format\": \"sparse_rows\",\n  \"num_cols\": 25,\n  \"rows\": [\n    [\n      0,\n      1,\n      5,\n      6\n    ]\n  ]\n}\n"
    );

    let table = fs::read_to_string(root.join("distance-results.csv")).unwrap();
    assert!(table.starts_with("instance_id,code_id,qec_code_spec,n,k,expected_distance"));
    assert!(
        table.contains("surface-rotated-d5,rotated-surface-code,surface_rotated:d=5,25,23,5,exact")
    );
}

#[test]
fn css_dimension_uses_gf2_ranks() {
    let hx: SparseRowsMatrix =
        serde_json::from_str(r#"{"format":"sparse_rows","num_cols":5,"rows":[[0,1],[1,2]]}"#)
            .unwrap();
    let hz: SparseRowsMatrix =
        serde_json::from_str(r#"{"format":"sparse_rows","num_cols":5,"rows":[[3,4]]}"#).unwrap();

    assert_eq!(css_dimension(5, &hx, &hz).unwrap(), 2);
}

#[test]
fn committed_surface_toric_bb_ladder_artifacts_match_manifest() {
    let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
    let manifest_path = repo.join("benchmarks/distance_ladders/surface-toric-bb-v1.json");
    let manifest = load_distance_ladder(&fs::read_to_string(&manifest_path).unwrap()).unwrap();
    let manifest_root = manifest_path.parent().unwrap();
    let artifact_root = manifest_root.join(&manifest.artifact_root);

    assert_eq!(manifest.entries.len(), 8);
    for entry in &manifest.entries {
        let instance_root = artifact_root.join(&entry.instance_id);
        let instance = fs::read_to_string(instance_root.join("instance.json")).unwrap();
        assert!(instance.contains(&format!(r#""instance_id": "{}""#, entry.instance_id)));
        assert!(instance.contains(&format!(r#""qec_code_spec": "{}""#, entry.qec_code_spec)));

        for matrix_name in ["hx.json", "hz.json"] {
            let matrix_text = fs::read_to_string(instance_root.join(matrix_name)).unwrap();
            let matrix: SparseRowsMatrix = serde_json::from_str(&matrix_text).unwrap();
            matrix.validate_expected_width(entry.n).unwrap();
        }
    }

    let table = fs::read_to_string(manifest_root.join(&manifest.results_table)).unwrap();
    assert_eq!(table.lines().count(), manifest.entries.len() * 2 + 1);
    for entry in &manifest.entries {
        assert!(table.contains(&format!(
            "{},{},{},{},{},{},{},randomized-upper-bound,",
            entry.instance_id,
            entry.code_id,
            csv_field(&entry.qec_code_spec),
            entry.n,
            entry.k.unwrap(),
            entry.expected_distance,
            entry.expected_bound_type
        )));
        assert!(table.contains(&format!(
            "{},{},{},{},{},{},{},gurobi-ilp-exact,",
            entry.instance_id,
            entry.code_id,
            csv_field(&entry.qec_code_spec),
            entry.n,
            entry.k.unwrap(),
            entry.expected_distance,
            entry.expected_bound_type
        )));
    }
}

#[test]
fn committed_expanded_ladder_artifacts_match_manifest() {
    let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
    let manifest_path =
        repo.join("benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2.json");
    let manifest = load_distance_ladder(&fs::read_to_string(&manifest_path).unwrap()).unwrap();
    let manifest_root = manifest_path.parent().unwrap();
    let artifact_root = manifest_root.join(&manifest.artifact_root);

    assert_eq!(manifest.entries.len(), 19);
    for entry in &manifest.entries {
        let instance_root = artifact_root.join(&entry.instance_id);
        let instance = fs::read_to_string(instance_root.join("instance.json")).unwrap();
        assert!(instance.contains(&format!(r#""instance_id": "{}""#, entry.instance_id)));
        assert!(instance.contains(&format!(r#""qec_code_spec": "{}""#, entry.qec_code_spec)));

        if let Some(spec) = &entry.quantum_tanner_spec {
            assert!(instance.contains(&spec.to_string_lossy().to_string()));
        }

        for matrix_name in ["hx.json", "hz.json"] {
            let matrix_text = fs::read_to_string(instance_root.join(matrix_name)).unwrap();
            let matrix: SparseRowsMatrix = serde_json::from_str(&matrix_text).unwrap();
            matrix.validate_expected_width(entry.n).unwrap();
        }
    }

    let native_results = fs::read_to_string(
        manifest_root.join("surface-toric-bb-kasai-tanner-v2/rstim225-native-results.csv"),
    )
    .unwrap();
    assert_eq!(
        native_results.lines().count(),
        manifest.entries.len() * 2 + 1
    );
    assert!(native_results.contains("random-window-upper-bound"));
    assert!(native_results.contains("timeout"));

    let comparison = fs::read_to_string(
        manifest_root.join("surface-toric-bb-kasai-tanner-v2/rstim225-comparison.md"),
    )
    .unwrap();
    assert_eq!(comparison.lines().count(), manifest.entries.len() + 2);
    assert!(comparison.contains("| random-window | QDistRndMW | QDistEvol | decoderDist |"));
    assert!(!comparison.contains("| randomized |"));
    assert!(comparison.contains("| apm-kasai-p192 | 2304 | 1156 | 14 upper |"));
}

fn csv_field(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_owned()
    }
}
