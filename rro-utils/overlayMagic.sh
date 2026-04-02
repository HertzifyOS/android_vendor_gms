#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: 2022, 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

DEBUG="${DEBUG:-0}"
if [[ "$DEBUG" != 0 ]]; then
    log="/dev/tty"
else
    log="/dev/null"
fi

APK_PATH="$1"
TARGET_PATH="$2"
MY_DIR="$(dirname "$(realpath "$0")")"
GMS_DIR="$(realpath "$MY_DIR/..")"

OVERLAY_MK="${GMS_DIR}/common/overlays.mk"
OVERLAY_DIR="${GMS_DIR}/common/proprietary/product/overlay/"
FOLDER=${TARGET_PATH/.apk/}

echo "Generating RRO for ${TARGET_PATH}" > "${log}"
"${MY_DIR}/generate_rro.sh" "$TARGET_PATH"
rm -rf "$TARGET_PATH"

find "$FOLDER" -type f \( \
    -name ic_launcher_phone.png -o \
    -name ic_qs_branded_vpn.xml -o \
    -name stat_sys_branded_vpn.xml -o \
    -name shortcut_base.png -o \
    -name fingerprint_location_animation.mp4 -o \
    -name ic_5g_plus_mobiledata.xml -o \
    -name ic_5g_plus_mobiledata_updated.xml \
\) -delete

echo "Modifying package names in AndroidManifest.xml" > "${log}"
find "$FOLDER" -type f -name AndroidManifest.xml | xargs -P "$(nproc)" -I {} sed -i "s|(package=\"[^\"]+)|\1_gms|" -r "{}"

export MY_DIR FOLDER log
process_xml() {
    local file="$1"
    echo "Processing XML file: $file" > "${log}"

    while IFS= read -r tag; do
        type=$(echo "$tag" | cut -d: -f1)
        node=$(echo "$tag" | cut -d: -f2)
        echo "Removing $type:$node from $file" > "${log}"
        xmlstarlet ed -L -d "/resources/$type[@name='$node']" "$file"
    done < "${MY_DIR}/exclude-tag.txt"

    echo "Reformatting $file" > "${log}"
    xmlstarlet fo -s 4 "$file" > "$file.bak" && mv "$file.bak" "$file"
    sed -i "s|\?android:\^attr-private|\@\*android\:attr|g" $file
    sed -i "s|\@android\:color|\@\*android\:color|g" $file
    sed -i "s|\^attr-private|attr|g" $file
    sed -i "s|com.google.android.apps.nexuslauncher|com.android.launcher3|g" $file
    sed -i "s|com.google.android.apps.wallpaper|com.android.wallpaper|g" $file
    sed -i "s|com.google.android.dialer.extensions.GoogleDialtactsActivity|com.android.dialer.DialtactsActivity|g" $file
    sed -i "s|com.google.android.dialer|com.android.dialer|g" $file
    sed -i "s|com.google.android.apps.messaging|com.android.messaging|g" $file
}

export -f process_xml
find "$FOLDER/res" -name "*.xml" ! -path "$FOLDER/res/raw/*" ! -path "$FOLDER/res/drawable*/*" ! -path "$FOLDER/res/xml" | xargs -P "$(nproc)" -I {} bash -c 'process_xml "{}"'

echo "Renaming files that start with \$" > "${log}"
find "$FOLDER" -type f -name '$*' | while IFS= read -r file; do
    new_name="${file%/*}/${file##*/}"
    new_name="${new_name//\$/}"

    if [[ "$file" != "$new_name" ]]; then
        echo "Renaming $file to $new_name" > "${log}"
        mv "$file" "$new_name"

        old_basename="$(basename "$file" .xml)"
        new_basename="$(basename "$new_name" .xml)"
        grep -rl "$old_basename" "$FOLDER" | while IFS= read -r text_file; do
            echo "Replacing $old_basename with $new_basename in $text_file" > "${log}"
            sed -i "s|$old_basename|$new_basename|g" "$text_file"
        done
    fi
done

echo "Recreating overlays.mk" > "${log}"
echo -e "PRODUCT_PACKAGES += \\" > "$OVERLAY_MK"

for dir in "${OVERLAY_DIR}"/*/; do
    if [[ -d "$dir" ]]; then
        entry="    $(basename "$dir") \\"
        echo "Adding ${entry} to overlays.mk" > "${log}"
        echo "$entry" >> "$OVERLAY_MK"
    fi
done
