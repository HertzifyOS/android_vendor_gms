#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: The PixelOS Project
# SPDX-License-Identifier: Apache-2.0
#

import copy
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from pathlib import Path

_HERTZIFY_SCRIPTS_DEV = Path(__file__).resolve().parents[3] / 'hertzify' / 'scripts' / 'dev'
GENERATE_RRO_PY = _HERTZIFY_SCRIPTS_DEV / 'generate_rro.py'
BEAUTIFY_RRO_PY = _HERTZIFY_SCRIPTS_DEV / 'beautify_rro.py'

_SCRIPT_DIR = Path(__file__).resolve().parent
EXCLUDE_TAGS_FILE = _SCRIPT_DIR / 'exclude-tag.txt'

_BEAUTIFY_SKIP_OVERLAYS = {
    'PixelSetupWizardOverlay2024_GMS',
    'PixelSetupWizardOverlayExpressive_GMS',
    'PixelDocumentsUIGoogleOverlay_GMS',
}

_TARGET_PACKAGE_SUBSTITUTIONS = {
    'com.google.android.telecomresources': 'com.android.server.telecom',
}

_EXCLUDED_FILENAMES = {
    'ic_launcher_phone.png',
    'ic_qs_branded_vpn.xml',
    'ic_safety_protection.xml',
    'stat_sys_branded_vpn.xml',
    'shortcut_base.png',
    'fingerprint_location_animation.mp4',
    'fingerprint_sp_apply_2024.json',
    'fingerprint_sp_expressive.json',
    'udfps_edu_lottie.xml',
    'ic_5g_plus_mobiledata.xml',
    'ic_5g_plus_mobiledata_updated.xml',
}


def _run(script: Path, *args: str):
    env = {**os.environ, 'PYTHONPATH': str(_HERTZIFY_SCRIPTS_DEV)}
    subprocess.run([sys.executable, str(script), *args], env=env, check=False)


def delete_excluded_files(overlay_dir: Path):
    for f in overlay_dir.rglob('*'):
        if f.is_file() and f.name in _EXCLUDED_FILENAMES:
            f.unlink()


def rename_dollar_files(overlay_dir: Path):
    for f in sorted(overlay_dir.rglob('*')):
        if not f.is_file() or '$' not in f.name:
            continue
        new_path = f.parent / f.name.replace('$', '')
        if new_path == f:
            continue
        old_stem = f.stem
        new_stem = new_path.stem
        f.rename(new_path)
        for ref_file in overlay_dir.rglob('*'):
            if not ref_file.is_file():
                continue
            try:
                text = ref_file.read_text(encoding='utf-8')
                if old_stem in text:
                    ref_file.write_text(text.replace(old_stem, new_stem), encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue


_TEXT_SUBSTITUTIONS = [
    ('?android:^attr-private', '@*android:attr'),
    ('@android:color', '@*android:color'),
    ('^attr-private', 'attr'),
    ('com.google.android.apps.nexuslauncher', 'com.android.launcher3'),
    ('com.android.documentsui', 'com.google.android.documentsui'),
    ('@style/Theme.DeviceDefault', '@android:style/Theme.DeviceDefault'),
]


def apply_text_substitutions(overlay_dir: Path):
    for xml_file in overlay_dir.rglob('*.xml'):
        parts = xml_file.relative_to(overlay_dir).parts
        if xml_file.name != 'AndroidManifest.xml':
            if 'res' not in parts:
                continue
            res_sub = parts[list(parts).index('res') + 1] if list(parts).index('res') + 1 < len(parts) else ''
            if res_sub.startswith(('raw', 'drawable', 'xml')):
                continue
        text = xml_file.read_text(encoding='utf-8')
        new_text = text
        for old, new in _TEXT_SUBSTITUTIONS:
            new_text = new_text.replace(old, new)
        if new_text != text:
            xml_file.write_text(new_text, encoding='utf-8')


def retarget_overlay_packages(overlay_dir: Path):
    for path in overlay_dir.rglob('*'):
        if path.name not in ('.overlay-meta.json', 'AndroidManifest.xml'):
            continue
        text = path.read_text(encoding='utf-8')
        new_text = text
        for old, new in _TARGET_PACKAGE_SUBSTITUTIONS.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding='utf-8')


def apply_exclude_tags(overlay_dir: Path):
    if not EXCLUDE_TAGS_FILE.is_file():
        return

    entries = []
    for line in EXCLUDE_TAGS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        tag_type, name = line.split(':', 1)
        entries.append((tag_type, name))

    if not entries:
        return

    for xml_file in overlay_dir.rglob('*.xml'):
        parts = xml_file.relative_to(overlay_dir).parts
        if 'res' not in parts:
            continue
        res_sub = parts[list(parts).index('res') + 1] if list(parts).index('res') + 1 < len(parts) else ''
        if res_sub.startswith(('raw', 'drawable', 'xml')):
            continue

        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue

        root = tree.getroot()
        removed = False
        for tag_type, name in entries:
            for elem in root.findall(f"{tag_type}[@name='{name}']"):
                root.remove(elem)
                removed = True

        if removed:
            ET.indent(tree, space='    ')
            tree.write(str(xml_file), encoding='unicode')


def suffix_manifest_packages(overlay_dir: Path):
    for manifest in overlay_dir.rglob('AndroidManifest.xml'):
        text = manifest.read_text(encoding='utf-8')
        new_text = re.sub(r'(package="(?!.*_gms")[^"]+)"', r'\1_gms"', text)
        if new_text != text:
            manifest.write_text(new_text, encoding='utf-8')


def merge_split_drawables(overlay_dir: Path):
    android_ns = 'http://schemas.android.com/apk/res/android'
    aapt_ns = 'http://schemas.android.com/aapt'
    ET.register_namespace('android', android_ns)
    ET.register_namespace('aapt', aapt_ns)
    prefixes = {android_ns: 'android', aapt_ns: 'aapt'}

    def prefixed_name(qname):
        if qname.startswith('{'):
            uri, local = qname[1:].split('}', 1)
            return f'{prefixes.get(uri, uri)}:{local}'
        return qname

    def to_aapt2_style(root):
        def move_xmlns(m):
            ns = re.findall(r'xmlns:\w+="[^"]*"', m[2])
            if not ns:
                return m[0]
            ns.sort(key=lambda s: 'xmlns:android' not in s)  # android before aapt
            attrs = re.sub(r'\s*xmlns:\w+="[^"]*"', '', m[2]).strip()
            return f'{m[1]} {attrs}\n  {" ".join(ns)}>'

        body = re.sub(
            r'(<[\w-]+)([^>]*)>', move_xmlns, ET.tostring(root, encoding='unicode'), count=1
        )
        return f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n'

    def fold_references(tree, stem, inner):
        matches = [
            (el, attr)
            for el in tree.iter()
            for attr, val in el.attrib.items()
            if val.startswith('@') and val.partition('/')[2] == stem
        ]
        for el, attr in matches:
            idx = list(el.attrib).index(attr)  # where the attribute sat
            aapt_attr = ET.Element(f'{{{aapt_ns}}}attr')
            aapt_attr.set('name', prefixed_name(attr))
            aapt_attr.append(copy.deepcopy(inner))
            el.insert(idx, aapt_attr)
            del el.attrib[attr]
        return bool(matches)

    def fold_child(child):
        try:
            inner = ET.parse(child).getroot()
        except ET.ParseError:
            return False
        folded = False
        for xml_file in overlay_dir.rglob('*.xml'):
            if xml_file == child:
                continue
            try:
                text = xml_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            if child.stem not in text:  # cheap filter + skips non-XML resources
                continue
            try:
                tree = ET.parse(xml_file)
            except ET.ParseError:
                continue
            if fold_references(tree, child.stem, inner):
                ET.indent(tree, space='    ')
                xml_file.write_text(to_aapt2_style(tree.getroot()), encoding='utf-8')
                folded = True
        return folded

    for child in list(overlay_dir.rglob('$*__*.xml')):
        if fold_child(child):
            child.unlink()


def remove_meta_files(overlay_dir: Path):
    for f in overlay_dir.rglob('.overlay-meta.json'):
        f.unlink()


def write_overlays_mk(overlay_dir: Path):
    common_dir = overlay_dir.parents[2]

    vendor_mk = common_dir / 'common-vendor.mk'
    if vendor_mk.is_file():
        lines = vendor_mk.read_text().splitlines(keepends=True)
        lines = [l for l in lines if not ('product/overlay/' in l and '.apk' in l)]
        vendor_mk.write_text(''.join(lines))

    overlays_mk = common_dir / 'overlays.mk'
    packages = sorted(
        d.name for d in overlay_dir.iterdir()
        if d.is_dir() and (d / 'Android.bp').is_file()
    )
    if not packages:
        return
    lines = ['PRODUCT_PACKAGES += \\']
    for i, pkg in enumerate(packages):
        sep = ' \\' if i < len(packages) - 1 else ''
        lines.append(f'    {pkg}{sep}')
    overlays_mk.write_text('\n'.join(lines) + '\n')


def main():
    parser = ArgumentParser(
        prog='generate-overlays',
        description='Generate GMS RRO overlays from APKs in the overlay directory',
    )
    parser.add_argument('overlay_dir', type=Path, help='Directory containing overlay APKs')
    parser.add_argument(
        '--framework-res',
        type=Path,
        required=True,
        help='Path to framework-res.apk',
    )
    args = parser.parse_args()

    overlay_dir: Path = args.overlay_dir
    framework_path: Path = args.framework_res

    if not framework_path.is_file():
        print(f'error: framework-res.apk not found at {framework_path}', file=sys.stderr)
        sys.exit(1)

    if not any(overlay_dir.glob('*.apk')):
        return

    _run(
        GENERATE_RRO_PY,
        str(overlay_dir),
        '--overlays', str(overlay_dir),
        '--framework', str(framework_path),
    )
    for apk in overlay_dir.glob('*.apk'):
        apk.unlink()
    merge_split_drawables(overlay_dir)
    delete_excluded_files(overlay_dir)
    rename_dollar_files(overlay_dir)
    apply_exclude_tags(overlay_dir)
    retarget_overlay_packages(overlay_dir)
    for overlay_subdir in sorted(overlay_dir.iterdir()):
        if not overlay_subdir.is_dir():
            continue
        if overlay_subdir.name in _BEAUTIFY_SKIP_OVERLAYS:
            continue
        if not (overlay_subdir / 'Android.bp').is_file():
            continue
        _run(BEAUTIFY_RRO_PY, str(overlay_subdir))
    apply_text_substitutions(overlay_dir)
    suffix_manifest_packages(overlay_dir)
    remove_meta_files(overlay_dir)
    write_overlays_mk(overlay_dir)


if __name__ == '__main__':
    main()
