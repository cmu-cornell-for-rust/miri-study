#!/usr/bin/env bash
# bench_miri.sh — submit one sbatch job per crate subdirectory
set -euo pipefail
# ── Config ────────────────────────────────────────────────────────────────────
SCRATCH="/scratch/user/u.mm346025"
SIF="$SCRATCH/tree-timing.sif"
CARGO_HOME="$SCRATCH/.cargo"
RUSTUP_HOME="$SCRATCH/.rustup"
CSV="$(pwd)/results.csv"
DEFAULT_MIRIFLAGS="-Zmiri-disable-alignment-check -Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows -Zmiri-ignore-leaks"
# ─────────────────────────────────────────────────────────────────────────────
if [[ ! -f "$CSV" ]]; then
echo "crate,status,elapsed_seconds,timestamp,job_id,error_msg" > "$CSV"
fi
for dir in */; do
    MIRIFLAGS="$DEFAULT_MIRIFLAGS"
    [[ -d "$dir" ]] || continue
    crate="${dir%/}"
    if [[ "$crate" == "hashbrown-0.16.1" ]]; then
        MIRIFLAGS="$DEFAULT_MIRIFLAGS -Zmiri-strict-provenance"
    fi
crate_path="$(pwd)/$crate"
jobscript="$crate_path/_sbatch.sh"
cat > "$jobscript" <<JOB
#!/usr/bin/env bash
#SBATCH --job-name=miri-${crate}
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=${crate_path}/miri_%j.log
#SBATCH --error=${crate_path}/miri_%j.err
module load WebProxy
singularity exec \
    --env CARGO_HOME="$CARGO_HOME" \
    --env RUSTUP_HOME="$RUSTUP_HOME" \
    "$SIF" bash -c 'cargo miri setup'
set -euo pipefail
cd "${crate_path}"
rm traces-* && rm events-*
cargo clean
cargo fetch
start=\$(date +%s)
stderr_file=\$(mktemp)
if MIRIFLAGS="${MIRIFLAGS}" MIRI_TRACING=1 RUSTC_LOG=miri=trace cargo miri test --lib --tests 2>"\$stderr_file"; then
    status="success"
    error_msg=""
else
    status="failed"
    error_msg=\$(grep -v "^\s*\$" "\$stderr_file" | tail -1 | sed "s/,/ /g")
fi
rm -f "\$stderr_file"
end=\$(date +%s)
elapsed=\$((end - start))
ts=\$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${crate},\$status,\$elapsed,\$ts,\$SLURM_JOB_ID,\"\$error_msg\"" >> "${CSV}"
'
JOB
chmod +x "$jobscript"
job_id=$(sbatch "$jobscript" | awk '{print $NF}')
echo "Submitted $crate → job $job_id"
done
echo ""
echo "Monitor queue:     squeue -u \$USER"
echo "Watch results:     tail -f $CSV"
echo "Formatted results: column -t -s, $CSV"