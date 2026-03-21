#!/bin/bash

apk_path="vendor/gms/common/proprietary"

find "${apk_path}" -type f -name "*.part00" | while read -r firstpart; do
    outfile="${firstpart%.part00}"
    cat "${outfile}".part* > "$outfile"
    rm -f "${outfile}".part*
done
