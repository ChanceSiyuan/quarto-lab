use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Default)]
struct InstanceRows {
    instance_id: String,
    n: String,
    k: String,
    expected: String,
    expected_bound_type: String,
    random_window: Option<MethodCell>,
    codedistance_qdist_rnd_mw: Option<MethodCell>,
    codedistance_qdist_evol: Option<MethodCell>,
    codedistance_decoder_dist: Option<MethodCell>,
}

#[derive(Debug, Clone)]
struct MethodCell {
    status: String,
    distance: String,
    elapsed_ms: String,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let mut inputs = Vec::new();
    let mut csv_output = None;
    let mut md_output = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--input" => {
                inputs.push(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--input requires a path".to_owned())?,
                ));
            }
            "--csv-output" => {
                csv_output = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--csv-output requires a path".to_owned())?,
                ));
            }
            "--md-output" => {
                md_output = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--md-output requires a path".to_owned())?,
                ));
            }
            _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
        }
    }

    if inputs.is_empty() {
        return Err("--input is required".to_owned());
    }
    let csv_output = csv_output.ok_or_else(|| "--csv-output is required".to_owned())?;
    let md_output = md_output.ok_or_else(|| "--md-output is required".to_owned())?;

    let rows = load_rows(&inputs)?;
    write_csv(&csv_output, &rows)?;
    write_markdown(&md_output, &rows)
}

fn load_rows(paths: &[PathBuf]) -> Result<Vec<InstanceRows>, String> {
    let mut order = Vec::new();
    let mut grouped: HashMap<String, InstanceRows> = HashMap::new();

    for path in paths {
        let text = fs::read_to_string(path)
            .map_err(|err| format!("failed to read {}: {err}", path.display()))?;
        let mut lines = text.lines();
        let header = lines
            .next()
            .ok_or_else(|| format!("{} is empty", path.display()))?;
        let headers = parse_csv_line(header);

        for line in lines {
            if line.trim().is_empty() {
                continue;
            }
            let fields = parse_csv_line(line);
            let get = |name: &str| -> Result<String, String> {
                let index = headers
                    .iter()
                    .position(|header| header == name)
                    .ok_or_else(|| format!("{} missing CSV header {name}", path.display()))?;
                fields
                    .get(index)
                    .cloned()
                    .ok_or_else(|| format!("missing field {name} in line {line}"))
            };

            let instance_id = get("instance_id")?;
            let method = get("method")?;
            if !grouped.contains_key(&instance_id) {
                order.push(instance_id.clone());
            }
            let entry = grouped
                .entry(instance_id.clone())
                .or_insert_with(|| InstanceRows {
                    instance_id: instance_id.clone(),
                    n: get("n").unwrap_or_default(),
                    k: get("k").unwrap_or_default(),
                    expected: get("expected_distance").unwrap_or_default(),
                    expected_bound_type: get("expected_bound_type").unwrap_or_default(),
                    ..InstanceRows::default()
                });
            let cell = MethodCell {
                status: get("status")?,
                distance: get("computed_distance")?,
                elapsed_ms: get("elapsed_ms")?,
            };
            match method.as_str() {
                "random-window-upper-bound" => entry.random_window = Some(cell),
                "codedistance-QDistRndMW" => entry.codedistance_qdist_rnd_mw = Some(cell),
                "codedistance-QDistEvol" => entry.codedistance_qdist_evol = Some(cell),
                "codedistance-decoderDist" => entry.codedistance_decoder_dist = Some(cell),
                _ => {}
            }
        }
    }

    let mut rows = Vec::new();
    for instance_id in order {
        if let Some(row) = grouped.remove(&instance_id) {
            rows.push(row);
        }
    }
    Ok(rows)
}

fn write_csv(path: &PathBuf, rows: &[InstanceRows]) -> Result<(), String> {
    let mut lines = vec![
        "instance_id,n,k,expected,expected_bound_type,random_window,random_window_ms,codedistance_QDistRndMW,codedistance_QDistRndMW_ms,codedistance_QDistEvol,codedistance_QDistEvol_ms,codedistance_decoderDist,codedistance_decoderDist_ms"
            .to_owned(),
    ];
    for row in rows {
        lines.push(
            [
                row.instance_id.clone(),
                row.n.clone(),
                row.k.clone(),
                row.expected.clone(),
                row.expected_bound_type.clone(),
                cell_value(row.random_window.as_ref()),
                cell_ms(row.random_window.as_ref()),
                cell_value(row.codedistance_qdist_rnd_mw.as_ref()),
                cell_ms(row.codedistance_qdist_rnd_mw.as_ref()),
                cell_value(row.codedistance_qdist_evol.as_ref()),
                cell_ms(row.codedistance_qdist_evol.as_ref()),
                cell_value(row.codedistance_decoder_dist.as_ref()),
                cell_ms(row.codedistance_decoder_dist.as_ref()),
            ]
            .iter()
            .map(|field| csv_escape(field))
            .collect::<Vec<_>>()
            .join(","),
        );
    }
    write_text(path, format!("{}\n", lines.join("\n")))
}

fn write_markdown(path: &PathBuf, rows: &[InstanceRows]) -> Result<(), String> {
    let mut lines = vec![
        "| instance | n | k | expected | random-window | QDistRndMW | QDistEvol | decoderDist |"
            .to_owned(),
        "|---|---:|---:|---:|---:|---:|---:|---:|".to_owned(),
    ];
    for row in rows {
        lines.push(format!(
            "| {} | {} | {} | {} {} | {} | {} | {} | {} |",
            row.instance_id,
            row.n,
            row.k,
            row.expected,
            row.expected_bound_type,
            md_cell(row.random_window.as_ref()),
            md_cell(row.codedistance_qdist_rnd_mw.as_ref()),
            md_cell(row.codedistance_qdist_evol.as_ref()),
            md_cell(row.codedistance_decoder_dist.as_ref())
        ));
    }
    write_text(path, format!("{}\n", lines.join("\n")))
}

fn cell_value(cell: Option<&MethodCell>) -> String {
    match cell {
        Some(cell) if cell.status == "completed" => format!("d={}", cell.distance),
        Some(cell) => cell.status.clone(),
        None => "missing".to_owned(),
    }
}

fn cell_ms(cell: Option<&MethodCell>) -> String {
    cell.map(|cell| cell.elapsed_ms.clone()).unwrap_or_default()
}

fn md_cell(cell: Option<&MethodCell>) -> String {
    match cell {
        Some(cell) if cell.status == "completed" => {
            format!("d={} / {} ms", cell.distance, cell.elapsed_ms)
        }
        Some(cell) => format!("{} / {} ms", cell.status, cell.elapsed_ms),
        None => "missing".to_owned(),
    }
}

fn parse_csv_line(line: &str) -> Vec<String> {
    let mut fields = Vec::new();
    let mut field = String::new();
    let mut chars = line.chars().peekable();
    let mut in_quotes = false;

    while let Some(ch) = chars.next() {
        match ch {
            '"' if in_quotes && chars.peek() == Some(&'"') => {
                field.push('"');
                chars.next();
            }
            '"' => in_quotes = !in_quotes,
            ',' if !in_quotes => {
                fields.push(field);
                field = String::new();
            }
            _ => field.push(ch),
        }
    }
    fields.push(field);
    fields
}

fn csv_escape(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_owned()
    }
}

fn write_text(path: &PathBuf, text: String) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
    }
    fs::write(path, text).map_err(|err| format!("failed to write {}: {err}", path.display()))
}

fn usage() -> String {
    "usage: autoqec-distance-wide --input <csv> [--input <csv> ...] --csv-output <path> --md-output <path>".to_owned()
}
