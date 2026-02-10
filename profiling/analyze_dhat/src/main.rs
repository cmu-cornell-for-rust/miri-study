use clap::Parser;
use folded::Folded;
use metric::Metric;
use std::{
    fs::{self, File},
    io::Write,
    path::PathBuf,
};
use unit::Unit;

mod dhat;
mod folded;
mod metric;
mod unit;

type Error = Box<dyn std::error::Error + Send + Sync + 'static>;

fn main() -> Result<(), Error> {

    let input = std::env::args().nth(1).expect("input file is required");
    let output = std::env::args().nth(2);

    let file = fs::File::open(input)?;

    // Convert dhat to lines
    let dhat: dhat::Dhat = serde_json::from_reader(file)?;
    let metric = Metric::default();
    let unit = Unit::default();
    let folded = Folded::from_dhat(dhat, metric, unit).to_string();

    // Determine where to write the data to
    let writer = match &output {
        Some(output) => &mut File::create(&output)? as &mut dyn Write,
        None => &mut std::io::stdout(),
    };

    // Write the data
    write!(writer, "{folded}")?;
    if let Some(output) = output {
        eprintln!("wrote {output:?}");
    }
    Ok(())
}