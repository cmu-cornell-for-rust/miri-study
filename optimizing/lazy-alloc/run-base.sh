#!/usr/bin/env bash
# bench_miri.sh — run all crates sequentially for builds: base, lazy, lazy2
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SCRATCH="/scratch/user/u.mm346025"
TEAM_SCRATCH="/scratch/group/p.cis260229.000"
BASE_CARGO_HOME="$SCRATCH/.cargo"
RUSTUP_HOME="$SCRATCH/.rustup"
MIRIFLAGS="-Zmiri-disable-alignment-check -Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-disable-stacked-borrows -Zmiri-ignore-leaks"
BUILDS=("base")
CSV="$(pwd)/results.csv"
CRATES_ROOT="$(pwd)"

# ── Validate SIFs ─────────────────────────────────────────────────────────────
for BUILD in "${BUILDS[@]}"; do
    SIF="$SCRATCH/${BUILD}.sif"
    if [[ ! -f "$SIF" ]]; then
        echo "Error: SIF not found at $SIF" >&2
        exit 1
    fi
done

# ── CSV header ────────────────────────────────────────────────────────────────
if [[ ! -f "$CSV" ]]; then
    echo "build,crate,status,elapsed_seconds,timestamp,job_id" > "$CSV"
fi

# ── Collect crate names ───────────────────────────────────────────────────────
CRATE_DIRS=()
for dir in "$CRATES_ROOT"/*/; do
    [[ -d "$dir" ]] || continue
    CRATE_DIRS+=("${dir%/}")
done

if [[ ${#CRATE_DIRS[@]} -eq 0 ]]; then
    echo "Error: no crate subdirectories found in $CRATES_ROOT" >&2
    exit 1
fi

# ── Write single job script ───────────────────────────────────────────────────
JOBSCRIPT="$CRATES_ROOT/_sbatch_all.sh"

cat > "$JOBSCRIPT" <<'HEADER'
#!/usr/bin/env bash
#SBATCH --job-name=dev-all
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00

set -euo pipefail
module load WebProxy
HEADER

# Embed config vars into the job script (expand now, at submission time)
cat >> "$JOBSCRIPT" <<VARS

SCRATCH="${SCRATCH}"
BASE_CARGO_HOME="${BASE_CARGO_HOME}"
RUSTUP_HOME="${RUSTUP_HOME}"
MIRIFLAGS="${MIRIFLAGS}"
CSV="${CSV}"
CRATES_ROOT="${CRATES_ROOT}"
BUILDS=(${BUILDS[*]})
CRATE_DIRS=($(printf '"%s" ' "${CRATE_DIRS[@]}"))

VARS

cat >> "$JOBSCRIPT" <<'BODY'

echo "[$(date -u)] Starting bench run: ${#BUILDS[@]} builds × ${#CRATE_DIRS[@]} crates"

for BUILD in "${BUILDS[@]}"; do
    SIF="$SCRATCH/${BUILD}.sif"
    echo ""
    echo "════════════════════════════════════════"
    echo "[$(date -u)] Build: $BUILD  SIF: $SIF"
    echo "════════════════════════════════════════"

    for CRATE_PATH in "${CRATE_DIRS[@]}"; do
        CRATE="$(basename "$CRATE_PATH")"
        echo ""
        echo "── [$(date -u)] $BUILD / $CRATE ──"

        singularity exec \
            --env CARGO_HOME="$BASE_CARGO_HOME" \
            --env RUSTUP_HOME="$RUSTUP_HOME" \
            "$SIF" bash -c "
set -euo pipefail
cd '${CRATE_PATH}'
cargo clean
cargo fetch
cargo build
if [[ '${CRATE}' == 'hashbrown-0.16.1' ]]; then
    EFFECTIVE_MIRIFLAGS=\"-Zmiri-disable-alignment-check -Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows -Zmiri-ignore-leaks -Zmiri-strict-provenance\"
else
    EFFECTIVE_MIRIFLAGS='${MIRIFLAGS}'
fi
start=\$(date +%s%3N)
if MIRIFLAGS=\"\$EFFECTIVE_MIRIFLAGS\" cargo miri test --lib --tests 2>/dev/null; then
    status='success'
else
    status='failed'
fi
end=\$(date +%s%3N)
elapsed=\$((end - start))
ts=\$(date -u +'%Y-%m-%dT%H:%M:%SZ')
echo \"${BUILD},${CRATE},\$status,\$elapsed,\$ts,\$SLURM_JOB_ID\" >> '${CSV}'
echo \"  → \$status in \${elapsed}s\"
"
    done
done

echo ""
echo "[$(date -u)] All done."
BODY

chmod +x "$JOBSCRIPT"

JOB_ID=$(sbatch --wait "$JOBSCRIPT" | awk '{print $NF}')
echo "Submitted all builds → job $JOB_ID"
echo ""
echo "Monitor queue:     squeue -u \$USER -j $JOB_ID"
echo "Watch results:     tail -f $CSV"
echo "Formatted results: column -t -s, $CSV"
