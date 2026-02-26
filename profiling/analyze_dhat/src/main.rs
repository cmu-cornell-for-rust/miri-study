use serde::{Serialize};
use std::{
    hash::Hash, fs::{self}, path::{Path, PathBuf}
};
use crate::utils::*;
use dhat::Dhat;
mod dhat;
mod utils;
mod callgrind;

// A simplified representation of a ProgramPoint from DHAT
struct PP {
    rank: usize,
    bytes: u64,
    frames: Vec<String>,
}

// Data on some high-level function
// top = if the function is at the top of the stack (i.e. frames[1])
#[derive(Serialize, Default)]
struct HLFunction {
    name: String,
    bytes: u64,
    bytes_top: u64,
    count: usize,
    count_top: usize,
    avg: f64,
    avg_top: f64,
}

impl HLFunction {
    fn to_csv(&self) -> String {
        serde_json::json!({
            "bytes": self.bytes,
            "bytes_top": self.bytes_top,
            "count": self.count,
            "count_top": self.count_top,
            "avg": self.avg,
            "avg_top": self.avg_top
        }).to_string()
    }
}

// Record to be written to CSV
#[derive(Default, Serialize)]
struct CSVLine {
    config: String,
    file: String,
    testname: String,
    total_points: usize,
    total_bytes: u64,
    insert_allocation: String,
    new_allocation: String,
    grow_amortized: String,
    grow_one: String,
    finish_grow: String,
    add_name: String,
    tree_new: String,
    b_retag: String,
    eval_callee: String,
    provenance_gc: String,
    perform_transition: String,
    miri_machine: String,
}

// Parameters extracted from the filename
#[derive(PartialEq, Eq, Hash, Serialize, Default)]
struct TestParams {
    config: String,
    file: String,
    testname: String,
}

impl From<&str> for TestParams {
    fn from(path: &str) -> Self {
        let parts: Vec<&str> = path
            .split('/')
            .last()
            .unwrap_or("")
            .split('.')
            .collect();
        
        TestParams {
            config: parts.get(0).unwrap_or(&"").to_string(),
            file: parts.get(1).unwrap_or(&"").to_string(),
            testname: parts.get(2).unwrap_or(&"").to_string(),
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let outputs_dir = "/workspaces/miri-study/profiling/libc-outputs/dhat";
    process_dhat_folder(outputs_dir)?;
    Ok(())
}

fn log_fn_stats(dhat: &Dhat, test_params: TestParams) -> Result<CSVLine, Box<dyn std::error::Error>> {
    let points = sort_by_memory(dhat)?;
    
    let total_points = points.len();
    let total_bytes: u64 = dhat.program_points.iter().map(|pp| pp.total_bytes).sum();
    println!("Total memory points: {} ({:.2} MB)", total_points, total_bytes as f64 / 1_048_576.0);

    let insert_allocation = get_fn_stats(&points, &"insert_allocation".to_string()).to_csv();
    // Children of insert_allocation:    
    let new_allocation = get_fn_stats(&points, &"new_allocation".to_string()).to_csv();
    let grow_amortized = get_fn_stats(&points, &"grow_amortized".to_string()).to_csv();
    let grow_one = get_fn_stats(&points, &"grow_one".to_string()).to_csv();
    let finish_grow = get_fn_stats(&points, &"finish_grow".to_string()).to_csv();
    let add_name = get_fn_stats(&points, &"add_name".to_string()).to_csv();
    let tree_new = get_fn_stats(&points, &"Tree>::new".to_string()).to_csv();

    let b_retag = get_fn_stats(&points, &"b_retag".to_string()).to_csv();
    let eval_callee = get_fn_stats(&points, &"eval_callee_and_args".to_string()).to_csv();
    let provenance_gc = get_fn_stats(&points, &"provenance_gc".to_string()).to_csv();
    let perform_transition = get_fn_stats(&points, &"perform_transition".to_string()).to_csv();
    let miri_machine = get_fn_stats(&points, &"MiriMachine".to_string()).to_csv();

    let freq = get_most_freq_fns(&points, None);
    println!("Most frequent functions:");
    for (fn_name, count) in freq.iter().take(10) {
        println!("{}: {} points", fn_name, count);
    }

    let csv_line = CSVLine {
        config: test_params.config,
        file: test_params.file,
        testname: test_params.testname,
        total_points,
        total_bytes,
        insert_allocation,
        new_allocation,
        grow_amortized,
        grow_one,
        finish_grow,
        add_name,
        tree_new,
        b_retag,
        eval_callee,
        provenance_gc,
        perform_transition,
        miri_machine,
    };
    Ok(csv_line)
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