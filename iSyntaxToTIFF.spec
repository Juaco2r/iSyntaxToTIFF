# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all

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

for pkg in ['tifffile', 'imagecodecs', 'zarr', 'numcodecs', 'PIL']:
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

# OpenPhi is bundled, but the Philips Pathology SDK modules are loaded later
# from the SDK folder selected by the user. Do not import OpenPhi here because
# OpenPhi imports pixelengine, which is only available after SDK setup.
hiddenimports += [
    'openphi',
    'openphi.openphi',
]

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

exe_kwargs = dict(
    exclude_binaries=True,
    name='iSyntaxToTIFF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

if sys.platform.startswith('win') and os.path.exists(icon_path):
    exe_kwargs['icon'] = icon_path

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
    name='iSyntaxToTIFF',
)
