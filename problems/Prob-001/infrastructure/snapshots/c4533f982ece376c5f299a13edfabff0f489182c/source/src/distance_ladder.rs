use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct DistanceLadder {
    pub id: String,
    pub title: String,
    pub artifact_root: PathBuf,
    pub results_table: PathBuf,
    pub entries: Vec<DistanceLadderEntry>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct DistanceLadderEntry {
    pub instance_id: String,
    pub code_id: String,
    pub qec_code_spec: String,
    #[serde(default)]
    pub quantum_tanner_spec: Option<PathBuf>,
    pub n: usize,
    #[serde(default)]
    pub k: Option<usize>,
    pub expected_distance: usize,
    pub expected_bound_type: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct SparseRowsMatrix {
    pub format: String,
    pub num_cols: usize,
    pub rows: Vec<Vec<usize>>,
}

#[derive(Debug, Clone)]
pub struct ExportOptions {
    pub manifest_path: PathBuf,
    pub qec_code_bin: PathBuf,
    pub force: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExportSummary {
    pub instances_written: usize,
    pub results_table_rows: usize,
    pub artifact_root: PathBuf,
    pub results_table: PathBuf,
}

#[derive(Debug, Serialize)]
struct MaterializedInstance<'a> {
    instance_id: &'a str,
    code_id: &'a str,
    qec_code_spec: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    quantum_tanner_spec: Option<&'a str>,
    n: usize,
    k: usize,
    expected_distance: usize,
    expected_bound_type: &'a str,
    artifacts: MatrixArtifacts,
    generator: GeneratorMetadata<'a>,
}

#[derive(Debug, Serialize)]
struct MatrixArtifacts {
    hx: &'static str,
    hz: &'static str,
}

#[derive(Debug, Serialize)]
struct GeneratorMetadata<'a> {
    tool: &'static str,
    hx_command: Vec<String>,
    hz_command: Vec<String>,
    #[serde(skip)]
    _marker: std::marker::PhantomData<&'a ()>,
}

#[derive(Debug, Clone)]
struct ExportedEntry {
    instance_id: String,
    code_id: String,
    qec_code_spec: String,
    n: usize,
    k: usize,
    expected_distance: usize,
    expected_bound_type: String,
}

#[derive(Debug, Clone)]
enum MatrixSource {
    BuiltIn { qec_code_spec: String },
    QuantumTanner { spec_path: PathBuf },
}

pub fn load_distance_ladder(text: &str) -> Result<DistanceLadder, String> {
    let manifest: DistanceLadder =
        serde_json::from_str(text).map_err(|err| format!("invalid ladder JSON: {err}"))?;
    validate_manifest(&manifest)?;
    Ok(manifest)
}

pub fn export_distance_ladder(options: ExportOptions) -> Result<ExportSummary, String> {
    let manifest_text = fs::read_to_string(&options.manifest_path)
        .map_err(|err| format!("failed to read {}: {err}", options.manifest_path.display()))?;
    let manifest = load_distance_ladder(&manifest_text)?;
    let manifest_root = options.manifest_path.parent().ok_or_else(|| {
        format!(
            "manifest path has no parent: {}",
            options.manifest_path.display()
        )
    })?;
    let artifact_root = resolve_manifest_path(manifest_root, &manifest.artifact_root);
    let results_table = resolve_manifest_path(manifest_root, &manifest.results_table);

    fs::create_dir_all(&artifact_root)
        .map_err(|err| format!("failed to create {}: {err}", artifact_root.display()))?;

    let mut instances_written = 0;
    let mut exported_entries = Vec::new();
    for entry in &manifest.entries {
        exported_entries.push(export_entry(
            &options,
            entry,
            manifest_root,
            &artifact_root,
        )?);
        instances_written += 1;
    }

    write_results_table(&exported_entries, &results_table)?;

    Ok(ExportSummary {
        instances_written,
        results_table_rows: manifest.entries.len(),
        artifact_root,
        results_table,
    })
}

impl SparseRowsMatrix {
    pub fn validate_expected_width(&self, expected_num_cols: usize) -> Result<(), String> {
        if self.format != "sparse_rows" {
            return Err(format!("expected format=sparse_rows, got {}", self.format));
        }
        if self.num_cols != expected_num_cols {
            return Err(format!(
                "expected num_cols={expected_num_cols}, got {}",
                self.num_cols
            ));
        }
        for (row_index, row) in self.rows.iter().enumerate() {
            let mut sorted = row.clone();
            sorted.sort_unstable();
            for pair in sorted.windows(2) {
                if pair[0] == pair[1] {
                    return Err(format!(
                        "row {row_index} contains duplicate support {}",
                        pair[0]
                    ));
                }
            }
            for &support in row {
                if support >= self.num_cols {
                    return Err(format!(
                        "row {row_index} contains out-of-range support {support} for width {}",
                        self.num_cols
                    ));
                }
            }
        }
        Ok(())
    }
}

fn validate_manifest(manifest: &DistanceLadder) -> Result<(), String> {
    if manifest.id.is_empty() {
        return Err("ladder id must not be empty".to_owned());
    }
    if manifest.entries.is_empty() {
        return Err("ladder entries must not be empty".to_owned());
    }
    for entry in &manifest.entries {
        if entry.instance_id.is_empty() {
            return Err("entry instance_id must not be empty".to_owned());
        }
        if entry.code_id.is_empty() {
            return Err(format!("{} code_id must not be empty", entry.instance_id));
        }
        if entry.qec_code_spec.is_empty() {
            return Err(format!(
                "{} qec_code_spec must not be empty",
                entry.instance_id
            ));
        }
        if entry.qec_code_spec.starts_with("quantum_tanner:") && entry.quantum_tanner_spec.is_none()
        {
            return Err(format!(
                "{} quantum_tanner qec_code_spec requires quantum_tanner_spec",
                entry.instance_id
            ));
        }
        if let Some(path) = &entry.quantum_tanner_spec {
            if path.as_os_str().is_empty() {
                return Err(format!(
                    "{} quantum_tanner_spec must not be empty",
                    entry.instance_id
                ));
            }
        }
        if entry.n == 0 {
            return Err(format!("{} n must be positive", entry.instance_id));
        }
        if entry.k == Some(0) {
            return Err(format!(
                "{} k must be positive when provided",
                entry.instance_id
            ));
        }
        if entry.expected_distance == 0 {
            return Err(format!(
                "{} expected_distance must be positive",
                entry.instance_id
            ));
        }
        if entry.expected_bound_type != "exact" && entry.expected_bound_type != "upper" {
            return Err(format!(
                "{} expected_bound_type must be exact or upper",
                entry.instance_id
            ));
        }
    }
    Ok(())
}

fn export_entry(
    options: &ExportOptions,
    entry: &DistanceLadderEntry,
    manifest_root: &Path,
    artifact_root: &Path,
) -> Result<ExportedEntry, String> {
    let instance_root = artifact_root.join(&entry.instance_id);
    if instance_root.exists() && !options.force {
        return Err(format!(
            "{} already exists; rerun with --force to overwrite",
            instance_root.display()
        ));
    }
    fs::create_dir_all(&instance_root)
        .map_err(|err| format!("failed to create {}: {err}", instance_root.display()))?;

    let quantum_tanner_spec = entry
        .quantum_tanner_spec
        .as_ref()
        .map(|path| resolve_manifest_path(manifest_root, path));
    let source = match &quantum_tanner_spec {
        Some(path) => MatrixSource::QuantumTanner {
            spec_path: path.clone(),
        },
        None => MatrixSource::BuiltIn {
            qec_code_spec: entry.qec_code_spec.clone(),
        },
    };

    let hx = run_qec_code_matrix(&options.qec_code_bin, &source, "hx")?;
    let hz = run_qec_code_matrix(&options.qec_code_bin, &source, "hz")?;
    hx.validate_expected_width(entry.n)?;
    hz.validate_expected_width(entry.n)?;
    let computed_k = css_dimension(entry.n, &hx, &hz)?;
    if let Some(expected_k) = entry.k {
        if expected_k != computed_k {
            return Err(format!(
                "{} k mismatch: manifest has {expected_k}, generated matrices have {computed_k}",
                entry.instance_id
            ));
        }
    }

    write_pretty_json(&instance_root.join("hx.json"), &hx)?;
    write_pretty_json(&instance_root.join("hz.json"), &hz)?;
    let quantum_tanner_spec_text = entry
        .quantum_tanner_spec
        .as_ref()
        .map(|path| path.to_string_lossy().to_string());

    let instance = MaterializedInstance {
        instance_id: &entry.instance_id,
        code_id: &entry.code_id,
        qec_code_spec: &entry.qec_code_spec,
        quantum_tanner_spec: quantum_tanner_spec_text.as_deref(),
        n: entry.n,
        k: computed_k,
        expected_distance: entry.expected_distance,
        expected_bound_type: &entry.expected_bound_type,
        artifacts: MatrixArtifacts {
            hx: "hx.json",
            hz: "hz.json",
        },
        generator: GeneratorMetadata {
            tool: "qec-code",
            hx_command: matrix_command(&source, "hx"),
            hz_command: matrix_command(&source, "hz"),
            _marker: std::marker::PhantomData,
        },
    };
    write_pretty_json(&instance_root.join("instance.json"), &instance)?;
    Ok(ExportedEntry {
        instance_id: entry.instance_id.clone(),
        code_id: entry.code_id.clone(),
        qec_code_spec: entry.qec_code_spec.clone(),
        n: entry.n,
        k: computed_k,
        expected_distance: entry.expected_distance,
        expected_bound_type: entry.expected_bound_type.clone(),
    })
}

fn run_qec_code_matrix(
    qec_code_bin: &Path,
    source: &MatrixSource,
    matrix: &str,
) -> Result<SparseRowsMatrix, String> {
    let args = matrix_args(source, matrix);
    let output = Command::new(qec_code_bin)
        .args(&args)
        .output()
        .map_err(|err| format!("failed to run {}: {err}", qec_code_bin.display()))?;

    if !output.status.success() {
        return Err(format!(
            "qec-code failed for {} {matrix}: {}",
            source_label(source),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    serde_json::from_slice(&output.stdout).map_err(|err| {
        format!(
            "qec-code returned invalid JSON for {} {matrix}: {err}",
            source_label(source)
        )
    })
}

fn matrix_args(source: &MatrixSource, matrix: &str) -> Vec<String> {
    match source {
        MatrixSource::BuiltIn { qec_code_spec } => vec![
            "code".to_owned(),
            "css".to_owned(),
            "export".to_owned(),
            qec_code_spec.clone(),
            matrix.to_owned(),
        ],
        MatrixSource::QuantumTanner { spec_path } => vec![
            "code".to_owned(),
            "css".to_owned(),
            "quantum-tanner".to_owned(),
            "--spec".to_owned(),
            spec_path.to_string_lossy().to_string(),
            matrix.to_owned(),
        ],
    }
}

fn matrix_command(source: &MatrixSource, matrix: &str) -> Vec<String> {
    let mut command = vec!["qec-code".to_owned()];
    command.extend(matrix_args(source, matrix));
    command
}

fn source_label(source: &MatrixSource) -> String {
    match source {
        MatrixSource::BuiltIn { qec_code_spec } => qec_code_spec.clone(),
        MatrixSource::QuantumTanner { spec_path } => {
            format!("quantum-tanner:{}", spec_path.display())
        }
    }
}

pub fn css_dimension(
    num_cols: usize,
    hx: &SparseRowsMatrix,
    hz: &SparseRowsMatrix,
) -> Result<usize, String> {
    hx.validate_expected_width(num_cols)?;
    hz.validate_expected_width(num_cols)?;
    let rank_x = gf2_rank_sparse_rows(num_cols, &hx.rows);
    let rank_z = gf2_rank_sparse_rows(num_cols, &hz.rows);
    num_cols.checked_sub(rank_x + rank_z).ok_or_else(|| {
        format!("invalid CSS rank sum: rank_x={rank_x}, rank_z={rank_z}, n={num_cols}")
    })
}

fn gf2_rank_sparse_rows(num_cols: usize, rows: &[Vec<usize>]) -> usize {
    let words = (num_cols + 63) / 64;
    let mut basis = vec![vec![0_u64; words]; num_cols];
    let mut rank = 0;

    for row in rows {
        let mut vector = vec![0_u64; words];
        for &col in row {
            vector[col / 64] ^= 1_u64 << (col % 64);
        }

        for pivot in 0..num_cols {
            if vector[pivot / 64] & (1_u64 << (pivot % 64)) == 0 {
                continue;
            }
            if basis[pivot].iter().any(|&word| word != 0) {
                xor_assign(&mut vector, &basis[pivot]);
            } else {
                basis[pivot] = vector;
                rank += 1;
                break;
            }
        }
    }

    rank
}

fn xor_assign(left: &mut [u64], right: &[u64]) {
    for (left_word, right_word) in left.iter_mut().zip(right) {
        *left_word ^= *right_word;
    }
}

fn write_pretty_json<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let text = serde_json::to_string_pretty(value)
        .map_err(|err| format!("failed to encode JSON: {err}"))?;
    fs::write(path, format!("{text}\n"))
        .map_err(|err| format!("failed to write {}: {err}", path.display()))
}

fn write_results_table(entries: &[ExportedEntry], path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
    }

    let mut lines = vec![
        "instance_id,code_id,qec_code_spec,n,k,expected_distance,expected_bound_type,method,status,computed_distance,computed_bound_type,elapsed_ms,command,notes".to_owned(),
    ];

    for entry in entries {
        let fields = [
            entry.instance_id.as_str(),
            entry.code_id.as_str(),
            entry.qec_code_spec.as_str(),
            &entry.n.to_string(),
            &entry.k.to_string(),
            &entry.expected_distance.to_string(),
            entry.expected_bound_type.as_str(),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ];
        lines.push(
            fields
                .iter()
                .map(|field| csv_escape(field))
                .collect::<Vec<_>>()
                .join(","),
        );
    }

    fs::write(path, format!("{}\n", lines.join("\n")))
        .map_err(|err| format!("failed to write {}: {err}", path.display()))
}

fn csv_escape(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_owned()
    }
}

fn resolve_manifest_path(root: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        root.join(path)
    }
}
