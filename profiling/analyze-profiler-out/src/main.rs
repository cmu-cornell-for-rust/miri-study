use std::{
    fs::{self}, path::{Path, PathBuf}, env
};
use crate::dhat_utils::*;
use crate::dhat_lib::*;
use crate::perf::*;
mod dhat_utils;
mod dhat_lib;
mod callgrind;
mod perf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: {} <dhat|perf> <outputs_dir>", args[0]);
        std::process::exit(1);
    }

    let path = &args[2];

    match args[1].as_str() {
        "dhat" => process_dhat_folder(path)?,
        "perf" => read_perf(path)?,
        // {
        //     for entry in std::fs::read_dir(path)? {
        //         let entry = entry?;
        //         let path = entry.path();
        //         if path.extension().and_then(|e| e.to_str()) == Some("dat") {
        //             read_perf(&path.to_string_lossy())?;
        //         }
        //     }
        // },
        _ => {
            eprintln!("Unknown option '{}'. Expected 'dhat' or 'perf'.", args[1]);
            std::process::exit(1);
        }
    }

    Ok(())
}

fn process_dhat_folder(folder_path: &str) -> Result<(), Box<dyn std::error::Error>> {
    let project_name = folder_path.split('/').nth(4).unwrap_or("unknown_project");
    let dhat_dir = Path::new(folder_path);

    // Create outputs folder in the current project directory
    let outputs_dir = Path::new("outputs");
    fs::create_dir_all(outputs_dir)?;
    let csv_path = outputs_dir.join(format!("{}_memory_stats.csv", project_name));


    if csv_path.exists() {
        fs::remove_file(&csv_path)?;
        println!("Removed existing memory_stats.csv");
    }
    
    // Get all .out files
    let entries = fs::read_dir(dhat_dir)?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| {
            path.extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| ext == "out")
                .unwrap_or(false)
        })
        .collect::<Vec<PathBuf>>();

    // Create writer once and write header
    let file = std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&csv_path)?;
    let mut wtr = csv::Writer::from_writer(file);

    // Process each file
    for dhat_file in entries {
        println!("Processing: {:?}", dhat_file);
        
        if let Some(path_str) = dhat_file.to_str() {
            let test_params = TestParams::from(path_str);

            match fs::read_to_string(&dhat_file) {
                Ok(contents) => {
                    match serde_json::from_str::<Dhat>(&contents) {
                        Ok(dhat) => {
                            match log_fn_stats(&dhat, test_params) {
                                Ok(csv_line) => {
                                    wtr.serialize(csv_line)?;
                                }
                                Err(e) => eprintln!("Error logging stats for {:?}: {}", dhat_file, e),
                            }
                        }
                        Err(e) => eprintln!("Error parsing JSON from {:?}: {}", dhat_file, e),
                    }
                }
                Err(e) => eprintln!("Error reading file {:?}: {}", dhat_file, e),
            }
        }
    }
    
    wtr.flush()?;
    println!("Results written to: {:?}", csv_path);
    Ok(())
}