use std::collections::VecDeque;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use autoqec_tools::distance_ladder::load_distance_ladder;
use serde_json::Value;

const PYTHON_JOB: &str = r#"
import contextlib
import json
import multiprocessing as mp
import sys
import time
import traceback

import numpy as np
from codedistance.distance import CSScodeDistance


def load_sparse_rows(path):
    with open(path) as f:
        payload = json.load(f)
    rows = payload["rows"]
    n = payload["num_cols"]
    matrix = np.zeros((len(rows), n), dtype=np.uint8)
    for i, row in enumerate(rows):
        matrix[i, row] = 1
    return matrix


def clean(value):
    if hasattr(value, "item"):
        return value.item()
    return value


def run_component(hx, hz, method, component, iterations, seed):
    params = {"iterCount": iterations}
    start = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        result = CSScodeDistance(
            hx,
            hz,
            method=method,
            params=params,
            component=component,
            seed=seed,
        )
    elapsed_ms = int(round((time.perf_counter() - start) * 1000))
    return {
        "component": component,
        "distance": int(clean(result.get("d", 0))),
        "elapsed_ms": elapsed_ms,
        "R": int(clean(result.get("R", 0))),
        "T": int(clean(result.get("T", 0))),
        "progress": str(result.get("progress", "")),
    }


def solve_method(hx, hz, method, iterations, seed, queue):
    try:
        z_result = run_component(hx, hz, method, "Z", iterations, seed)
        x_result = run_component(hx, hz, method, "X", iterations, seed + 1)
        best = min(
            [z_result, x_result],
            key=lambda item: item["distance"] if item["distance"] > 0 else 10**18,
        )
        queue.put({
            "status": "completed",
            "method": method,
            "upper_bound": best["distance"],
            "bound_type": "upper",
            "component": best["component"],
            "z": z_result,
            "x": x_result,
        })
    except Exception:
        queue.put({
            "status": "error",
            "method": method,
            "error": traceback.format_exc(),
        })


def main():
    mp.set_start_method("fork", force=True)
    _, hx_path, hz_path, iterations, seed, timeout_seconds = sys.argv
    iterations = int(iterations)
    seed = int(seed)
    timeout_seconds = int(timeout_seconds)
    hx = load_sparse_rows(hx_path)
    hz = load_sparse_rows(hz_path)

    rows = []
    for method_index, method in enumerate(["QDistRndMW", "QDistEvol", "decoderDist"]):
        queue = mp.Queue()
        start = time.perf_counter()
        process = mp.Process(
            target=solve_method,
            args=(hx, hz, method, iterations, seed + method_index, queue),
        )
        process.start()
        process.join(timeout_seconds)
        elapsed_ms = int(round((time.perf_counter() - start) * 1000))
        if process.is_alive():
            process.terminate()
            process.join()
            rows.append({
                "method": method,
                "status": "timeout",
                "elapsed_ms": elapsed_ms,
                "notes": f"exceeded {timeout_seconds}s wall-clock limit",
            })
        elif process.exitcode != 0:
            rows.append({
                "method": method,
                "status": "error",
                "elapsed_ms": elapsed_ms,
                "notes": f"child process exited with {process.exitcode}",
            })
        else:
            result = queue.get() if not queue.empty() else {
                "method": method,
                "status": "error",
                "error": "child process returned no result",
            }
            result["elapsed_ms"] = elapsed_ms
            rows.append(result)

    print(json.dumps({"rows": rows}))


main()
"#;

#[derive(Debug, Clone)]
struct Config {
    manifest_path: PathBuf,
    python_bin: PathBuf,
    output_path: PathBuf,
    timeout: Duration,
    iterations: usize,
    seed: u64,
    max_parallel: usize,
}

#[derive(Debug, Clone)]
struct Job {
    order: usize,
    instance_id: String,
    code_id: String,
    qec_code_spec: String,
    n: usize,
    k: usize,
    expected_distance: usize,
    expected_bound_type: String,
    hx: PathBuf,
    hz: PathBuf,
    seed: u64,
}

#[derive(Debug, Clone)]
struct Row {
    order: usize,
    fields: Vec<String>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let config = parse_args()?;
    if config.max_parallel == 0 {
        return Err("--max-parallel must be positive".to_owned());
    }

    let jobs = build_jobs(&config)?;
    let queue = Arc::new(Mutex::new(VecDeque::from(jobs)));
    let rows = Arc::new(Mutex::new(Vec::new()));
    let mut workers = Vec::new();

    for _ in 0..config.max_parallel {
        let worker_config = config.clone();
        let worker_queue = Arc::clone(&queue);
        let worker_rows = Arc::clone(&rows);
        workers.push(thread::spawn(move || loop {
            let job = {
                let mut queue = worker_queue.lock().expect("queue lock poisoned");
                queue.pop_front()
            };
            let Some(job) = job else {
                break;
            };
            let job_rows = run_job(&worker_config, job);
            worker_rows
                .lock()
                .expect("rows lock poisoned")
                .extend(job_rows);
        }));
    }

    for worker in workers {
        worker
            .join()
            .map_err(|_| "benchmark worker panicked".to_owned())?;
    }

    let mut rows = Arc::try_unwrap(rows)
        .map_err(|_| "failed to unwrap rows".to_owned())?
        .into_inner()
        .map_err(|_| "rows lock poisoned".to_owned())?;
    rows.sort_by_key(|row| row.order);
    write_rows(&config.output_path, &rows)
}

fn parse_args() -> Result<Config, String> {
    let mut args = env::args().skip(1);
    let mut manifest_path = None;
    let mut python_bin = None;
    let mut output_path = None;
    let mut timeout_seconds = 300_u64;
    let mut iterations = 5000_usize;
    let mut seed = 20260626_u64;
    let mut max_parallel = 2_usize;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--manifest" => {
                manifest_path = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--manifest requires a path".to_owned())?,
                ));
            }
            "--python-bin" => {
                python_bin = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--python-bin requires a path".to_owned())?,
                ));
            }
            "--output" => {
                output_path = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--output requires a path".to_owned())?,
                ));
            }
            "--timeout-seconds" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--timeout-seconds requires a value".to_owned())?;
                timeout_seconds = value
                    .parse()
                    .map_err(|_| format!("invalid --timeout-seconds value: {value}"))?;
            }
            "--iterations" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--iterations requires a value".to_owned())?;
                iterations = value
                    .parse()
                    .map_err(|_| format!("invalid --iterations value: {value}"))?;
            }
            "--seed" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--seed requires a value".to_owned())?;
                seed = value
                    .parse()
                    .map_err(|_| format!("invalid --seed value: {value}"))?;
            }
            "--max-parallel" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--max-parallel requires a value".to_owned())?;
                max_parallel = value
                    .parse()
                    .map_err(|_| format!("invalid --max-parallel value: {value}"))?;
            }
            _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
        }
    }

    Ok(Config {
        manifest_path: manifest_path.ok_or_else(|| "--manifest is required".to_owned())?,
        python_bin: python_bin.ok_or_else(|| "--python-bin is required".to_owned())?,
        output_path: output_path.ok_or_else(|| "--output is required".to_owned())?,
        timeout: Duration::from_secs(timeout_seconds),
        iterations,
        seed,
        max_parallel,
    })
}

fn build_jobs(config: &Config) -> Result<Vec<Job>, String> {
    let manifest_text = fs::read_to_string(&config.manifest_path)
        .map_err(|err| format!("failed to read {}: {err}", config.manifest_path.display()))?;
    let manifest = load_distance_ladder(&manifest_text)?;
    let manifest_root = config.manifest_path.parent().ok_or_else(|| {
        format!(
            "manifest path has no parent: {}",
            config.manifest_path.display()
        )
    })?;
    let artifact_root = resolve_path(manifest_root, &manifest.artifact_root);

    let mut jobs = Vec::new();
    for entry in manifest.entries {
        let instance_root = artifact_root.join(&entry.instance_id);
        let instance_text =
            fs::read_to_string(instance_root.join("instance.json")).map_err(|err| {
                format!(
                    "failed to read {} instance.json: {err}",
                    instance_root.display()
                )
            })?;
        let instance: Value = serde_json::from_str(&instance_text).map_err(|err| {
            format!(
                "failed to parse {} instance.json: {err}",
                instance_root.display()
            )
        })?;
        let k = instance["k"]
            .as_u64()
            .ok_or_else(|| format!("{} instance.json lacks numeric k", entry.instance_id))?
            as usize;

        let order = jobs.len() * 3;
        jobs.push(Job {
            order,
            instance_id: entry.instance_id.clone(),
            code_id: entry.code_id.clone(),
            qec_code_spec: entry.qec_code_spec.clone(),
            n: entry.n,
            k,
            expected_distance: entry.expected_distance,
            expected_bound_type: entry.expected_bound_type.clone(),
            hx: instance_root.join("hx.json"),
            hz: instance_root.join("hz.json"),
            seed: config.seed + order as u64,
        });
    }

    Ok(jobs)
}

fn run_job(config: &Config, job: Job) -> Vec<Row> {
    let args = [
        "-c".to_owned(),
        PYTHON_JOB.to_owned(),
        job.hx.to_string_lossy().to_string(),
        job.hz.to_string_lossy().to_string(),
        config.iterations.to_string(),
        job.seed.to_string(),
        config.timeout.as_secs().to_string(),
    ];
    let command_text = format!(
        "{} -c <codedistance CSScodeDistance instance job> {} {} iterCount={} seed={} timeout_seconds={}",
        config.python_bin.display(),
        job.hx.display(),
        job.hz.display(),
        config.iterations,
        job.seed,
        config.timeout.as_secs()
    );
    let outer_timeout = Duration::from_secs(config.timeout.as_secs() * 3 + 120);
    let result = run_with_timeout(&config.python_bin, &args, outer_timeout);

    match result {
        ProcessResult::Completed {
            status_success,
            stdout,
            stderr,
        } if status_success => match serde_json::from_str::<Value>(&stdout) {
            Ok(json) => rows_from_json(config, &job, &command_text, &json),
            Err(err) => error_rows(
                config,
                &job,
                &command_text,
                format!(
                    "invalid JSON output: {err}; stdout={}; stderr={}",
                    compact_note(&stdout),
                    compact_note(&stderr)
                ),
            ),
        },
        ProcessResult::Completed { stderr, .. } => error_rows(
            config,
            &job,
            &command_text,
            format!("external runner failed: {}", compact_note(&stderr)),
        ),
        ProcessResult::Timeout => error_rows(
            config,
            &job,
            &command_text,
            format!(
                "instance runner exceeded {}s outer wall-clock limit",
                outer_timeout.as_secs()
            ),
        ),
        ProcessResult::StartError(err) => error_rows(config, &job, &command_text, err),
    }
}

fn rows_from_json(config: &Config, job: &Job, command_text: &str, json: &Value) -> Vec<Row> {
    let Some(rows) = json["rows"].as_array() else {
        return error_rows(
            config,
            job,
            command_text,
            "external runner JSON lacks rows array".to_owned(),
        );
    };

    rows.iter()
        .enumerate()
        .map(|(index, row)| {
            let method = row["method"].as_str().unwrap_or("unknown").to_owned();
            let status = row["status"].as_str().unwrap_or("error").to_owned();
            let (computed_distance, computed_bound_type, component, notes) =
                if status == "completed" {
                    (
                        row["upper_bound"]
                            .as_u64()
                            .map(|value| value.to_string())
                            .unwrap_or_default(),
                        row["bound_type"].as_str().unwrap_or("upper").to_owned(),
                        row["component"].as_str().unwrap_or("").to_owned(),
                        format!(
                            "timeout_seconds={}; iterCount={}; seed={}; z_bound={}; z_elapsed_ms={}; z_T={}; z_R={}; x_bound={}; x_elapsed_ms={}; x_T={}; x_R={}",
                            config.timeout.as_secs(),
                            config.iterations,
                            job.seed,
                            row["z"]["distance"].as_i64().unwrap_or_default(),
                            row["z"]["elapsed_ms"].as_i64().unwrap_or_default(),
                            row["z"]["T"].as_i64().unwrap_or_default(),
                            row["z"]["R"].as_i64().unwrap_or_default(),
                            row["x"]["distance"].as_i64().unwrap_or_default(),
                            row["x"]["elapsed_ms"].as_i64().unwrap_or_default(),
                            row["x"]["T"].as_i64().unwrap_or_default(),
                            row["x"]["R"].as_i64().unwrap_or_default(),
                        ),
                    )
                } else {
                    (
                        String::new(),
                        String::new(),
                        String::new(),
                        row["notes"]
                            .as_str()
                            .or_else(|| row["error"].as_str())
                            .map(compact_note)
                            .unwrap_or_default(),
                    )
                };

            Row {
                order: job.order + index,
                fields: vec![
                    job.instance_id.clone(),
                    job.code_id.clone(),
                    job.qec_code_spec.clone(),
                    job.n.to_string(),
                    job.k.to_string(),
                    job.expected_distance.to_string(),
                    job.expected_bound_type.clone(),
                    format!("codedistance-{method}"),
                    status,
                    computed_distance,
                    computed_bound_type,
                    row["elapsed_ms"]
                        .as_u64()
                        .map(|value| value.to_string())
                        .unwrap_or_default(),
                    component,
                    command_text.to_owned(),
                    notes,
                ],
            }
        })
        .collect()
}

fn error_rows(config: &Config, job: &Job, command_text: &str, notes: String) -> Vec<Row> {
    ["QDistRndMW", "QDistEvol", "decoderDist"]
        .iter()
        .enumerate()
        .map(|(index, method)| Row {
            order: job.order + index,
            fields: vec![
                job.instance_id.clone(),
                job.code_id.clone(),
                job.qec_code_spec.clone(),
                job.n.to_string(),
                job.k.to_string(),
                job.expected_distance.to_string(),
                job.expected_bound_type.clone(),
                format!("codedistance-{method}"),
                "error".to_owned(),
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                command_text.to_owned(),
                format!(
                    "timeout_seconds={}; iterCount={}; seed={}; {}",
                    config.timeout.as_secs(),
                    config.iterations,
                    job.seed,
                    notes
                ),
            ],
        })
        .collect()
}

enum ProcessResult {
    Completed {
        status_success: bool,
        stdout: String,
        stderr: String,
    },
    Timeout,
    StartError(String),
}

fn run_with_timeout(command: &Path, args: &[String], timeout: Duration) -> ProcessResult {
    let mut child = match Command::new(command)
        .args(args)
        .env("MPLCONFIGDIR", "/private/tmp/codedistance-mpl")
        .env("NUMBA_CACHE_DIR", "/private/tmp/codedistance-numba")
        .env("PYTHONPYCACHEPREFIX", "/private/tmp/codedistance-pycache")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(err) => return ProcessResult::StartError(format!("failed to start command: {err}")),
    };
    let start = Instant::now();

    loop {
        match child.try_wait() {
            Ok(Some(_)) => {
                return match child.wait_with_output() {
                    Ok(output) => ProcessResult::Completed {
                        status_success: output.status.success(),
                        stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                    },
                    Err(err) => ProcessResult::StartError(format!("failed to read output: {err}")),
                };
            }
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    return ProcessResult::Timeout;
                }
                thread::sleep(Duration::from_millis(100));
            }
            Err(err) => {
                let _ = child.kill();
                return ProcessResult::StartError(format!("failed to poll child: {err}"));
            }
        }
    }
}

fn write_rows(path: &Path, rows: &[Row]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
    }
    let mut lines = vec![
        "instance_id,code_id,qec_code_spec,n,k,expected_distance,expected_bound_type,method,status,computed_distance,computed_bound_type,elapsed_ms,component,command,notes".to_owned(),
    ];
    for row in rows {
        lines.push(
            row.fields
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

fn compact_note(value: &str) -> String {
    value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
        .take(240)
        .collect()
}

fn resolve_path(root: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        root.join(path)
    }
}

fn usage() -> String {
    "usage: autoqec-distance-codedistance --manifest <path> --python-bin <path> --output <path> [--timeout-seconds 300] [--iterations 5000] [--seed 20260626] [--max-parallel 2]".to_owned()
}
