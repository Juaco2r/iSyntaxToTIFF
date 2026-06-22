# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

project_root = os.path.abspath(".")
assets_path = os.path.join(project_root, "assets")
icon_path = os.path.join(assets_path, "icon", "app.ico")

datas = []
binaries = []
hiddenimports = []

if os.path.isdir(assets_path):
    datas.append((assets_path, "assets"))

for pkg in ["imagecodecs", "numcodecs", "zarr", "tifffile"]:
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("openphi")
except Exception:
    hiddenimports += ["openphi"]

# Do not bundle Philips SDK modules.
excludedimports = [
    "pixelengine",
    "softwarerenderbackend",
    "softwarerendercontext",
]

a = Analysis(
    ["src/isyntax_to_tiff/app.py"],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludedimports,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_kwargs = dict(
    exclude_binaries=True,
    name="iSyntaxToTIFF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

if sys.platform.startswith("win") and os.path.exists(icon_path):
    exe_kwargs["icon"] = icon_path

exe = EXE(
    pyz,
    a.scripts,
    [],
    **exe_kwargs,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="iSyntaxToTIFF",
)