use std::fs::File;
use std::io::{BufWriter, Write};
use std::process::{Command, Stdio};

pub fn read_perf(path: &str) -> Result<(), Box<dyn std::error::Error>> {
    let perf = Command::new("perf")
        .args(["report", "--stdio", "--no-children", "-i", ])
        .arg(path)
        .stdout(Stdio::piped())
        .spawn()?;

    let rustfilt = Command::new("rustfilt")
        .stdin(perf.stdout.unwrap())
        .output()?;

    let stdout = String::from_utf8(rustfilt.stdout)?;

    let csv_path = path.replace(".dat", ".csv");
    let file = File::create(&csv_path)?;
    let mut writer = BufWriter::new(file);

    writeln!(writer, "overhead,command,shared_object,symbol")?;

    for line in stdout.lines() {
        if line.contains('%') && (line.contains("[.]") || line.contains("[k]")) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            // Format: "5.10%  command  shared_object  [.]  symbol..."
            if parts.len() >= 5 {
                let overhead = parts[0];
                let command = parts[1];
                let shared_object = parts[2];
                // parts[3] is [.] or [k], symbol starts at parts[4]
                let symbol = parts[4..].join(" ");
                writeln!(writer, "{},{},{},\"{}\"", overhead, command, shared_object, symbol)?;
            }
        }
    }

    println!("Written to {}", csv_path);
    Ok(())
}