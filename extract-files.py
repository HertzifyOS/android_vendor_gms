#!/usr/bin/env -S PYTHONPATH=../../tools/extract-utils python3
#
# SPDX-FileCopyrightText: The PixelOS Project
# SPDX-License-Identifier: Apache-2.0
#

import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

from extract_utils.fixups_blob import (
    blob_fixup,
    blob_fixups_user_type,
)
from extract_utils.fixups_lib import (
    lib_fixups,
)
from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

namespace_imports = []


blob_fixups: blob_fixups_user_type = {
}  # fmt: skip

REPO_ROOT = Path(__file__).resolve().parent
COMMON_DIR = REPO_ROOT / 'common'
ANDROID_BP = COMMON_DIR / 'Android.bp'
PRODUCT_MK = COMMON_DIR / 'common-vendor.mk'
OPTIONAL_LIBS_FILE = REPO_ROOT / 'optional-libs.txt'
GENERATE_OVERLAYS_PY = REPO_ROOT / 'rro-utils' / 'generate-overlays.py'
OVERLAY_DIR = COMMON_DIR / 'proprietary' / 'product' / 'overlay'

APEX_BP_PROPERTIES = {
    'com.google.android.extservices': {
        'overrides': ['com.android.extservices'],
        'apps': ['GoogleExtServices'],
    },
    'com.google.android.gmssystem.prodvic': {
        'apps': ['PrebuiltGmsCoreVic'],
        'product_specific': True,
    },
}


def _bp_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return '[' + ', '.join(f'"{v}"' for v in value) + ']'
    return f'"{value}"'


def inject_optional_uses_libs():
    if not OPTIONAL_LIBS_FILE.is_file() or not ANDROID_BP.is_file():
        return

    patterns = []
    for line in OPTIONAL_LIBS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        apk_glob, _, rest = line.partition(';')
        m = re.search(r'LIBS=(.+)', rest)
        if not m:
            continue
        libs = ', '.join(f'"{lib.strip()}"' for lib in m.group(1).split(','))
        patterns.append((apk_glob.strip(), libs))

    def add_libs(match):
        apk_path = match.group(1)
        for apk_glob, libs in patterns:
            if fnmatch.fnmatchcase(apk_path, apk_glob):
                return f'{match.group(0)}\n    optional_uses_libs: [{libs}],'
        return match.group(0)

    bp = re.sub(r'apk: "proprietary/([^"]+)",', add_libs, ANDROID_BP.read_text())
    ANDROID_BP.write_text(bp)


def inject_apex_bp_properties():
    if not ANDROID_BP.is_file():
        return
    bp = ANDROID_BP.read_text()
    for module, props in APEX_BP_PROPERTIES.items():
        needle = f'name: "{module}",'
        extra = ''.join(f'\n    {k}: {_bp_value(v)},' for k, v in props.items())
        bp = bp.replace(needle, needle + extra, 1)
    ANDROID_BP.write_text(bp)


def inject_turbo_adapter_required():
    if not ANDROID_BP.is_file():
        return
    out = []
    in_turbo = False
    depth = 0
    inserted = False
    for line in ANDROID_BP.read_text().splitlines():
        if 'android_app_import {' in line:
            in_turbo = False
            depth = line.count('{') - line.count('}')
        elif depth > 0:
            depth += line.count('{') - line.count('}')
            if 'name: "TurboAdapter"' in line:
                in_turbo = True
            if depth == 0 and in_turbo and not inserted:
                out.append('    required: ["LibPowerStatsSymLink"],')
                inserted = True
        out.append(line)
    ANDROID_BP.write_text('\n'.join(out) + '\n')

    if PRODUCT_MK.is_file():
        mk = PRODUCT_MK.read_text()
        mk = re.sub(r'[ \t]*libpowerstatshaldataprovider[ \t]*\\\n', '', mk)
        PRODUCT_MK.write_text(mk)


def append_overlays_include():
    if not PRODUCT_MK.is_file():
        return
    line = '\ninclude vendor/gms/common/overlays.mk\n'
    body = PRODUCT_MK.read_text()
    if 'overlays.mk' not in body:
        PRODUCT_MK.write_text(body.rstrip() + line)

def run_generate_overlays(src: str):
    if not GENERATE_OVERLAYS_PY.is_file() or not OVERLAY_DIR.is_dir():
        return
    src_path = Path(src)
    dump_path = src_path if src_path.is_dir() else src_path.with_suffix('')
    if not dump_path.is_dir():
        return
    framework_path = dump_path / 'system' / 'framework' / 'framework-res.apk'
    if not framework_path.is_file():
        return
    subprocess.run(
        [
            str(GENERATE_OVERLAYS_PY),
            str(OVERLAY_DIR),
            '--framework-res', str(framework_path),
        ],
        cwd=REPO_ROOT,
        check=False,
    )

def split_large_files():
    max_size = 50 * 1024 * 1024
    proprietary_dir = COMMON_DIR / 'proprietary'

    for path in proprietary_dir.rglob('*'):
        if not path.is_file():
            continue

        if '.part' in path.name:
            continue

        if path.stat().st_size <= max_size:
            continue

        print(f'[*] Splitting: {path}')

        result = subprocess.run(
            [
                'split',
                '-b', '50M',
                '-d',
                '-a', '2',
                str(path),
                str(path) + '.part',
            ],
            check=False,
        )

        if result.returncode == 0:
            path.unlink()
        else:
            print(f'[!] Failed to split: {path}')

def detect_source() -> str:
    for arg in reversed(sys.argv[1:]):
        if arg.startswith('-'):
            continue
        return arg
    return os.environ.get('SRC', '')


module = ExtractUtilsModule(
    'common',
    'gms',
    device_rel_path='vendor/gms',
    blob_fixups=blob_fixups,
    lib_fixups=lib_fixups,
    namespace_imports=namespace_imports,
    skip_main_proprietary_file=True,
)

module.add_proprietary_file('proprietary-files.txt')

module.add_proprietary_file('proprietary-files_sounds.txt')

module.add_proprietary_file('proprietary-files_cellular.txt').add_copy_files_guard(
    'WITH_GMS_COMMS_SUITE', 'false', invert=True
)

module.add_proprietary_file('proprietary-files_aicore.txt').add_copy_files_guard(
    'WITH_GMS_AICORE', 'true'
)


if __name__ == '__main__':
    if not COMMON_DIR.is_dir():
        COMMON_DIR.mkdir()
    for _f in [
        COMMON_DIR / 'Android.bp',
        COMMON_DIR / 'Android.mk',
        COMMON_DIR / 'BoardConfigVendor.mk',
        COMMON_DIR / 'common-vendor.mk',
    ]:
        if not _f.exists():
            _f.touch()

    utils = ExtractUtils.device(module)
    utils.run()

    split_large_files()
    
    inject_optional_uses_libs()
    inject_apex_bp_properties()
    inject_turbo_adapter_required()
    append_overlays_include()

    if not any(a in ('--regenerate_makefiles', '-m') for a in sys.argv):
        src = detect_source()
        if src and src not in ('adb', ''):
            run_generate_overlays(src)
