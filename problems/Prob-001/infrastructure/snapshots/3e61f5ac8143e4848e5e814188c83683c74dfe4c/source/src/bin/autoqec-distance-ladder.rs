use std::env;
use std::path::PathBuf;

use autoqec_tools::distance_ladder::{export_distance_ladder, ExportOptions};

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        return Err(usage());
    };
    if command != "export" {
        return Err(usage());
    }

    let mut manifest_path = None;
    let mut qec_code_bin = PathBuf::from("qec-code");
    let mut force = false;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--manifest" => {
                manifest_path = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--manifest requires a path".to_owned())?,
                ));
            }
            "--qec-code-bin" => {
                qec_code_bin = PathBuf::from(
                    args.next()
                        .ok_or_else(|| "--qec-code-bin requires a path".to_owned())?,
                );
            }
            "--force" => {
                force = true;
            }
            _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
        }
    }

    let manifest_path = manifest_path.ok_or_else(|| "--manifest is required".to_owned())?;
    let summary = export_distance_ladder(ExportOptions {
        manifest_path,
        qec_code_bin,
        force,
    })?;

    println!(
        "exported {} instances under {}",
        summary.instances_written,
        summary.artifact_root.display()
    );
    println!(
        "wrote {} result-template rows to {}",
        summary.results_table_rows,
        summary.results_table.display()
    );
    Ok(())
}

fn usage() -> String {
    "usage: autoqec-distance-ladder export --manifest <path> [--qec-code-bin <path>] [--force]"
        .to_owned()
}
