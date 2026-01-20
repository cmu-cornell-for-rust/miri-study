#!/bin/bash

total_functions_used=0
total_expressions_used=0
total_impls_used=0
total_traits_used=0
total_methods_used=0

echo "Functions  Expressions  Impls  Traits  Methods  Dependency"
echo "----------------------------------------------------------"

awk '
BEGIN { process=0 }
/Functions/ { process=1; next }
process && NF>0 {
    split($1, f_arr,"/")
    split($2, e_arr,"/")
    split($3, i_arr,"/")
    split($4, t_arr,"/")
    split($5, m_arr,"/")

    used = f_arr[1]+e_arr[1]+i_arr[1]+t_arr[1]+m_arr[1]

    if (used > 0) {
        line = $0

        regex = "[a-zA-Z0-9_\\-]+[[:space:]]+[0-9]+\\.[0-9]+(\\.[0-9]+)?"
        if (match(line, regex)) {
            crate_name_version = substr(line, RSTART, RLENGTH)

            if(!seen_crate[crate_name_version]++) {
                if(!printed_file[FILENAME]++) {
                    print "\n[" FILENAME "]"
                }
                print line

                total_functions_used += f_arr[1]
                total_expressions_used += e_arr[1]
                total_impls_used += i_arr[1]
                total_traits_used += t_arr[1]
                total_methods_used += m_arr[1]
            }
        }
    }
}

END {
    printf "\nSummary across all files:\n"
    printf "Functions used: %d\n", total_functions_used
    printf "Expressions used: %d\n", total_expressions_used
    printf "Impls used: %d\n", total_impls_used
    printf "Traits used: %d\n", total_traits_used
    printf "Methods used: %d\n", total_methods_used
    printf "\nUnique crate+version (%d): ", length(seen_crate)

    for (c in seen_crate) printf "%s ", c
    printf "\n"
}' unsafe_report*.txt
