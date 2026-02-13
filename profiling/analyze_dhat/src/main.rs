use folded::Folded;
use iter_tools::Itertools;
use metric::Metric;
use serde::{Serialize, Deserialize};
use std::{
    fs::{self, File}, io::Write, path::{Path, PathBuf}, collections::HashMap
};
use unit::Unit;
use dhat::Dhat;

mod dhat;
mod folded;
mod metric;
mod unit;

struct ProgramPoint {
    idx: usize,
    rank: usize,
    bytes: u64,
    frame: Vec<String>,
}

#[derive(Default, Serialize)]
struct CSVLine {
    config: String,
    file: String,
    testname: String,
    time: String,
    total_points: usize,
    total_bytes: u64,
    insert_allocation_points: usize,
    insert_allocation_bytes: u64,
    b_retag_points: usize,
    b_retag_bytes: u64,
    eval_callee_and_args_points: usize,
    eval_callee_and_args_bytes: u64,
    provenance_gc_points: usize,
    provenance_gc_bytes: u64,
    perform_transition_points: usize,
    perform_transition_bytes: u64,
    mirimachine_points: usize,
    mirimachine_bytes: u64,
}

#[derive(Deserialize)]
struct TimestampRecord {
    config: String,
    file: String,
    testname: String,
    timestamp: String,
}

#[derive(PartialEq, Eq, Hash)]
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

fn load_timestamps(dhat_dir: &Path) -> Result<HashMap<TestParams, String>, Box<dyn std::error::Error>> {
    let timestamp_path = dhat_dir.join("timestamps.csv");
    let mut rdr = csv::Reader::from_path(timestamp_path)?;
    
    let mut map = HashMap::new();
    for result in rdr.deserialize() {
        let record: TimestampRecord = result?;
        let key = TestParams {
            config: record.config,
            file: record.file,
            testname: record.testname.replace("::", "-"),
        };
        map.insert(key, record.timestamp);
    }
    
    Ok(map)
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
    
    let timestamp_map = load_timestamps(dhat_dir)?;

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
            let timestamp = timestamp_map.get(&test_params).cloned().unwrap_or_else(|| "unknown".to_string());
            let timestamp_params = TimestampRecord {
                config: test_params.config,
                file: test_params.file,
                testname: test_params.testname,
                timestamp,
            };

            match fs::read_to_string(&dhat_file) {
                Ok(contents) => {
                    match serde_json::from_str::<Dhat>(&contents) {
                        Ok(dhat) => {
                            match log_fn_stats(&dhat, timestamp_params) {
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

fn get_fn_stats(points: &Vec<ProgramPoint>, fn_name: &String) -> (Vec<usize>, u64) {
    let ids = points
        .iter()
        .filter(|pp| pp.frame.iter().any(|frame| frame.contains(fn_name)))
        .map(|pp| pp.rank)
        .collect::<Vec<usize>>();
    let total_bytes: u64 = points
        .iter()
        .filter(|pp| pp.frame.iter().any(|frame| frame.contains(fn_name)))
        .map(|pp| pp.bytes)
        .sum();
    println!("Points with '{}': {} ({:.2} MB)", fn_name, ids.len(), total_bytes as f64 / 1_048_576.0);
    (ids, total_bytes)
}

fn log_fn_stats(dhat: &Dhat, timestamp_params: TimestampRecord) -> Result<CSVLine, Box<dyn std::error::Error>> {
    let points = sort_by_memory(dhat)?;
    
    let total_points = points.len();
    let total_bytes: u64 = dhat.program_points.iter().map(|pp| pp.total_bytes).sum();
    println!("Total memory points: {} ({:.2} MB)", total_points, total_bytes as f64 / 1_048_576.0);
    
    let (allocations, alloc_bytes) = get_fn_stats(&points, &"insert_allocation".to_string());
    let (retag_retags, retag_bytes) = get_fn_stats(&points, &"b_retag".to_string());
    let (eval_callee_args, eval_callee_bytes) = get_fn_stats(&points, &"eval_callee_and_args".to_string());
    let (prov_gc, prov_gc_bytes) = get_fn_stats(&points, &"provenance_gc".to_string());
    let (perform_transition, perform_transition_bytes) = get_fn_stats(&points, &"perform_transition".to_string());
    let (miri_machines, miri_bytes) = get_fn_stats(&points, &"MiriMachine".to_string());
    
    let csv_line = CSVLine {
        config: timestamp_params.config,
        file: timestamp_params.file,
        testname: timestamp_params.testname,
        time: timestamp_params.timestamp,
        total_points,
        total_bytes,
        insert_allocation_points: allocations.len(),
        insert_allocation_bytes: alloc_bytes,
        b_retag_points: retag_retags.len(),
        b_retag_bytes: retag_bytes,
        eval_callee_and_args_points: eval_callee_args.len(),
        eval_callee_and_args_bytes: eval_callee_bytes,
        provenance_gc_points: prov_gc.len(),
        provenance_gc_bytes: prov_gc_bytes,
        perform_transition_points: perform_transition.len(),
        perform_transition_bytes: perform_transition_bytes,
        mirimachine_points: miri_machines.len(),
        mirimachine_bytes: miri_bytes,
    };
    Ok(csv_line)
}

fn sort_by_memory(dhat: &Dhat) -> Result<(Vec<ProgramPoint>), Box<dyn std::error::Error>> {
    
    let mut memory_usage: Vec<_> = dhat.program_points.iter()
        .enumerate()
        .map(|(idx, pp)| (idx, pp.total_bytes))
        .collect();
    
    // Sort by total bytes (descending)
    memory_usage.sort_by(|a, b| b.1.cmp(&a.1));
    
    let mut points = Vec::new();

    for (i, (idx, bytes)) in memory_usage.iter().enumerate() {
        let pp = &dhat.program_points[*idx];
        let saved_pp = ProgramPoint {
            idx: *idx,
            rank: i+1,
            bytes: *bytes,
            frame: pp.frames.iter()
                .filter_map(|&frame_idx| dhat.frame_table.get(frame_idx))
                .cloned()
                .collect(),
        };
        points.push(saved_pp);
    }
    
    Ok(points)
}

fn calculate_total_memory(dhat: &Dhat) -> (u64, u64, Option<usize>) {
    
    // Sum all total_bytes across all program points
    let total_bytes: u64 = dhat.program_points
        .iter()
        .map(|pp| pp.total_bytes)
        .sum();
    
    let total_blocks: u64 = dhat.program_points
        .iter()
        .map(|pp| pp.total_blocks)
        .sum();
    
    println!("Total memory allocated: {} bytes ({:.2} MB)", 
             total_bytes, 
             total_bytes as f64 / 1_048_576.0);
    println!("Total allocations: {} blocks", total_blocks);
    
    if dhat.bklt {
        let peak_bytes: usize = dhat.program_points
            .iter()
            .filter_map(|pp| pp.heap_max_bytes)
            .sum();
        
        println!("Peak memory usage: {} bytes ({:.2} MB)", 
                 peak_bytes,
                 peak_bytes as f64 / 1_048_576.0);
        return (total_bytes, total_blocks, Some(peak_bytes));
    }
    
    (total_bytes, total_blocks, None)
}

fn print_top_memory(dhat: &Dhat, output_file: &str) -> Result<(), Box<dyn std::error::Error>> {
    
    let writer = &mut File::create(&PathBuf::from(output_file))? as &mut dyn Write;

    if let Ok(points) = sort_by_memory(dhat) {
        for point in points {
            writeln!(writer, "#{}: {} bytes", point.rank, point.bytes)?;
            for frame in point.frame {
                writeln!(writer, "\t{}", frame)?;
            }
        }
    }
    
    Ok(())
}

fn print_all(dhat: Dhat) -> Result<(), Box<dyn std::error::Error>>{
    
    let metric = Metric::default();
    let unit = Unit::default();
    let folded = Folded::from_dhat(dhat, metric, unit).to_string();

    let writer = &mut File::create(&PathBuf::from("./output.txt"))? as &mut dyn Write;
    write!(writer, "{folded}")?;
    Ok(())
}