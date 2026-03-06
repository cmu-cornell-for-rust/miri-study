use crate::dhat_lib::*;
use serde::Serialize;
use std::{
    collections::HashMap, fs::{File}, path::PathBuf, io::Write
};

// Record to be written to CSV
#[derive(Default, Serialize)]
pub(crate) struct CSVLine {
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

pub fn log_fn_stats(dhat: &Dhat, test_params: TestParams) -> Result<CSVLine, Box<dyn std::error::Error>> {
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

pub fn get_most_freq_fns(points: &Vec<PP>, filter: Option<&str>) -> Vec<(String, usize)> {
    let mut freq: HashMap<String, usize> = HashMap::new();
    for point in points {
        if let Some(name) = filter {
            if point.frames.iter().any(|f| !f.contains(name)) {
                continue
            }
        }

        if let Some(frame) = point.frames.get(1) {
            if let Some(last_part) = frame.split("::").last() {
                if let Some(top_lvl_fn) = last_part.split_once(char::is_whitespace) {
                    freq.entry(top_lvl_fn.0.to_string()).and_modify(|count| *count += 1).or_insert(1);
                }
            }
        }
    }
    
    let mut sorted: Vec<(String, usize)> = freq.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1));
    sorted
}

pub fn get_fn_stats(points: &Vec<PP>, fn_name: &String) -> HLFunction {

    let any_contains = points
        .iter()
        .filter(|pp| pp.frames.iter().any(|frame| frame.contains(fn_name)))
        .collect::<Vec<_>>();

    let top_contains = points
        .iter()
        .filter(|pp| pp.frames.get(1).unwrap_or(&"".to_string()).contains(fn_name))
        .collect::<Vec<_>>();

    let count = any_contains.len();
    let count_top = top_contains.len();
    let bytes: u64 = any_contains.iter().map(|pp| pp.bytes).sum();
    let bytes_top: u64 = top_contains.iter().map(|pp| pp.bytes).sum();
    
    println!("Points with '{}': {} ({:.2} MB)", fn_name, count, bytes as f64 / 1_048_576.0);

    HLFunction::new(fn_name.clone(), bytes, bytes_top, count, count_top)
}

pub fn sort_by_memory(dhat: &Dhat) -> Result<Vec<PP>, Box<dyn std::error::Error>> {
    
    let mut memory_usage: Vec<_> = dhat.program_points.iter()
        .enumerate()
        .map(|(idx, pp)| (idx, pp.total_bytes))
        .collect();
    
    // Sort by total bytes (descending)
    memory_usage.sort_by(|a, b| b.1.cmp(&a.1));
    
    let mut points = Vec::new();

    for (i, (idx, bytes)) in memory_usage.iter().enumerate() {
        let pp = &dhat.program_points[*idx];
        let saved_pp = PP {
            rank: i+1,
            bytes: *bytes,
            frames: pp.frames.iter()
                .filter_map(|&frame_idx| dhat.frame_table.get(frame_idx))
                .cloned()
                .collect(),
        };
        points.push(saved_pp);
    }
    
    Ok(points)
}

pub fn _fn_pattern(frame: &str, fn_name: &str) -> bool {
    if let Some(last_part) = frame.split("::").last() {
        if let Some(top_lvl_fn) = last_part.split_once(char::is_whitespace) {
            return top_lvl_fn.0.contains(fn_name);
        }
    }
    false
}


pub fn _calculate_total_memory(dhat: &Dhat) -> (u64, u64, Option<usize>) {
    
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

pub fn _print_top_memory(dhat: &Dhat, output_file: &str) -> Result<(), Box<dyn std::error::Error>> {
    
    let writer = &mut File::create(&PathBuf::from(output_file))? as &mut dyn Write;

    if let Ok(points) = sort_by_memory(dhat) {
        for point in points {
            writeln!(writer, "#{}: {} bytes", point.rank, point.bytes)?;
            for frame in point.frames {
                writeln!(writer, "\t{}", frame)?;
            }
        }
    }
    
    Ok(())
}