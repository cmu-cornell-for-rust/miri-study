use clap::Parser;
use std::{
    fs::{self, File},
    io::Write,
    path::PathBuf,
};

mod dhat;

fn main(){}

// /// Convert dhat JSON output to a flamegraph
// #[derive(Parser)]
// struct Args {
//     /// The dhat JSON file to process
//     input: PathBuf,
//     /// Where to place the output
//     ///
//     /// If not provided then stdout is used.
//     #[clap(short, long)]
//     output: Option<PathBuf>,
//     /// Which output format to use
//     #[clap(short, long)]
//     format: Option<Format>,
//     #[clap(short, long)]
//     metric: Option<Metric>,
//     #[clap(short, long)]
//     unit: Option<Unit>,
// }

// #[derive(clap::ValueEnum, Clone, Copy, Default)]
// enum Format {
//     /// Format as svg (default)
//     #[default]
//     Svg,
//     /// Format as folded stack traces
//     Folded,
// }

// type Error = Box<dyn std::error::Error + Send + Sync + 'static>;

// fn main() -> Result<(), Error> {
//     let Args {
//         input,
//         output,
//         format,
//         metric,
//         unit,
//     } = Args::parse();
//     let file = fs::File::open(input)?;

//     // Convert dhat to lines
//     let dhat: dhat::Dhat = serde_json::from_reader(file)?;
//     let metric = metric.unwrap_or_default();
//     let unit = unit.unwrap_or_default();
//     let folded = Folded::from_dhat(dhat, metric, unit).to_string();

//     // Determine where to write the data to
//     let writer = match &output {
//         Some(output) => &mut File::create(&output)? as &mut dyn Write,
//         None => &mut std::io::stdout(),
//     };

//     // Write the data
//     match format.unwrap_or_default() {
//         Format::Folded => write!(writer, "{folded}")?,
//         Format::Svg => {
//             let mut opts = flamegraph::Options::default();
//             flamegraph::from_lines(&mut opts, folded.lines(), writer)?;
//         }
//     }
//     if let Some(output) = output {
//         eprintln!("wrote {output:?}");
//     }
//     Ok(())
// }