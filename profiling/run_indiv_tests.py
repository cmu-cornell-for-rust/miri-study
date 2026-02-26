#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# Runs each test individually with the specified tool (dhat or callgrind).
# Output files and timestamps csv in {project}-outputs/{tool}/
# ------------------------------------------------------------------------------

from collections import defaultdict
from pathlib import Path
import subprocess
import re
import sys
import os
import csv


def run_command(cmd, cwd, output_dir):
    """Run a command with output redirected to the specified directory."""
    result = subprocess.run(
        cmd, 
        cwd=str(cwd), 
        shell=True, 
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, 'OUTPUT_DIR': str(output_dir)}
    )
    return result

def get_tests(project_dir):
    result = subprocess.run(
        ['cargo', 'test', '--', '--list'],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    binary_to_tests = defaultdict(list)
    current_binary = None

    for line in result.stdout.splitlines():
        running_match = re.search(r'Running.*?/(\w+)\.rs', line)
        if running_match:
            current_binary = running_match.group(1)
            print(f"Found binary: {current_binary}")
            continue
        
        test_match = re.match(r'^(\S+): test$', line)
        if test_match and current_binary:
            test_name = test_match.group(1)
            binary_to_tests[current_binary].append(test_name)
            print(f"  Found test: {current_binary}::{test_name}")
    
    binary_to_tests = dict(binary_to_tests)
    return binary_to_tests

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 run_indiv_tests.py <tool> <project_dir>")
        print("Example: python3 run_indiv_tests.py dhat libc-1.0.0")
        print("         python3 run_indiv_tests.py callgrind libc-1.0.0")
        sys.exit(1)
    
    tool = sys.argv[1]
    tool = tool.lower()
    if tool == "dhat":
        cmd_line = 5
    elif tool == "callgrind":
        cmd_line = 4
    elif tool == "perf":
        pass
    else:
        print(f"Unknown tool: {tool}")
        sys.exit(1)

    project_dir = Path(sys.argv[2]).resolve()
    if not project_dir.is_dir():
        print(f"Error: Directory {project_dir} does not exist")
        sys.exit(1)

    script_dir = Path(__file__).parent
    output_dir = script_dir / "outputs" / project_dir.name / tool
    output_dir.mkdir(parents=True, exist_ok=True)

    bin_tests = get_tests(project_dir)
    test_timestamps = []
    
    def iterate_tests(name, miri, skip, skip_by_arg, miri_flags):
        if miri:
            miri_cmd = "miri"
        else:
            miri_cmd = ""
        for binary, tests in bin_tests.items():
            if binary == "lib":
                bin_arg = "--lib"
            else:
                bin_arg = f"--test {binary}"
            for test_name in tests:
                safe_name = test_name.replace("::", "-")
                output_file = output_dir / f"{name}.{binary}.{safe_name}.{tool}"
                if tool.lower() == "perf":
                    cmd = f"""{miri_flags} perf record \
                            --call-graph dwarf \
                            -F 99 \
                            -e cycles \
                            -o {output_file}.dat \
                            -- cargo {miri_cmd} test {bin_arg} {test_name} -- --exact"""
                    result = run_command(cmd, project_dir, output_dir)

                    duration_string = run_command(
                        f"perf report --header-only -i {output_file}.dat | grep 'sample duration'", 
                        output_dir, 
                        output_dir
                    ).stdout.strip()
                    if re.match(r'#\s+sample duration\s*:\s+[\d.]+\s+ms', duration_string):
                        duration_ms = duration_string.split()[4]
                        duration_s = float(duration_ms) / 1000
                        test_timestamps.append({
                            'config': name,
                            'file': binary,
                            'testname': test_name,
                            'timestamp': duration_s
                        })
                        print(f"{tool} {name}: {binary}::{test_name} finished in: {duration_s}s")
                    else:
                        print(f"Duration string did not match expected format: {duration_string}")

                else:
                    cmd = f"""{miri_flags} valgrind --tool={tool} \
                                --time-stamp=yes \
                                --trace-children=yes \
                                --trace-children-skip={skip} \
                                --trace-children-skip-by-arg={skip_by_arg} \
                                --{tool}-out-file={output_file}.out.%p \
                                cargo {miri_cmd} test {bin_arg} {test_name} -- --exact"""
                    result = run_command(cmd, project_dir, output_dir)

                
                    # Extract timestamp from output
                    lines = result.stdout.splitlines()
                    for i, line in enumerate(lines):
                        if re.search(r'==\d{2}:\d{2}:\d{2}:\d{2}\.\d+ +\d+== (Total:|Events)', line):
                            if i > 0: 
                                timestamp_line = lines[i - 1]
                                timestamp_match = re.search(r'==(\d{2}:\d{2}:\d{2}:\d{2}\.\d{3})', timestamp_line)
                                if timestamp_match:
                                    timestamp = timestamp_match.group(1)
                                    test_timestamps.append({
                                        'config': name,
                                        'file': binary,
                                        'testname': test_name,
                                        'timestamp': timestamp
                                    })
                                    print(f"{tool} {name}: {binary}::{test_name} finished at: {timestamp}")
                            break

                    # Remove cargo compilation output file
                    for file_path in output_dir.glob(f"{name}.{binary}.{safe_name}.{tool}.out.*"):
                        try:
                            with open(file_path, 'r') as f:
                                file_lines = f.readlines()
                                def has_compile_cmd():
                                    if miri:
                                        return not re.search(r'--crate-name\s+(\S+)', file_lines[cmd_line])
                                    else:
                                        return "cargo test" in file_lines[cmd_line]

                                if has_compile_cmd():
                                    file_path.unlink()
                                else:
                                    new_name = output_dir / f"{name}.{binary}.{safe_name}.{tool}.out"
                                    file_path.rename(new_name)
                        except Exception as e:
                            print(f"Error processing {file_path}: {e}")
    
    miri_skip = "*/rustc"
    miri_skip_by_arg = "'--crate-type','-vV','--print','--format-version','--error-format=json'"
    
    print(f"\n[PHASE 1/3] Running default cargo test for all tests")
    iterate_tests("default",
                  False, 
                  "*/rustc,*/build-script-build", 
                  "'--crate-type'", 
                  "")

    print(f"\n[PHASE 2/3] Running cargo miri test for all tests")
    iterate_tests("miri",
                  True, 
                  miri_skip,
                  miri_skip_by_arg, 
                  "export MIRIFLAGS=\"-Zmiri-disable-data-race-detector -Zmiri-disable-validation\" && ")

    
    print(f"\n[PHASE 3/3] Running cargo miri test (tree-borrows) for all tests")
    iterate_tests("miri-tree",
                  True, 
                  miri_skip,
                  miri_skip_by_arg, 
                  "export MIRIFLAGS=\"-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows\" && ")
    
    # Write timestamps to CSV
    csv_path = output_dir / "timestamps.csv"
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['config', 'file', 'testname', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(test_timestamps)
    
    print(f"\nTimestamps written to: {csv_path}")
    print("All tests completed!")

if __name__ == "__main__":
    main()