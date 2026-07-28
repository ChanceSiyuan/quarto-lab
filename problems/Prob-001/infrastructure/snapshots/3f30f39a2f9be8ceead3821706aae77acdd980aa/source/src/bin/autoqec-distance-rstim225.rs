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

#[derive(Debug, Clone)]
struct Config {
    manifest_path: PathBuf,
    qec_code_bin: PathBuf,
    output_path: PathBuf,
    timeout: Duration,
    iterations: usize,
    restarts: usize,
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
    method: String,
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
            let row = run_job(&worker_config, job);
            worker_rows.lock().expect("rows lock poisoned").push(row);
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
    let mut qec_code_bin = None;
    let mut output_path = None;
    let mut timeout_seconds = 300_u64;
    let mut iterations = 5000_usize;
    let mut restarts = 8_usize;
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
            "--qec-code-bin" => {
                qec_code_bin =
                    Some(PathBuf::from(args.next().ok_or_else(|| {
                        "--qec-code-bin requires a path".to_owned()
                    })?));
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
            "--restarts" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--restarts requires a value".to_owned())?;
                restarts = value
                    .parse()
                    .map_err(|_| format!("invalid --restarts value: {value}"))?;
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
        qec_code_bin: qec_code_bin.ok_or_else(|| "--qec-code-bin is required".to_owned())?,
        output_path: output_path.ok_or_else(|| "--output is required".to_owned())?,
        timeout: Duration::from_secs(timeout_seconds),
        iterations,
        restarts,
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

        for method in ["randomized-upper-bound", "random-window-upper-bound"] {
            let order = jobs.len();
            jobs.push(Job {
                order,
                instance_id: entry.instance_id.clone(),
                code_id: entry.code_id.clone(),
                qec_code_spec: entry.qec_code_spec.clone(),
                n: entry.n,
                k,
                expected_distance: entry.expected_distance,
                expected_bound_type: entry.expected_bound_type.clone(),
                method: method.to_owned(),
                hx: instance_root.join("hx.json"),
                hz: instance_root.join("hz.json"),
                seed: config.seed + order as u64,
            });
        }
    }

    Ok(jobs)
}

fn run_job(config: &Config, job: Job) -> Row {
    let mut args = vec![
        "code".to_owned(),
        "css-distance".to_owned(),
        job.method.clone(),
        "--hx".to_owned(),
        job.hx.to_string_lossy().to_string(),
        "--hz".to_owned(),
        job.hz.to_string_lossy().to_string(),
        "--iterations".to_owned(),
        config.iterations.to_string(),
        "--restarts".to_owned(),
        config.restarts.to_string(),
        "--seed".to_owned(),
        job.seed.to_string(),
        "--target-weight".to_owned(),
        job.expected_distance.to_string(),
        "--json".to_owned(),
    ];
    let command_text = format!("{} {}", config.qec_code_bin.display(), args.join(" "));
    let start = Instant::now();
    let result = run_with_timeout(&config.qec_code_bin, &args, config.timeout);
    let elapsed_ms = start.elapsed().as_millis().to_string();
    args.clear();

    let (status, computed_distance, computed_bound_type, notes) = match result {
        ProcessResult::Completed {
            status_success,
            stdout,
            stderr,
        } => {
            if !status_success {
                (
                    "error".to_owned(),
                    String::new(),
                    String::new(),
                    compact_note(&stderr),
                )
            } else {
                match serde_json::from_str::<Value>(&stdout) {
                    Ok(json) => (
                        json["status"].as_str().unwrap_or("completed").to_owned(),
                        json["upper_bound"]
                            .as_u64()
                            .map(|value| value.to_string())
                            .unwrap_or_default(),
                        json["bound_type"].as_str().unwrap_or("upper").to_owned(),
                        format!(
                            "timeout_seconds={}; iterations={}; restarts={}; seed={}",
                            config.timeout.as_secs(),
                            config.iterations,
                            config.restarts,
                            job.seed
                        ),
                    ),
                    Err(err) => (
                        "error".to_owned(),
                        String::new(),
                        String::new(),
                        format!(
                            "invalid JSON output: {err}; stdout={}",
                            compact_note(&stdout)
                        ),
                    ),
                }
            }
        }
        ProcessResult::Timeout => (
            "timeout".to_owned(),
            String::new(),
            String::new(),
            format!("exceeded {}s wall-clock limit", config.timeout.as_secs()),
        ),
        ProcessResult::StartError(err) => ("error".to_owned(), String::new(), String::new(), err),
    };

    Row {
        order: job.order,
        fields: vec![
            job.instance_id,
            job.code_id,
            job.qec_code_spec,
            job.n.to_string(),
            job.k.to_string(),
            job.expected_distance.to_string(),
            job.expected_bound_type,
            job.method,
            status,
            computed_distance,
            computed_bound_type,
            elapsed_ms,
            command_text,
            notes,
        ],
    }
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
        "instance_id,code_id,qec_code_spec,n,k,expected_distance,expected_bound_type,method,status,computed_distance,computed_bound_type,elapsed_ms,command,notes".to_owned(),
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
    "usage: autoqec-distance-rstim225 --manifest <path> --qec-code-bin <path> --output <path> [--timeout-seconds 300] [--iterations 5000] [--restarts 8] [--seed 20260626] [--max-parallel 2]".to_owned()
}
