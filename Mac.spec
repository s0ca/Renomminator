# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_all


app_name = "Nomminator"
tesseract_bin_candidates = [
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
]
tessdata_candidates = [
    "/opt/homebrew/share/tessdata/eng.traineddata",
    "/usr/local/share/tessdata/eng.traineddata",
]

datas = [
    ("templates", "templates"),
    ("static", "static"),
]
binaries = []
hiddenimports = []

for tesseract_bin in tesseract_bin_candidates:
    if os.path.exists(tesseract_bin):
        binaries.append((tesseract_bin, "tesseract"))
        break

for tessdata_file in tessdata_candidates:
    if os.path.exists(tessdata_file):
        datas.append((tessdata_file, "tessdata"))
        break

for package in (
    "flask",
    "jinja2",
    "werkzeug",
    "click",
    "itsdangerous",
    "pytesseract",
    "PIL",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)

app = BUNDLE(
    coll,
    name=f"{app_name}.app",
    icon="Nomminator.icns",
    bundle_identifier="com.nomminator.app",
    info_plist={
        "CFBundleName": app_name,
        "CFBundleDisplayName": app_name,
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
