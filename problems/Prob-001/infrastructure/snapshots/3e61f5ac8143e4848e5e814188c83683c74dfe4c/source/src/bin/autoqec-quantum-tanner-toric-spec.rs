use std::env;
use std::fs;
use std::path::PathBuf;

use serde::Serialize;

#[derive(Debug, Serialize)]
struct QuantumTannerToricSpec {
    fixture_id: String,
    construction_mode: &'static str,
    base_group: ExplicitFiniteGroupSpec,
    a_generator_indices: Vec<usize>,
    b_generator_indices: Vec<usize>,
    local_codes: LocalCodesSpec,
}

#[derive(Debug, Serialize)]
struct ExplicitFiniteGroupSpec {
    name: String,
    element_order: String,
    order: usize,
    identity: usize,
    multiplication_table: Vec<Vec<usize>>,
}

#[derive(Debug, Serialize)]
struct LocalCodesSpec {
    matrix_role: &'static str,
    field: &'static str,
    h_a: Vec<Vec<u8>>,
    h_b: Vec<Vec<u8>>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let mut distance = None;
    let mut output = None;
    let mut fixture_id = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--distance" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--distance requires a value".to_owned())?;
                distance = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| format!("invalid --distance value: {value}"))?,
                );
            }
            "--fixture-id" => {
                fixture_id = Some(
                    args.next()
                        .ok_or_else(|| "--fixture-id requires a value".to_owned())?,
                );
            }
            "--output" => {
                output = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--output requires a path".to_owned())?,
                ));
            }
            _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
        }
    }

    let distance = distance.ok_or_else(|| "--distance is required".to_owned())?;
    if distance < 2 {
        return Err("--distance must be at least 2".to_owned());
    }
    let output = output.ok_or_else(|| "--output is required".to_owned())?;
    let fixture_id = fixture_id.unwrap_or_else(|| format!("quantum_tanner_toric_d{distance}"));

    let spec = build_spec(distance, fixture_id);
    let text = serde_json::to_string_pretty(&spec)
        .map_err(|err| format!("failed to encode spec JSON: {err}"))?;

    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
    }
    fs::write(&output, format!("{text}\n"))
        .map_err(|err| format!("failed to write {}: {err}", output.display()))
}

fn build_spec(distance: usize, fixture_id: String) -> QuantumTannerToricSpec {
    let order = distance * distance;
    QuantumTannerToricSpec {
        fixture_id,
        construction_mode: "lr_cayley_no_cover_v1",
        base_group: ExplicitFiniteGroupSpec {
            name: format!("Z{distance}xZ{distance}"),
            element_order: format!("id = {distance}*x + y for (x,y) in Z{distance} x Z{distance}"),
            order,
            identity: 0,
            multiplication_table: multiplication_table(distance),
        },
        a_generator_indices: vec![distance, distance * (distance - 1)],
        b_generator_indices: vec![1, distance - 1],
        local_codes: LocalCodesSpec {
            matrix_role: "parity_check",
            field: "GF(2)",
            h_a: vec![vec![1, 1]],
            h_b: vec![vec![1, 1]],
        },
    }
}

fn multiplication_table(distance: usize) -> Vec<Vec<usize>> {
    let order = distance * distance;
    let mut table = vec![vec![0; order]; order];
    for left in 0..order {
        let (left_x, left_y) = decode(distance, left);
        for right in 0..order {
            let (right_x, right_y) = decode(distance, right);
            table[left][right] = encode(
                distance,
                (left_x + right_x) % distance,
                (left_y + right_y) % distance,
            );
        }
    }
    table
}

fn encode(distance: usize, x: usize, y: usize) -> usize {
    distance * x + y
}

fn decode(distance: usize, value: usize) -> (usize, usize) {
    (value / distance, value % distance)
}

fn usage() -> String {
    "usage: autoqec-quantum-tanner-toric-spec --distance <d> --output <path> [--fixture-id <id>]"
        .to_owned()
}
