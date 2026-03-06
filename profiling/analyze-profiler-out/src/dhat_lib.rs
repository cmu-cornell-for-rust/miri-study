use serde::{Serialize, Deserialize};

// A simplified representation of a ProgramPoint from DHAT
#[allow(unused)]
pub(crate)struct PP {
    pub(crate)rank: usize,
    pub(crate) bytes: u64,
    pub(crate) frames: Vec<String>,
}

// Data on some high-level function
// top = if the function is at the top of the stack (i.e. frames[1])
#[derive(Serialize, Default)]
pub(crate) struct HLFunction {
    name: String,
    bytes: u64,
    bytes_top: u64,
    count: usize,
    count_top: usize,
    avg: f64,
    avg_top: f64,
}

impl HLFunction {
    pub(crate) fn to_csv(&self) -> String {
        serde_json::json!({
            "bytes": self.bytes,
            "bytes_top": self.bytes_top,
            "count": self.count,
            "count_top": self.count_top,
            "avg": self.avg,
            "avg_top": self.avg_top
        }).to_string()
    }

    pub(crate) fn new(name: String, bytes: u64, bytes_top: u64, count: usize, count_top: usize) -> Self {
        let avg = if count > 0 { bytes as f64 / count as f64 } else { 0.0 };
        let avg_top = if count_top > 0 { bytes_top as f64 / count_top as f64 } else { 0.0 };
        HLFunction {
            name,
            bytes,
            bytes_top,
            count,
            count_top,
            avg,
            avg_top
        }
    }
}


// Parameters extracted from the filename
#[derive(PartialEq, Eq, Hash, Serialize, Default)]
pub(crate) struct TestParams {
    pub(crate) config: String,
    pub(crate) file: String,
    pub(crate) testname: String,
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

/// A Rust representation of DHAT's JSON file format, which is described in
/// comments in dhat/dh_main.c in Valgrind's source code.
///
/// Building this structure in order to serialize does take up some memory. We
/// could instead stream the JSON output directly to file ourselves. This would
/// be more efficient but make the code uglier.
// Copied from https://github.com/nnethercote/dhat-rs/blob/b536631fd9d9103d7191b63181f67755b5958ab5/src/lib.rs#L1826
#[derive(Deserialize, Debug)]
#[allow(non_snake_case, dead_code)]
pub(crate) struct Dhat {
    /// Version number of the format. Incremented on each
    /// backwards-incompatible change. A mandatory integer.
    pub(crate) dhatFileVersion: u32,
    /// The invocation mode. A mandatory, free-form string.
    pub(crate) mode: String,
    /// The verb used before above stack frames, i.e. "<verb> at {". A
    /// mandatory string.
    pub(crate) verb: String,
    /// Are block lifetimes recorded? Affects whether some other fields are
    /// present. A mandatory boolean.
    pub(crate) bklt: bool,
    /// Are block accesses recorded? Affects whether some other fields are
    /// present. A mandatory boolean.
    pub(crate) bkacc: bool,
    /// Byte/bytes/blocks-position units. Optional strings. "byte", "bytes",
    /// and "blocks" are the values used if these fields are omitted.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) bu: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) bsu: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) bksu: Option<String>,
    // Time units (individual and 1,000,000x). Mandatory strings.
    pub(crate) tu: String,
    pub(crate) Mtu: String,
    /// The "short-lived" time threshold, measures in "tu"s.
    /// - bklt=true: a mandatory integer.
    /// - bklt=false: omitted.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) tuth: Option<usize>,
    /// The executed command. A mandatory string.
    pub(crate) cmd: String,
    // The process ID. A mandatory integer.
    pub(crate) pid: u32,
    /// The time of the global max (t-gmax).
    /// - bklt=true: a mandatory integer.
    /// - bklt=false: omitted.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) tg: Option<u128>,
    /// The time at the end of execution (t-end). A mandatory integer.
    pub(crate) te: u128,
    /// The program points. A mandatory array.
    #[serde(rename = "pps")]
    pub(crate) program_points: Vec<ProgramPoint>,
    /// Frame table. A mandatory array of strings.
    #[serde(rename = "ftbl")]
    pub(crate) frame_table: Vec<String>,
}

// A Rust representation of a PpInfo within DHAT's JSON file format.
#[derive(Deserialize, Debug)]
#[allow(non_snake_case, dead_code)]
pub(crate) struct ProgramPoint {
    /// Total bytes and blocks. Mandatory integers.
    #[serde(rename = "tb")]
    pub(crate) total_bytes: u64,
    #[serde(rename = "tbk")]
    pub(crate) total_blocks: u64,

    /// Total lifetimes of all blocks allocated at this PP.
    /// - bklt=true: a mandatory integer.
    /// - bklt=false: omitted.
    // Derived from `PpInfo::total_lifetimes_duration`.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "tl")]
    pub(crate) total_lifetimes: Option<u128>,

    /// The maximum bytes and blocks for this PP.
    /// - bklt=true: mandatory integers.
    /// - bklt=false: omitted.
    // `PpInfo::max_bytes` and `PpInfo::max_blocks`.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "mb")]
    pub(crate) max_bytes: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "mbk")]
    pub(crate) max_blocks: Option<usize>,

    /// The bytes and blocks at t-gmax for this PP.
    /// - bklt=true: mandatory integers.
    /// - bklt=false: omitted.
    // `PpInfo::at_tgmax_bytes` and `PpInfo::at_tgmax_blocks`.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "gb")]
    pub(crate) heap_max_bytes: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "gbk")]
    pub(crate) heap_max_blocks: Option<usize>,

    /// The bytes and blocks at t-end for this PP.
    /// - bklt=true: mandatory integers.
    /// - bklt=false: omitted.
    // `PpInfo::curr_bytes` and `PpInfo::curr_blocks` (at termination, i.e.
    // "end").
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "eb")]
    pub(crate) end_bytes: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "ebk")]
    pub(crate) end_blocks: Option<usize>,

    // Frames. Each element is an index into `ftbl`.
    #[serde(rename = "fs")]
    pub(crate) frames: Vec<usize>,
}