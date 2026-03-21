#!/bin/bash
#
# Copyright (C) 2021-2022 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEBUG=0
if [[ ${DEBUG} != 0 ]]; then
    log="/dev/tty"
else
    log="/dev/null"
fi

if [[ -z "${SRC}" ]] && [[ -z "${1}" ]]; then
    echo "Missing source"
    exit
elif [[ -z "${SRC}" ]]; then
    echo "Using '${1}' as source"
    SRC="${1}"
fi

if [[ -z "${ANDROID_ROOT}" ]] || [[ -z "${OUTDIR}" ]] && [[ -z "${2}" ]]; then
    echo "Missing outdir, assuming: './common/'"
    out="./common/"
elif [[ -z "${ANDROID_ROOT}" ]] || [[ -z "${OUTDIR}" ]]; then
    echo "Using '${2}' as outdir"
    out="${2}"
else
    out="${ANDROID_ROOT}/${OUTDIR}"
fi

if [[ -z "${MY_DIR}" ]]; then
    echo "Missing MY_DIR, assuming: './'"
    MY_DIR="./"
fi

if [[ -f "${SRC}/system/apex/com.google.android.extservices.apex" ]]; then
    APEX_PATH="${SRC}/system/apex/com.google.android.extservices.apex"
elif [[ -f "${SRC}/system/system/apex/com.google.android.extservices.apex" ]]; then
    APEX_PATH="${SRC}/system/system/apex/com.google.android.extservices.apex"
else
    echo "APEX file not found in expected locations!"
    exit
fi

# Create a temporary working directory
TMPDIR=$(mktemp -d)

# Unpack the apex
apktool d "${APEX_PATH}" -o "${TMPDIR}"/out > "${log}"

# Unpack the resulting original_apex.
7z e "${TMPDIR}"/out/unknown/original_apex -o"${TMPDIR}/extracted_apex" > "${log}"

# Unpack the resulting apex_payload.img
7z e "${TMPDIR}"/extracted_apex/apex_payload.img -o"${TMPDIR}" > "${log}"

# Save the GoogleExtServices.apk
if [[ ! -d "${out}"/proprietary/system/priv-app/GoogleExtServices ]]; then
    mkdir -p "${out}"/proprietary/system/priv-app/GoogleExtServices
fi
cp "${TMPDIR}"/GoogleExtServices.apk "${out}"/proprietary/system/priv-app/GoogleExtServices/GoogleExtServices.apk
cp "${TMPDIR}"/privapp_allowlist_com.google.android.ext.services.xml "${out}"/proprietary/system/etc/permissions/privapp_allowlist_com.google.android.ext.services.xml


# Clear the temporary working directory
rm -rf "${TMPDIR}"

# Pin the updated file in proprietary-files.txt
if [[ -f "${MY_DIR}/proprietary-files.txt" ]]; then
    sha1sum=$(sha1sum "${out}"/proprietary/system/priv-app/GoogleExtServices/GoogleExtServices.apk | awk '{print $1}')
    sed -i "s|system/priv-app/GoogleExtServices/GoogleExtServices.apk.*|system/priv-app/GoogleExtServices/GoogleExtServices.apk;OVERRIDES=ExtServices;PRESIGNED\|${sha1sum}|" "${MY_DIR}/proprietary-files.txt"
    sha1sum=$(sha1sum "${out}"/proprietary/system/etc/permissions/privapp_allowlist_com.google.android.ext.services.xml | awk '{print $1}')
    sed -i "s|system/etc/permissions/privapp_allowlist_com.google.android.ext.services.xml.*|system/etc/permissions/privapp_allowlist_com.google.android.ext.services.xml\|${sha1sum}|" "${MY_DIR}/proprietary-files.txt"
fi

echo "Updated GoogleExtServices!"
