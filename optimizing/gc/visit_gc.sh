#!/usr/bin/env bash
# gc-runs.sh — sweep for all crates in cwd
set -euo pipefail
# ── Config ────────────────────────────────────────────────────────────────────
SCRATCH="/scratch/user/u.mm346025"
TEAM_SCRATCH="/scratch/group/p.cis260229.000"
SIF_NAMES=("visit_gc")
BASE_CARGO_HOME="$SCRATCH/.cargo"
RUSTUP_HOME="$SCRATCH/.rustup"
BASE_MIRIFLAGS="-Zmiri-disable-alignment-check -Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows -Zmiri-ignore-leaks"
# The three gc thresholds to sweep
VISIT_GC_VALUES=(25000 100000 50000)
CRATES_ROOT="$(pwd)"
CSV="$(pwd)/results.csv"

# ── Validate SIFs ────────────────────────────────────────────────────────────
for SIF_NAME in "${SIF_NAMES[@]}"; do
    SIF="$SCRATCH/${SIF_NAME}.sif"
    if [[ ! -f "$SIF" ]]; then
        echo "Error: SIF not found at $SIF" >&2
        exit 1
    fi
done

# ── Collect crate directories ─────────────────────────────────────────────────
CRATE_DIRS=()
for dir in "$CRATES_ROOT"/*/; do
    [[ -d "$dir" ]] || continue
    CRATE_DIRS+=("${dir%/}")
done

if [[ ${#CRATE_DIRS[@]} -eq 0 ]]; then
    echo "Error: no crate subdirectories found in $CRATES_ROOT" >&2
    exit 1
fi

echo "Found ${#CRATE_DIRS[@]} crates: $(printf '%s ' "${CRATE_DIRS[@]##*/}")"

# ── CSV header ────────────────────────────────────────────────────────────────
if [[ ! -f "$CSV" ]]; then
    echo "build,crate,status,elapsed_seconds,timestamp,job_id" > "$CSV"
fi

# ── Write single job script ───────────────────────────────────────────────────
JOBSCRIPT="$(pwd)/_sbatch_gimli_retag.sh"

cat > "$JOBSCRIPT" <<-'HEADER'
#!/usr/bin/env bash
#SBATCH --job-name=miri-gimli-retag
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=16G
#SBATCH --time=6:00:00

set -euo pipefail
module load WebProxy
HEADER

# Embed config vars (expanded at submission time)
cat >> "$JOBSCRIPT" <<-VARS

SCRATCH="${SCRATCH}"
SIF_NAMES=(${SIF_NAMES[*]})
BASE_CARGO_HOME="${BASE_CARGO_HOME}"
RUSTUP_HOME="${RUSTUP_HOME}"
BASE_MIRIFLAGS="${BASE_MIRIFLAGS}"
VISIT_GC_VALUES=(${VISIT_GC_VALUES[*]})
CRATE_DIRS=($(printf '"%s" ' "${CRATE_DIRS[@]}"))
CSV="${CSV}"

VARS

cat >> "$JOBSCRIPT" <<-'BODY'

echo "[$(date -u)] Starting sweep: ${#SIF_NAMES[@]} SIFs × ${VISIT_GC_VALUES[@]} visit-gc values × ${#CRATE_DIRS[@]} crates"

for SIF_NAME in "${SIF_NAMES[@]}"; do
    SIF="$SCRATCH/${SIF_NAME}.sif"
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "[$(date -u)] SIF: $SIF_NAME"
    echo "╚══════════════════════════════════════════╝"

    for GC_VAL in "${VISIT_GC_VALUES[@]}"; do
        EFFECTIVE_MIRIFLAGS="${BASE_MIRIFLAGS} -Zmiri-visit-gc=${GC_VAL}"

        echo ""
        echo "════════════════════════════════════════"
        echo "[$(date -u)] visit-gc=${GC_VAL}  MIRIFLAGS: $EFFECTIVE_MIRIFLAGS"
        echo "════════════════════════════════════════"

        for CRATE_PATH in "${CRATE_DIRS[@]}"; do
            CRATE="$(basename "$CRATE_PATH")"
            BUILD_LABEL="${SIF_NAME}-${GC_VAL}"

            echo ""
            echo "── [$(date -u)] $BUILD_LABEL / $CRATE ──"

            singularity exec \
                --env CARGO_HOME="$BASE_CARGO_HOME" \
                --env RUSTUP_HOME="$RUSTUP_HOME" \
                "$SIF" bash -c "
set -euo pipefail
cd '${CRATE_PATH}'
cargo clean
rm -rf target
cargo fetch
cargo build
start=\$(date +%s%3N)
if MIRIFLAGS='${EFFECTIVE_MIRIFLAGS}' cargo miri test --lib --tests 2>/dev/null; then
    status='success'
else
    status='failed'
fi
end=\$(date +%s%3N)
elapsed=\$(( (end - start) / 1000 ))
ts=\$(date -u +'%Y-%m-%dT%H:%M:%SZ')
echo '${BUILD_LABEL},${CRATE},'\$status','\$elapsed','\$ts','\$SLURM_JOB_ID >> '${CSV}'
echo \"  → \$status in \${elapsed}s\"
"
        done
    done
done

echo ""
echo "[$(date -u)] Sweep complete."
BODY

chmod +x "$JOBSCRIPT"

JOB_ID=$(sbatch --wait "$JOBSCRIPT" | awk '{print $NF}')
echo "Submitted visit-gc sweep → job $JOB_ID"
echo ""
echo "Monitor queue:     squeue -u \$USER -j $JOB_ID"
echo "Watch results:     tail -f $CSV"
echo "Formatted results: column -t -s, $CSV"