# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
project_root = os.path.abspath('.')
script_path = os.path.join(project_root, 'src', 'isyntax_to_tiff', 'app.py')
assets_path = os.path.join(project_root, 'assets')
icon_path = os.path.join(assets_path, 'icon', 'app.ico')

datas = []
binaries = []
hiddenimports = []

if os.path.isdir(assets_path):
    datas.append((assets_path, 'assets'))

# Bundle normal Python dependencies needed by the converter.
for pkg in ['tifffile', 'imagecodecs', 'zarr', 'numcodecs', 'PIL']:
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    hiddenimports += collect_submodules('openphi')
except Exception:
    hiddenimports += ['openphi']

# IMPORTANT: Philips SDK modules are intentionally NOT bundled.
# The user configures the Philips SDK folder from inside the app.
excludedimports = [
    'pixelengine',
    'softwarerenderbackend',
    'softwarerendercontext',
]

a = Analysis(
    [script_path],
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='iSyntaxToTIFF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='iSyntaxToTIFF',
)
