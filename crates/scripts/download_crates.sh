#!/usr/bin/env bash
set -euo pipefail

FILE="crates_with_unsafe"
if [[ ! -f "$FILE" ]]; then
    echo "File $FILE does not exist!"
    exit 1
fi

last_line=$(grep "^Unique crate+version" "$FILE" | tail -n1)
if [[ -z "$last_line" ]]; then
    echo "No 'Unique crate+version' line found in $FILE"
    exit 1
fi

crate_list=$(echo "$last_line" | sed -E 's/^Unique crate\+version \([0-9]+\): //')
read -r -a tokens <<< "$crate_list"

declare -A crates_seen
for ((i=0; i<${#tokens[@]}; i+=2)); do
    crate="${tokens[i]}"
    version="${tokens[i+1]}"
    if [[ -z "${crates_seen[$crate]+_}" ]]; then
        crates_seen["$crate"]="$version"
    fi
done

mkdir -p downloaded_crates
cd downloaded_crates

for crate in "${!crates_seen[@]}"; do
    version="${crates_seen[$crate]}"
    folder="${crate}-${version}"
    cargo download "${crate}==${version}" --extract --output "$folder" -v || continue
    tar -czf "${folder}.tar.gz" "$folder"
done
