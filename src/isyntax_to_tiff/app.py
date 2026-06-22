"""
iSyntaxToTIFF
Standalone PyQt5 application for converting Philips .isyntax files to pyramidal
RGB OME-TIFF using Philips Pathology SDK + OpenPhi.

Windows builds target the Philips SDK Windows Python 3.7 package.
Linux builds target the Philips SDK Ubuntu 20.04 Python 3.8 package.

Design goal:
- Keep the normal TiffCropper app intact.
- This app only handles Philips SDK setup/test, iSyntax thumbnail preview,
  and .isyntax -> .ome.tif conversion.
- The user selects/prepares the Philips Pathology SDK ZIP or folder once.

Tested setup from our debugging:
- Python 3.7 environment
- Philips Pathology SDK 2.0-L1 research SDK
- OpenPhi installed in the Python environment / bundled into the EXE
- Import order for Philips modules:
    import pixelengine
    import softwarerenderbackend
    import softwarerendercontext
    from openphi import OpenPhi

Author: José Rodriguez-Rojas / TiffCropper iSyntax standalone helper
"""

import os
import sys
import csv
import json
import math
import shutil
import inspect
import zipfile
import re
import traceback
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import tifffile

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox, QListWidget,
    QAbstractItemView, QGroupBox, QComboBox, QSpinBox, QCheckBox, QProgressBar,
    QTextEdit, QSizePolicy, QAction
)


APP_NAME = "iSyntaxToTIFF"
APP_VERSION = "1.7"
APP_AUTHOR = "José Rodriguez-Rojas"


def _app_config_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP_NAME


def _app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / APP_NAME


APP_SETTINGS_DIR = _app_config_dir()
APP_SETTINGS_FILE = APP_SETTINGS_DIR / "settings.json"
APP_SDK_EXTRACT_DIR = _app_data_dir() / "SDK"
APP_SDK_LEGACY_EXTRACT_DIR = _app_data_dir() / "PhilipsSDK"


# ============================================================
# Small helpers
# ============================================================

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _mpp_to_dpi(mpp: float) -> float:
    # micrometers/pixel -> pixels/inch
    return 25400.0 / float(mpp)


def _to_uint8_rgb(arr: np.ndarray) -> np.ndarray:
    """Display-only robust RGB conversion."""
    arr = np.asarray(arr)
    arr = np.squeeze(arr)

    if arr.ndim == 2:
        if arr.dtype != np.uint8:
            arr = _normalize_to_uint8(arr)
        arr = np.stack([arr, arr, arr], axis=-1)
        return np.ascontiguousarray(arr.astype(np.uint8, copy=False))

    if arr.ndim == 3:
        if arr.shape[-1] == 4:
            arr = arr[:, :, :3]
        elif arr.shape[-1] == 1:
            ch = arr[:, :, 0]
            if ch.dtype != np.uint8:
                ch = _normalize_to_uint8(ch)
            arr = np.stack([ch, ch, ch], axis=-1)
        elif arr.shape[-1] >= 3:
            arr = arr[:, :, :3]
        else:
            ch = arr[:, :, 0]
            if ch.dtype != np.uint8:
                ch = _normalize_to_uint8(ch)
            arr = np.stack([ch, ch, ch], axis=-1)
        if arr.dtype != np.uint8:
            arr = _normalize_to_uint8(arr)
        return np.ascontiguousarray(arr.astype(np.uint8, copy=False))

    raise ValueError("Unsupported preview array shape: %s" % (arr.shape,))


def _normalize_to_uint8(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.dtype == np.uint8:
        return arr
    arrf = arr.astype(np.float32, copy=False)
    finite = np.isfinite(arrf)
    if not np.any(finite):
        return np.zeros(arrf.shape, dtype=np.uint8)
    vals = arrf[finite]
    lo = float(np.percentile(vals, 1.0))
    hi = float(np.percentile(vals, 99.8))
    if hi <= lo:
        lo = float(vals.min())
        hi = float(vals.max())
    if hi <= lo:
        return np.zeros(arrf.shape, dtype=np.uint8)
    out = np.clip((arrf - lo) / (hi - lo), 0, 1)
    return (out * 255.0).astype(np.uint8)


def _rgb_to_qpixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(_to_uint8_rgb(rgb))
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def _load_settings() -> Dict[str, Any]:
    try:
        if APP_SETTINGS_FILE.exists():
            return json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Backward-compatible migration from the first preview builds.
    try:
        old_file = Path(os.environ.get("APPDATA", str(Path.home()))) / "TiffCropper" / "isyntax_converter_settings.json"
        if old_file.exists():
            return json.loads(old_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_settings(settings: Dict[str, Any]) -> None:
    try:
        APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception:
        pass


def _open_folder(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("._") or "sdk"


def _preferred_sdk_zip_keywords() -> List[str]:
    if sys.platform.startswith("win"):
        return ["pathologysdk", "windows", "py37", "research"]
    if sys.platform.startswith("linux"):
        return ["pathologysdk", "ubuntu20", "py38", "research"]
    return ["pathologysdk", "research"]


def _zip_matches_current_platform(zip_path: Path) -> bool:
    name = zip_path.name.lower().replace("-", "_")
    keywords = _preferred_sdk_zip_keywords()
    return all(k.lower().replace("-", "_") in name for k in keywords)


def _find_matching_sdk_zip(folder: Path) -> Optional[Path]:
    folder = Path(folder)
    if not folder.exists() or not folder.is_dir():
        return None
    try:
        zips = [z for z in folder.rglob("*.zip") if z.is_file()]
    except Exception:
        return None

    # Prefer the exact platform/research package.
    for z in zips:
        if _zip_matches_current_platform(z):
            return z

    # Fallback: any research PathologySDK ZIP matching the OS family.
    platform_terms = ["windows"] if sys.platform.startswith("win") else (["ubuntu", "linux"] if sys.platform.startswith("linux") else [])
    for z in zips:
        name = z.name.lower()
        if "pathologysdk" in name and "research" in name and any(t in name for t in platform_terms):
            return z

    # Last fallback: if there is only one PathologySDK ZIP, use it.
    sdk_zips = [z for z in zips if "pathologysdk" in z.name.lower()]
    if len(sdk_zips) == 1:
        return sdk_zips[0]
    return None



def _single_zip_root(member_names: List[str]) -> Optional[str]:
    """Return the single top-level folder in a ZIP, if all members share one."""
    roots = set()
    for name in member_names:
        clean = name.replace("\\", "/").strip("/")
        if not clean:
            continue
        first = clean.split("/", 1)[0]
        if first:
            roots.add(first)
    if len(roots) == 1:
        return next(iter(roots))
    return None


def _short_sdk_extract_name(zip_path: Path) -> str:
    """Use short extraction folders to avoid Windows MAX_PATH issues."""
    name = zip_path.name.lower().replace("-", "_")
    if sys.platform.startswith("win") and "windows" in name and "py37" in name:
        return "win_py37"
    if sys.platform.startswith("linux") and ("ubuntu20" in name or "linux" in name) and "py38" in name:
        return "linux_py38"
    if "pathologysdk" in name and "packages" in name:
        return "packages"
    return _safe_name(zip_path.stem)[:40] or "sdk_zip"


def _safe_extract_zip(zip_path: Path, dest_dir: Path, strip_single_root: bool = True) -> None:
    """Safely extract a ZIP while avoiding nested duplicate root folders.

    Philips SDK package ZIPs usually contain a top-level folder with the same
    name as the ZIP. If we extract the ZIP into a folder with that same name,
    paths become duplicated and can exceed the Windows path limit. This helper
    strips that common top-level folder and creates parent folders explicitly.
    """
    zip_path = Path(zip_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        infos = zf.infolist()
        raw_names = [m.filename.replace("\\", "/").strip("/") for m in infos if m.filename]
        common_root = _single_zip_root(raw_names) if strip_single_root else None

        for member in infos:
            member_name = member.filename.replace("\\", "/").strip("/")
            if not member_name:
                continue
            if member_name.startswith("/") or ".." in Path(member_name).parts:
                raise RuntimeError("Unsafe path inside ZIP: %s" % member.filename)

            rel_name = member_name
            if common_root and (rel_name == common_root or rel_name.startswith(common_root + "/")):
                rel_name = rel_name[len(common_root):].lstrip("/")
                if not rel_name:
                    continue

            target = (dest_dir / rel_name).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise RuntimeError("Unsafe path inside ZIP: %s" % member.filename)

            if member.is_dir() or member_name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, open(str(target), "wb") as dst:
                shutil.copyfileobj(src, dst)

            # Preserve executable bits on Linux/macOS when present.
            try:
                mode = (member.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(str(target), mode)
            except Exception:
                pass


def _extract_zip_if_needed(zip_path: Path, extract_parent: Path, message_callback=None) -> Path:
    zip_path = Path(zip_path)
    extract_parent = Path(extract_parent)
    extract_parent.mkdir(parents=True, exist_ok=True)
    out_dir = extract_parent / _short_sdk_extract_name(zip_path)

    if out_dir.exists() and find_philips_sdk_root(str(out_dir)) is not None:
        if message_callback:
            message_callback("SDK ZIP already prepared: %s" % out_dir)
        return out_dir

    if out_dir.exists():
        try:
            shutil.rmtree(str(out_dir))
        except Exception:
            # If Windows keeps a DLL locked, create a fresh folder instead of failing.
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = extract_parent / (out_dir.name + "_" + stamp)

    out_dir.mkdir(parents=True, exist_ok=True)

    if message_callback:
        message_callback("Extracting SDK ZIP: %s" % zip_path.name)
        message_callback("Extraction folder: %s" % out_dir)
    _safe_extract_zip(zip_path, out_dir, strip_single_root=True)
    return out_dir

def prepare_philips_sdk_source(source_path: Path, message_callback=None) -> Tuple[Optional[Path], str]:
    """Accept either a Philips Pathology SDK ZIP or an extracted folder.

    Supports both the platform-specific SDK ZIP and the larger
    PathologySDK_2.0-L1_Packages ZIP that contains Windows/Linux packages.
    """
    source_path = Path(source_path).expanduser()
    if not source_path.exists():
        return None, "Selected SDK path does not exist: %s" % source_path

    if source_path.is_dir():
        root = find_philips_sdk_root(str(source_path))
        if root is not None:
            return root, "SDK root detected: %s" % root

        nested_zip = _find_matching_sdk_zip(source_path)
        if nested_zip is not None:
            if message_callback:
                message_callback("Found platform SDK ZIP inside selected folder: %s" % nested_zip.name)
            return prepare_philips_sdk_source(nested_zip, message_callback)

        return None, (
            "Could not detect a Philips SDK root or matching SDK ZIP inside:\n%s\n\n"
            "Expected either a folder containing Modules/philips.pathologysdk.* or a PathologySDK ZIP."
        ) % source_path

    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        try:
            extracted = _extract_zip_if_needed(source_path, APP_SDK_EXTRACT_DIR, message_callback)
        except Exception as exc:
            return None, "Could not extract SDK ZIP:\n%s\n\n%s" % (source_path, exc)

        root = find_philips_sdk_root(str(extracted))
        if root is not None:
            return root, "SDK root detected after extraction: %s" % root

        nested_zip = _find_matching_sdk_zip(extracted)
        if nested_zip is not None:
            if message_callback:
                message_callback("Found platform SDK package inside bundle: %s" % nested_zip.name)
            try:
                nested_extracted = _extract_zip_if_needed(nested_zip, APP_SDK_EXTRACT_DIR, message_callback)
            except Exception as exc:
                return None, "Could not extract nested SDK package:\n%s\n\n%s" % (nested_zip, exc)

            root = find_philips_sdk_root(str(nested_extracted))
            if root is not None:
                return root, "SDK root detected after nested extraction: %s" % root

        return None, (
            "The ZIP was extracted, but no compatible SDK root was detected.\n\n"
            "Selected ZIP: %s\nExtracted to: %s\n\n"
            "For Windows, use the Windows Python 3.7 research SDK package.\n"
            "For Linux, use the Ubuntu 20.04 Python 3.8 research SDK package."
        ) % (source_path, extracted)

    return None, "Please select a Philips Pathology SDK ZIP file or an extracted SDK folder."


# ============================================================
# Philips SDK path detection and setup
# ============================================================

def _candidate_sdk_roots_from(start_folder: Optional[str] = None) -> List[Path]:
    candidates: List[Path] = []

    def add(p):
        if p:
            pp = Path(p).expanduser()
            if pp not in candidates:
                candidates.append(pp)

    if start_folder:
        start = Path(start_folder).expanduser()
        add(start)
        # If user selects a child folder, walk up a few parents.
        for parent in list(start.parents)[:5]:
            add(parent)

    for env in ["PHILIPS_SDK_PATH", "PHILIPS_PATHOLOGY_SDK_PATH", "PHILIPS_PATHOLOGY_SDK"]:
        add(os.environ.get(env, ""))

    # Portable EXE layout: SDK2 beside the EXE / script
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent
    add(app_dir / "SDK2")
    add(app_dir / "PhilipsSDK" / "SDK2")

    # Prepared SDKs extracted by the app.
    add(APP_SDK_EXTRACT_DIR)
    add(APP_SDK_LEGACY_EXTRACT_DIR)

    # Common Windows location used during development/testing.
    add(r"C:\PhilipsSDK\SDK2")

    return candidates


def _sdk_has_expected_layout(root: Path) -> bool:
    return (
        (root / "Modules" / "philips.pathologysdk.pixelengine.2.0-L1").exists() and
        (root / "Modules" / "philips.pathologysdk.softwarerenderbackend.2.0-L1").exists() and
        (root / "Modules" / "philips.pathologysdk.softwarerendercontext.2.0-L1").exists()
    )


def _iter_dirs_limited(root: Path, max_depth: int = 6) -> Iterable[Path]:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        return
    base_depth = len(root.resolve().parts)
    stack = [root]
    while stack:
        current = stack.pop()
        yield current
        try:
            current_depth = len(current.resolve().parts) - base_depth
            if current_depth >= max_depth:
                continue
            for child in current.iterdir():
                if child.is_dir():
                    stack.append(child)
        except Exception:
            continue


def find_philips_sdk_root(start_folder: Optional[str] = None) -> Optional[Path]:
    """Find a Philips Pathology SDK root folder containing Modules/..."""
    for cand in _candidate_sdk_roots_from(start_folder):
        if cand.exists() and _sdk_has_expected_layout(cand):
            return cand

        if cand.exists() and cand.is_dir():
            for folder in _iter_dirs_limited(cand, max_depth=6):
                if _sdk_has_expected_layout(folder):
                    return folder
                nested = folder / "SDK2"
                if nested.exists() and _sdk_has_expected_layout(nested):
                    return nested
    return None


def philips_sdk_paths(sdk_root: Path) -> Dict[str, Path]:
    sdk_root = Path(sdk_root)
    pe_root = sdk_root / "Modules" / "philips.pathologysdk.pixelengine.2.0-L1"
    srb_root = sdk_root / "Modules" / "philips.pathologysdk.softwarerenderbackend.2.0-L1"
    src_root = sdk_root / "Modules" / "philips.pathologysdk.softwarerendercontext.2.0-L1"
    return {
        "sdk_root": sdk_root,
        "pe_root": pe_root,
        "srb_root": srb_root,
        "src_root": src_root,
        "pe_dll": pe_root / "pixelengine",
        "srb_dll": srb_root / "softwarerenderbackend",
        "src_dll": src_root / "softwarerendercontext",
        "redistributables": sdk_root / "Redistributables",
    }


def apply_philips_sdk_paths(sdk_root: Path) -> None:
    """Expose Philips SDK folders to Python 3.7 via sys.path and PATH.

    Python 3.7 does not have os.add_dll_directory, therefore PATH must be
    modified before importing pixelengine/softwarerenderbackend/context.
    """
    paths = philips_sdk_paths(sdk_root)

    # Python package roots
    for key in ["pe_root", "srb_root", "src_root"]:
        p = paths[key]
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

    # DLL folders
    dll_dirs = [paths["pe_dll"], paths["srb_dll"], paths["src_dll"], paths["redistributables"]]
    current_path = os.environ.get("PATH", "")
    current_parts = current_path.split(os.pathsep) if current_path else []
    prepend = []
    for d in dll_dirs:
        if d.exists() and str(d) not in current_parts and str(d) not in prepend:
            prepend.append(str(d))
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + current_parts)

    if sys.platform.startswith("linux"):
        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        current_ld_parts = current_ld.split(os.pathsep) if current_ld else []
        ld_prepend = []
        for d in dll_dirs:
            if d.exists() and str(d) not in current_ld_parts and str(d) not in ld_prepend:
                ld_prepend.append(str(d))
        if ld_prepend:
            os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(ld_prepend + current_ld_parts)

    os.environ["PHILIPS_SDK_PATH"] = str(paths["sdk_root"])
    os.environ["PHILIPS_PATHOLOGY_SDK_PATH"] = str(paths["sdk_root"])


def test_philips_sdk(sdk_root: Path) -> Tuple[bool, str]:
    """Test SDK imports using the proven import order."""
    sdk_root = Path(sdk_root)
    apply_philips_sdk_paths(sdk_root)

    lines = ["SDK root: %s" % sdk_root]
    try:
        import pixelengine  # noqa: F401
        lines.append("pixelengine OK")
    except Exception as exc:
        lines.append("pixelengine FAILED: %s" % exc)
        return False, "\n".join(lines)

    try:
        import softwarerenderbackend  # noqa: F401
        lines.append("softwarerenderbackend OK")
    except Exception as exc:
        lines.append("softwarerenderbackend FAILED: %s" % exc)
        return False, "\n".join(lines)

    try:
        import softwarerendercontext  # noqa: F401
        lines.append("softwarerendercontext OK")
    except Exception as exc:
        lines.append("softwarerendercontext FAILED: %s" % exc)
        return False, "\n".join(lines)

    try:
        from openphi import OpenPhi  # noqa: F401
        lines.append("OpenPhi OK")
    except Exception as exc:
        lines.append("OpenPhi FAILED: %s" % exc)
        return False, "\n".join(lines)

    lines.append("Ready for iSyntax conversion")
    return True, "\n".join(lines)


def require_openphi(sdk_root: Optional[Path] = None):
    if sdk_root:
        ok, msg = test_philips_sdk(sdk_root)
        if not ok:
            raise RuntimeError(msg)
    else:
        # Try known/default locations.
        found = find_philips_sdk_root(None)
        if found:
            ok, msg = test_philips_sdk(found)
            if not ok:
                raise RuntimeError(msg)

    # Import order matters for Philips SDK.
    import pixelengine  # noqa: F401
    import softwarerenderbackend  # noqa: F401
    import softwarerendercontext  # noqa: F401
    from openphi import OpenPhi
    return OpenPhi


def find_sdk_installer(sdk_root: Path) -> Optional[Path]:
    root = Path(sdk_root)
    names = ["InstallPathologySDK.bat"] if sys.platform.startswith("win") else ["InstallPathologySDK.sh", "install.sh"]
    for name in names:
        direct = root / name
        if direct.exists():
            return direct
    try:
        patterns = ["InstallPathologySDK.bat"] if sys.platform.startswith("win") else ["InstallPathologySDK.sh", "*.sh"]
        for pat in patterns:
            matches = list(root.rglob(pat))
            if matches:
                return matches[0]
        return None
    except Exception:
        return None


def run_sdk_installer(sdk_root: Path) -> None:
    installer = find_sdk_installer(sdk_root)
    if installer is None:
        raise FileNotFoundError("Could not find InstallPathologySDK.bat inside: %s" % sdk_root)

    if sys.platform.startswith("win"):
        # Request admin privileges. This opens a separate cmd window.
        try:
            import ctypes
            params = '/c cd /d "{}" && "{}" && pause'.format(str(installer.parent), str(installer))
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, str(installer.parent), 1)
            return
        except Exception:
            subprocess.Popen(["cmd", "/c", str(installer)], cwd=str(installer.parent))
            return
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        try:
            installer.chmod(installer.stat().st_mode | 0o111)
        except Exception:
            pass
        subprocess.Popen(["bash", str(installer)], cwd=str(installer.parent))
        return
    subprocess.Popen([str(installer)], cwd=str(installer.parent))


# ============================================================
# OpenPhi / iSyntax reading helpers
# ============================================================

def open_isyntax(input_path: Path, sdk_root: Optional[Path], view: str = "display"):
    OpenPhi = require_openphi(sdk_root)
    try:
        return OpenPhi(str(input_path), view=view)
    except TypeError:
        return OpenPhi(str(input_path))


def close_slide(slide) -> None:
    try:
        slide.close()
    except Exception:
        pass


def get_slide_dimensions(slide) -> Tuple[List[Tuple[int, int]], List[float]]:
    dims_raw = list(getattr(slide, "level_dimensions", []) or [])
    if not dims_raw:
        raise RuntimeError("OpenPhi did not expose level_dimensions.")
    dims = [(int(w), int(h)) for (w, h) in dims_raw]
    downsamples_raw = list(getattr(slide, "level_downsamples", []) or [])
    if not downsamples_raw:
        downsamples = [1.0]
        for i in range(1, len(dims)):
            downsamples.append(float(dims[0][0]) / max(1.0, float(dims[i][0])))
    else:
        downsamples = [float(x) for x in downsamples_raw]
    while len(downsamples) < len(dims):
        downsamples.append(float(dims[0][0]) / max(1.0, float(dims[len(downsamples)][0])))
    return dims, downsamples


def isyntax_mpp_from_slide(slide) -> Optional[Tuple[float, float]]:
    props = getattr(slide, "properties", {}) or {}
    key_pairs = [
        ("openslide.mpp-x", "openslide.mpp-y"),
        ("mpp-x", "mpp-y"),
        ("philips.mpp-x", "philips.mpp-y"),
        ("DICOM_PIXEL_SPACING_X", "DICOM_PIXEL_SPACING_Y"),
    ]
    for kx, ky in key_pairs:
        x = _safe_float(props.get(kx))
        y = _safe_float(props.get(ky))
        if x and y and x > 0 and y > 0:
            return float(x), float(y)
    return None


def select_pyramid_levels(slide, max_levels: int = 8, min_dimension: int = 1024) -> List[int]:
    dims, downsamples = get_slide_dimensions(slide)
    if len(dims) <= 1:
        return [0]

    max_levels = max(1, int(max_levels or 1))
    min_dimension = max(1, int(min_dimension or 1))
    selected = [0]
    last_ds = float(downsamples[0])

    for level in range(1, len(dims)):
        if len(selected) >= max_levels:
            break
        w, h = dims[level]
        ds = float(downsamples[level])

        if len(selected) >= 2 and max(w, h) < min_dimension:
            selected.append(level)
            break

        if ds >= last_ds * 1.8:
            selected.append(level)
            last_ds = ds

    if selected[-1] != len(dims) - 1 and len(selected) < max_levels:
        selected.append(len(dims) - 1)

    out = []
    for x in selected:
        if x not in out:
            out.append(int(x))
    return out


def read_isyntax_thumbnail(input_path: Path, sdk_root: Path, max_side: int = 700, view: str = "display") -> Tuple[np.ndarray, Dict[str, Any]]:
    slide = open_isyntax(input_path, sdk_root, view=view)
    try:
        dims, downsamples = get_slide_dimensions(slide)
        full_w, full_h = dims[0]

        # Prefer a built-in thumbnail if OpenPhi exposes it.
        if hasattr(slide, "get_thumbnail"):
            try:
                img = slide.get_thumbnail((int(max_side), int(max_side))).convert("RGB")
                arr = np.asarray(img, dtype=np.uint8)
                return arr, {
                    "reader": "OpenPhi.get_thumbnail",
                    "full_dims": (full_w, full_h),
                    "level_count": len(dims),
                    "mpp": isyntax_mpp_from_slide(slide),
                }
            except Exception:
                pass

        # Fallback: choose the lowest-resolution level and downsample if needed.
        level = len(dims) - 1
        level_w, level_h = dims[level]
        img = slide.read_region((0, 0), int(level), (int(level_w), int(level_h))).convert("RGB")
        if max(level_w, level_h) > max_side:
            from PIL import Image
            img.thumbnail((int(max_side), int(max_side)), Image.LANCZOS)
        arr = np.asarray(img, dtype=np.uint8)
        return arr, {
            "reader": "OpenPhi.lowest_level",
            "full_dims": (full_w, full_h),
            "level_count": len(dims),
            "mpp": isyntax_mpp_from_slide(slide),
        }
    finally:
        close_slide(slide)


# ============================================================
# OME-TIFF writing helpers
# ============================================================

def _filter_kwargs(func, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only kwargs supported by a callable signature.

    This avoids crashes with older tifffile versions in Python 3.7, e.g.
    resolutionunit not accepted by TiffWriter.write.
    """
    try:
        sig = inspect.signature(func)
        params = sig.parameters
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return kwargs
        return {k: v for k, v in kwargs.items() if k in params}
    except Exception:
        return kwargs


def compression_kwargs_for_tifffile(compression: str, jpeg_quality: int = 100) -> Dict[str, Any]:
    comp = str(compression or "deflate").strip().lower()
    if comp in ("none", "uncompressed", "raw", ""):
        return {}
    if comp in ("deflate", "zip", "zlib", "lossless"):
        # Lossless. Predictor can improve size and is supported by many tifffile versions.
        return {"compression": "deflate", "predictor": True}
    if comp in ("jpeg", "jpg"):
        # Lossy option. Quality is only used if current tifffile/imagecodecs supports compressionargs.
        return {"compression": "jpeg", "compressionargs": {"level": int(max(1, min(100, jpeg_quality)))}}
    raise ValueError("Unsupported compression: %s" % compression)


def isyntax_rgb_tile_generator(
    slide,
    level: int,
    tile_size: int,
    background: int = 255,
    cancel_event=None,
    progress_callback=None,
    message_callback=None,
    progress_offset: int = 0,
    progress_total: int = 1,
) -> Iterable[np.ndarray]:
    dims, downsamples = get_slide_dimensions(slide)
    level = int(level)
    level_w, level_h = dims[level]
    ds = float(downsamples[level]) if level < len(downsamples) else 1.0
    tile_size = int(tile_size)
    background = max(0, min(255, int(background)))

    nx = int(math.ceil(float(level_w) / tile_size))
    ny = int(math.ceil(float(level_h) / tile_size))
    total_tiles = max(1, nx * ny)
    done = 0

    for y in range(0, level_h, tile_size):
        for x in range(0, level_w, tile_size):
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Cancelled by user.")

            read_w = min(tile_size, level_w - x)
            read_h = min(tile_size, level_h - y)
            loc0 = (int(round(float(x) * ds)), int(round(float(y) * ds)))

            region = slide.read_region(location=loc0, level=level, size=(int(read_w), int(read_h))).convert("RGB")
            tile = np.asarray(region, dtype=np.uint8)
            tile = tile[:read_h, :read_w, :]

            # Pad edge tiles so tiled TIFF writing has consistent tile shape.
            if tile.shape[0] != tile_size or tile.shape[1] != tile_size:
                padded = np.full((tile_size, tile_size, 3), background, dtype=np.uint8)
                padded[:tile.shape[0], :tile.shape[1], :] = tile
                tile = padded

            yield np.ascontiguousarray(tile)

            done += 1
            if progress_callback is not None:
                progress_callback(progress_offset + done, max(1, progress_total))
            if message_callback is not None and (done == 1 or done % 50 == 0 or done == total_tiles):
                message_callback("Level %s tile %s/%s | size %s x %s" % (level, done, total_tiles, level_w, level_h))


def convert_isyntax_to_ome_tiff(
    input_path: Path,
    sdk_root: Path,
    output_dir: Optional[Path] = None,
    tile_size: int = 512,
    compression: str = "deflate",
    jpeg_quality: int = 100,
    max_pyramid_levels: int = 8,
    min_pyramid_dimension: int = 1024,
    view: str = "display",
    overwrite: bool = False,
    cancel_event=None,
    progress_callback=None,
    message_callback=None,
) -> Path:
    input_path = Path(input_path)
    sdk_root = Path(sdk_root)
    if not input_path.exists():
        raise FileNotFoundError("Input file does not exist: %s" % input_path)
    if input_path.suffix.lower() != ".isyntax":
        raise ValueError("Expected .isyntax file, got: %s" % input_path.name)

    if output_dir is None or str(output_dir).strip() == "":
        # Default behavior: save the .ome.tif beside the original .isyntax file.
        output_dir = input_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (input_path.stem + ".ome.tif")

    if output_path.exists() and not overwrite:
        return output_path

    tile_size = int(tile_size)
    if tile_size < 128:
        raise ValueError("Tile size should be at least 128 px.")
    if tile_size % 16 != 0:
        raise ValueError("Tile size should be a multiple of 16.")

    if view not in ("display", "source"):
        view = "display"

    if message_callback:
        message_callback("Opening iSyntax: %s" % input_path.name)

    slide = open_isyntax(input_path, sdk_root, view=view)
    tmp_path = output_path.with_name(output_path.name + ".part")

    try:
        dims, downsamples = get_slide_dimensions(slide)
        full_w, full_h = dims[0]
        mpp = isyntax_mpp_from_slide(slide)
        levels = select_pyramid_levels(slide, max_pyramid_levels, min_pyramid_dimension)

        total_tiles = 0
        for lv in levels:
            w, h = dims[lv]
            total_tiles += int(math.ceil(float(w) / tile_size)) * int(math.ceil(float(h) / tile_size))
        total_tiles = max(1, total_tiles)

        if progress_callback:
            progress_callback(0, total_tiles)
        if message_callback:
            message_callback(
                "Converting %s -> %s | full size %s x %s | iSyntax levels %s | compression %s" %
                (input_path.name, output_path.name, full_w, full_h, levels, compression)
            )

        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

        metadata = {"axes": "YXS", "Name": input_path.stem}
        if mpp:
            metadata.update({
                "PhysicalSizeX": float(mpp[0]),
                "PhysicalSizeY": float(mpp[1]),
                "PhysicalSizeXUnit": "µm",
                "PhysicalSizeYUnit": "µm",
            })

        compression_kwargs = compression_kwargs_for_tifffile(compression, jpeg_quality)
        progress_offset = 0

        with tifffile.TiffWriter(str(tmp_path), bigtiff=True, ome=True) as tif:
            for i, lv in enumerate(levels):
                if cancel_event is not None and cancel_event.is_set():
                    raise RuntimeError("Cancelled by user.")

                level_w, level_h = dims[lv]
                n_tiles = int(math.ceil(float(level_w) / tile_size)) * int(math.ceil(float(level_h) / tile_size))

                ds = float(downsamples[lv]) if lv < len(downsamples) else 1.0
                level_mpp = None
                resolution = None
                if mpp:
                    level_mpp = (float(mpp[0]) * ds, float(mpp[1]) * ds)
                    try:
                        resolution = (_mpp_to_dpi(level_mpp[0]), _mpp_to_dpi(level_mpp[1]))
                    except Exception:
                        resolution = None

                if message_callback:
                    message_callback("Writing pyramid level %s/%s | iSyntax level %s | %s x %s" %
                                     (i + 1, len(levels), lv, level_w, level_h))

                level_kwargs = {
                    "data": isyntax_rgb_tile_generator(
                        slide=slide,
                        level=lv,
                        tile_size=tile_size,
                        background=255,
                        cancel_event=cancel_event,
                        progress_callback=progress_callback,
                        message_callback=message_callback,
                        progress_offset=progress_offset,
                        progress_total=total_tiles,
                    ),
                    "shape": (int(level_h), int(level_w), 3),
                    "dtype": np.uint8,
                    "photometric": "rgb",
                    "tile": (tile_size, tile_size),
                    "metadata": metadata if i == 0 else None,
                    "software": "%s v%s" % (APP_NAME, APP_VERSION),
                    "resolution": resolution,
                }
                level_kwargs.update(compression_kwargs)
                # Avoid TypeError with older tifffile versions. Do not use resolutionunit here.
                level_kwargs = {k: v for k, v in level_kwargs.items() if v is not None}

                if i == 0:
                    level_kwargs["subifds"] = max(0, len(levels) - 1)
                else:
                    level_kwargs["subfiletype"] = 1

                level_kwargs = _filter_kwargs(tif.write, level_kwargs)

                try:
                    tif.write(**level_kwargs)
                except TypeError as exc:
                    # Fallback for old tifffile if compressionargs/predictor are unsupported.
                    msg = str(exc)
                    retry = dict(level_kwargs)
                    changed = False
                    for bad in ["compressionargs", "predictor", "resolutionunit"]:
                        if bad in retry:
                            retry.pop(bad, None)
                            changed = True
                    if changed:
                        retry = _filter_kwargs(tif.write, retry)
                        tif.write(**retry)
                    else:
                        raise

                progress_offset += n_tiles

        if output_path.exists() and overwrite:
            output_path.unlink()
        os.replace(str(tmp_path), str(output_path))

        if message_callback:
            message_callback("Saved OME-TIFF: %s" % output_path)
        if progress_callback:
            progress_callback(total_tiles, total_tiles)
        return output_path

    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise
    finally:
        close_slide(slide)


# ============================================================
# Background worker
# ============================================================

class ConvertWorker(QThread):
    message = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sdk_root: Path, input_paths: List[Path], output_dir: Optional[Path], options: Dict[str, Any]):
        super(ConvertWorker, self).__init__()
        self.sdk_root = Path(sdk_root)
        self.input_paths = [Path(p) for p in input_paths]
        self.output_dir = Path(output_dir) if output_dir else None
        self.options = dict(options or {})
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()
        self.message.emit("Cancellation requested. Waiting for current tile/file to finish safely...")

    def run(self):
        rows = []
        ok = 0
        failed = 0
        try:
            for file_i, p in enumerate(self.input_paths, start=1):
                if self.cancel_event.is_set():
                    raise RuntimeError("Cancelled by user.")
                try:
                    self.message.emit("Starting file %s/%s: %s" % (file_i, len(self.input_paths), p.name))
                    out = convert_isyntax_to_ome_tiff(
                        input_path=p,
                        sdk_root=self.sdk_root,
                        output_dir=self.output_dir,
                        tile_size=self.options.get("tile_size", 512),
                        compression=self.options.get("compression", "deflate"),
                        jpeg_quality=self.options.get("jpeg_quality", 100),
                        max_pyramid_levels=self.options.get("max_pyramid_levels", 8),
                        min_pyramid_dimension=self.options.get("min_pyramid_dimension", 1024),
                        view=self.options.get("view", "display"),
                        overwrite=self.options.get("overwrite", False),
                        cancel_event=self.cancel_event,
                        progress_callback=self.progress.emit,
                        message_callback=self.message.emit,
                    )
                    ok += 1
                    rows.append({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "input": str(p),
                        "output": str(out),
                        "status": "success",
                        "message": "",
                    })
                except Exception as exc:
                    failed += 1
                    rows.append({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "input": str(p),
                        "output": "",
                        "status": "failed",
                        "message": "%s\n%s" % (exc, traceback.format_exc()),
                    })
                    self.message.emit("FAILED: %s | %s" % (p.name, exc))
                    if self.options.get("stop_on_error", False):
                        raise

            log_dir = self.output_dir or (self.input_paths[0].parent if self.input_paths else Path.cwd())
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / ("iSyntaxToTIFF_log_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))
            with open(str(log_path), "w", newline="", encoding="utf-8") as f:
                fieldnames = ["timestamp", "input", "output", "status", "message"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow({k: row.get(k, "") for k in fieldnames})

            self.finished_ok.emit({"ok": ok, "failed": failed, "log_path": str(log_path), "rows": rows})
        except Exception as exc:
            self.failed.emit("%s\n\n%s" % (exc, traceback.format_exc()))


# ============================================================
# GUI
# ============================================================

class ThumbnailLabel(QLabel):
    def __init__(self, parent=None):
        super(ThumbnailLabel, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(420, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: white; border: 1px solid #bdc3c7; border-radius: 6px;")
        self._pix = None
        self.setText("iSyntax thumbnail preview")

    def set_rgb(self, rgb: np.ndarray):
        self._pix = _rgb_to_qpixmap(rgb)
        self.update_pixmap()

    def clear(self):
        self._pix = None
        self.setText("iSyntax thumbnail preview")

    def resizeEvent(self, event):
        super(ThumbnailLabel, self).resizeEvent(event)
        self.update_pixmap()

    def update_pixmap(self):
        if self._pix is None:
            return
        scaled = self._pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.settings = _load_settings()
        self.worker = None
        self.current_output_dir = None
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 780)
        self._build_ui()
        self._load_initial_settings()
        self._update_jpeg_enabled()
        self._startup_python_warning()

    def _build_menu(self):
        """Build top menu actions so SDK/output setup is clearer."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        self.act_select_sdk = QAction("Select / Prepare SDK ZIP or folder", self)
        self.act_select_sdk.triggered.connect(self.select_sdk_source)
        file_menu.addAction(self.act_select_sdk)

        self.act_test_sdk = QAction("Test SDK", self)
        self.act_test_sdk.triggered.connect(self.test_sdk_clicked)
        file_menu.addAction(self.act_test_sdk)

        self.act_run_installer = QAction("Run SDK installer", self)
        self.act_run_installer.triggered.connect(self.run_installer_clicked)
        file_menu.addAction(self.act_run_installer)

        self.act_open_sdk = QAction("Open SDK folder", self)
        self.act_open_sdk.triggered.connect(self.open_sdk_folder_clicked)
        file_menu.addAction(self.act_open_sdk)

        self.act_clear_sdk = QAction("Clear saved SDK path", self)
        self.act_clear_sdk.triggered.connect(self.clear_sdk_clicked)
        file_menu.addAction(self.act_clear_sdk)

        file_menu.addSeparator()

        self.act_set_output = QAction("Set output folder", self)
        self.act_set_output.triggered.connect(self.select_output_folder)
        file_menu.addAction(self.act_set_output)

        self.act_clear_output = QAction("Clear output folder", self)
        self.act_clear_output.triggered.connect(self.clear_output_folder)
        file_menu.addAction(self.act_clear_output)

        file_menu.addSeparator()

        self.act_exit = QAction("Exit", self)
        self.act_exit.triggered.connect(self.close)
        file_menu.addAction(self.act_exit)

        help_menu = menubar.addMenu("&Help")

        self.act_help = QAction("Help", self)
        self.act_help.triggered.connect(self.show_help_dialog)
        help_menu.addAction(self.act_help)

        self.act_about = QAction("About", self)
        self.act_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(self.act_about)

    def _build_ui(self):
        self._build_menu()

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(10, 8, 10, 8)
        main.setSpacing(8)

        subtitle = QLabel(
            "Standalone Philips iSyntax converter. Output is pyramidal RGB OME-TIFF. "
            "Philips Pathology SDK is configured from File > Select / Prepare SDK ZIP or folder."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #444; padding-bottom: 4px;")
        main.addWidget(subtitle)

        # Status panel: show paths/status only. Configuration actions live in the File menu.
        status_box = QGroupBox("Setup status")
        status_layout = QGridLayout(status_box)
        status_layout.setColumnStretch(1, 1)

        status_layout.addWidget(QLabel("SDK folder:"), 0, 0)
        self.sdk_edit = QLineEdit()
        self.sdk_edit.setReadOnly(True)
        self.sdk_edit.setPlaceholderText("File > Select / Prepare SDK ZIP or folder")
        status_layout.addWidget(self.sdk_edit, 0, 1)

        status_layout.addWidget(QLabel("Output folder:"), 1, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Not set: output will be saved beside each .isyntax file")
        status_layout.addWidget(self.output_edit, 1, 1)

        self.sdk_status = QLabel("SDK status: not tested")
        self.sdk_status.setWordWrap(True)
        self.sdk_status.setStyleSheet("color: #444; padding-top: 4px;")
        status_layout.addWidget(self.sdk_status, 2, 0, 1, 2)
        main.addWidget(status_box)

        # Inputs
        input_box = QGroupBox("Philips iSyntax input")
        input_layout = QGridLayout(input_box)
        input_layout.setColumnStretch(0, 1)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        input_layout.addWidget(self.file_list, 0, 0, 5, 1)

        self.btn_add_files = QPushButton("Add .isyntax files")
        self.btn_remove_files = QPushButton("Remove selected")
        self.btn_clear_files = QPushButton("Clear list")
        self.btn_preview = QPushButton("Preview selected")
        input_layout.addWidget(self.btn_add_files, 0, 1)
        input_layout.addWidget(self.btn_remove_files, 1, 1)
        input_layout.addWidget(self.btn_clear_files, 2, 1)
        input_layout.addWidget(self.btn_preview, 3, 1)

        output_hint = QLabel("Output folder is set from File > Set output folder. If empty, each output is saved beside its .isyntax file.")
        output_hint.setWordWrap(True)
        output_hint.setStyleSheet("color: #666;")
        input_layout.addWidget(output_hint, 4, 1)
        main.addWidget(input_box)

        # Preview + options side-by-side
        middle = QHBoxLayout()
        preview_box = QGroupBox("Thumbnail preview")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_label = ThumbnailLabel()
        self.preview_info = QLabel("No preview loaded.")
        self.preview_info.setWordWrap(True)
        preview_layout.addWidget(self.preview_label, 1)
        preview_layout.addWidget(self.preview_info)
        middle.addWidget(preview_box, 2)

        options_box = QGroupBox("Conversion options")
        opt = QGridLayout(options_box)
        opt.setColumnStretch(1, 1)
        row = 0
        opt.addWidget(QLabel("Compression:"), row, 0)
        self.compression_combo = QComboBox()
        self.compression_combo.addItem("Deflate lossless (recommended)", "deflate")
        self.compression_combo.addItem("JPEG lossy", "jpeg")
        self.compression_combo.addItem("None / uncompressed", "none")
        opt.addWidget(self.compression_combo, row, 1)
        row += 1

        opt.addWidget(QLabel("JPEG quality:"), row, 0)
        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(100)
        opt.addWidget(self.jpeg_quality_spin, row, 1)
        row += 1

        opt.addWidget(QLabel("Tile size:"), row, 0)
        self.tile_size_spin = QSpinBox()
        self.tile_size_spin.setRange(128, 4096)
        self.tile_size_spin.setSingleStep(128)
        self.tile_size_spin.setValue(512)
        opt.addWidget(self.tile_size_spin, row, 1)
        row += 1

        opt.addWidget(QLabel("OpenPhi view:"), row, 0)
        self.view_combo = QComboBox()
        self.view_combo.addItem("display", "display")
        self.view_combo.addItem("source", "source")
        opt.addWidget(self.view_combo, row, 1)
        row += 1

        opt.addWidget(QLabel("Max pyramid levels:"), row, 0)
        self.max_levels_spin = QSpinBox()
        self.max_levels_spin.setRange(1, 16)
        self.max_levels_spin.setValue(8)
        opt.addWidget(self.max_levels_spin, row, 1)
        row += 1

        opt.addWidget(QLabel("Min pyramid dimension:"), row, 0)
        self.min_dim_spin = QSpinBox()
        self.min_dim_spin.setRange(128, 8192)
        self.min_dim_spin.setSingleStep(128)
        self.min_dim_spin.setValue(1024)
        opt.addWidget(self.min_dim_spin, row, 1)
        row += 1

        self.overwrite_check = QCheckBox("Overwrite existing output")
        self.stop_on_error_check = QCheckBox("Stop on first error")
        self.open_output_check = QCheckBox("Open output folder after conversion")
        self.open_output_check.setChecked(True)
        opt.addWidget(self.overwrite_check, row, 0, 1, 2); row += 1
        opt.addWidget(self.stop_on_error_check, row, 0, 1, 2); row += 1
        opt.addWidget(self.open_output_check, row, 0, 1, 2); row += 1

        warning = QLabel(
            "Note: Deflate is lossless after OpenPhi renders the RGB image. "
            "This does not guarantee preservation of raw multichannel/fluorescence intensities."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #8a5a00;")
        opt.addWidget(warning, row, 0, 1, 2)
        middle.addWidget(options_box, 1)
        main.addLayout(middle, 1)

        # Controls/log
        controls = QHBoxLayout()
        self.btn_convert = QPushButton("Convert to pyramidal OME-TIFF")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        controls.addWidget(self.btn_convert)
        controls.addWidget(self.btn_cancel)
        main.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setValue(0)
        main.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        main.addWidget(self.log)

        # Signals
        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_remove_files.clicked.connect(self.remove_selected_files)
        self.btn_clear_files.clicked.connect(self.file_list.clear)
        self.btn_preview.clicked.connect(self.preview_selected)
        self.compression_combo.currentIndexChanged.connect(self._update_jpeg_enabled)
        self.btn_convert.clicked.connect(self.start_conversion)
        self.btn_cancel.clicked.connect(self.cancel_conversion)

    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "About iSyntaxToTIFF",
            (
                "iSyntaxToTIFF\n\n"
                "Standalone Philips iSyntax to pyramidal RGB OME-TIFF converter.\n"
                "Version: %s\n"
                "Author: %s\n\n"
                "The Philips Pathology SDK is configured from the File menu.\n\n"
                "Recommended for brightfield visual conversion workflows. "
                "Not intended as a validated raw multichannel quantitative export."
            ) % (APP_VERSION, APP_AUTHOR)
        )

    def show_help_dialog(self):
        QMessageBox.information(
            self,
            "iSyntaxToTIFF Help",
            (
                "Basic workflow:\n\n"
                "1. File > Select / Prepare SDK ZIP or folder\n"
                "2. File > Test SDK\n"
                "3. Add .isyntax files\n"
                "4. Preview selected (optional)\n"
                "5. File > Set output folder (optional)\n"
                "   If no output folder is set, output is saved beside each .isyntax file.\n"
                "6. Choose compression and conversion options\n"
                "7. Click Convert to pyramidal OME-TIFF\n\n"
                "Notes:\n"
                "- Deflate lossless is recommended.\n"
                "- JPEG quality applies only when JPEG compression is selected.\n"
                "- Output is a rendered RGB OME-TIFF from OpenPhi."
            )
        )

    def clear_output_folder(self):
        self.output_edit.clear()
        self.settings.pop("last_output_dir", None)
        _save_settings(self.settings)
        self.append_log("Output folder cleared. Output will be saved beside each .isyntax file.")

    def _startup_python_warning(self):
        if getattr(sys, "frozen", False):
            return
        expected = (3, 7) if sys.platform.startswith("win") else ((3, 8) if sys.platform.startswith("linux") else None)
        if expected and sys.version_info[:2] != expected:
            self.append_log(
                "WARNING: This app is currently running with Python %s. "
                "For source runs, Windows should use Python 3.7 and Linux should use Python 3.8. "
                "Packaged app builds already include their own Python runtime." % sys.version.split()[0]
            )

    def _load_initial_settings(self):
        sdk = self.settings.get("sdk_path") or ""
        if not sdk:
            found = find_philips_sdk_root(None)
            sdk = str(found) if found else ""
        self.sdk_edit.setText(str(sdk))
        self.output_edit.setText(str(self.settings.get("last_output_dir", "")))

    def append_log(self, text: str):
        self.log.append("[%s] %s" % (_now(), text))

    def current_sdk_root(self) -> Optional[Path]:
        text = self.sdk_edit.text().strip()
        if not text:
            return None
        found = find_philips_sdk_root(text)
        return found

    def save_sdk_path(self, root: Path):
        self.settings["sdk_path"] = str(root)
        _save_settings(self.settings)

    def select_sdk_source(self):
        start = self.sdk_edit.text().strip() or str(Path.home())

        box = QMessageBox(self)
        box.setWindowTitle("Select Philips Pathology SDK")
        box.setText("Select the Philips Pathology SDK as either a ZIP file or an extracted folder.")
        box.setInformativeText(
            "You may select the full PathologySDK_2.0-L1_Packages ZIP or the platform-specific research ZIP. "
            "The app will extract and detect the correct SDK folder."
        )
        zip_btn = box.addButton("Select ZIP file", QMessageBox.AcceptRole)
        folder_btn = box.addButton("Select folder", QMessageBox.ActionRole)
        cancel_btn = box.addButton(QMessageBox.Cancel)
        box.exec_()

        clicked = box.clickedButton()
        if clicked == cancel_btn:
            return
        if clicked == zip_btn:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Philips Pathology SDK ZIP",
                start,
                "ZIP files (*.zip);;All files (*)"
            )
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Philips Pathology SDK folder", start)

        if not path:
            return

        self.append_log("Preparing SDK source: %s" % path)
        root, msg = prepare_philips_sdk_source(Path(path), message_callback=self.append_log)
        if root is None:
            self.sdk_edit.setText(path)
            self.sdk_status.setText(msg)
            QMessageBox.warning(self, "SDK not detected", msg)
            return

        self.sdk_edit.setText(str(root))
        self.save_sdk_path(root)
        self.sdk_status.setText(msg)
        self.append_log(msg.replace("\n", " | "))
        QMessageBox.information(
            self,
            "SDK prepared",
            "%s\n\nNext step: File > Test SDK. If the test fails because system dependencies are missing, use File > Run SDK installer and then test again." % msg
        )

    def test_sdk_clicked(self):
        root = self.current_sdk_root()
        if root is None:
            QMessageBox.warning(self, "SDK required", "Select or prepare a valid Philips Pathology SDK ZIP/folder first.")
            return
        ok, msg = test_philips_sdk(root)
        self.sdk_status.setText(msg)
        self.append_log(msg.replace("\n", " | "))
        if ok:
            self.save_sdk_path(root)
            QMessageBox.information(self, "Philips SDK OK", msg)
        else:
            QMessageBox.critical(self, "OpenPhi / Philips SDK error", msg)

    def run_installer_clicked(self):
        root = self.current_sdk_root()
        if root is None:
            QMessageBox.warning(self, "SDK required", "Select or prepare a valid Philips Pathology SDK ZIP/folder first.")
            return
        try:
            run_sdk_installer(root)
            self.append_log("Started SDK installer from: %s" % root)
            QMessageBox.information(
                self, "SDK installer started",
                "The Philips SDK installer was started. If Windows asks for administrator permission, accept it.\n\n"
                "After it finishes, click Test SDK again."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Installer error", str(exc))

    def open_sdk_folder_clicked(self):
        root = self.current_sdk_root()
        if root is None:
            QMessageBox.warning(self, "SDK required", "No valid SDK folder selected.")
            return
        _open_folder(root)

    def clear_sdk_clicked(self):
        self.sdk_edit.clear()
        self.settings.pop("sdk_path", None)
        _save_settings(self.settings)
        self.sdk_status.setText("SDK path cleared.")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Philips iSyntax files",
            str(Path.home()),
            "Philips iSyntax Files (*.isyntax);;All Files (*)"
        )
        existing = set(self.file_list.item(i).text() for i in range(self.file_list.count()))
        for f in files:
            if f not in existing:
                self.file_list.addItem(f)
                existing.add(f)

    def remove_selected_files(self):
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

    def select_output_folder(self):
        start = self.output_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select output folder", start)
        if folder:
            self.output_edit.setText(folder)
            self.settings["last_output_dir"] = folder
            _save_settings(self.settings)

    def selected_input_path(self) -> Optional[Path]:
        items = self.file_list.selectedItems()
        if items:
            return Path(items[0].text())
        if self.file_list.count() > 0:
            return Path(self.file_list.item(0).text())
        return None

    def preview_selected(self):
        root = self.current_sdk_root()
        if root is None:
            QMessageBox.warning(self, "SDK required", "Select/prepare and test a valid Philips Pathology SDK first.")
            return
        p = self.selected_input_path()
        if p is None:
            QMessageBox.warning(self, "No file", "Add/select an .isyntax file first.")
            return
        try:
            self.append_log("Reading thumbnail: %s" % p.name)
            arr, meta = read_isyntax_thumbnail(p, root, max_side=900, view=self.view_combo.currentData())
            self.preview_label.set_rgb(arr)
            info = "File: %s\nReader: %s\nFull dims: %s\nLevels: %s\nMPP: %s" % (
                p.name,
                meta.get("reader"),
                meta.get("full_dims"),
                meta.get("level_count"),
                meta.get("mpp"),
            )
            self.preview_info.setText(info)
            self.append_log("Thumbnail OK: %s" % info.replace("\n", " | "))
        except Exception as exc:
            self.preview_label.clear()
            self.preview_info.setText("Preview failed: %s" % exc)
            QMessageBox.critical(self, "Preview failed", "%s\n\n%s" % (exc, traceback.format_exc()))

    def _update_jpeg_enabled(self):
        is_jpeg = self.compression_combo.currentData() == "jpeg"
        self.jpeg_quality_spin.setEnabled(bool(is_jpeg))
        if not is_jpeg:
            self.jpeg_quality_spin.setStyleSheet("color: gray;")
        else:
            self.jpeg_quality_spin.setStyleSheet("")

    def gather_options(self) -> Dict[str, Any]:
        return {
            "compression": self.compression_combo.currentData(),
            "jpeg_quality": int(self.jpeg_quality_spin.value()),
            "tile_size": int(self.tile_size_spin.value()),
            "view": self.view_combo.currentData(),
            "max_pyramid_levels": int(self.max_levels_spin.value()),
            "min_pyramid_dimension": int(self.min_dim_spin.value()),
            "overwrite": bool(self.overwrite_check.isChecked()),
            "stop_on_error": bool(self.stop_on_error_check.isChecked()),
        }

    def start_conversion(self):
        root = self.current_sdk_root()
        if root is None:
            QMessageBox.warning(self, "SDK required", "Select/prepare and test a valid Philips Pathology SDK first.")
            return

        ok, msg = test_philips_sdk(root)
        self.sdk_status.setText(msg)
        if not ok:
            QMessageBox.critical(self, "SDK test failed", msg)
            return

        paths = [Path(self.file_list.item(i).text()) for i in range(self.file_list.count())]
        if not paths:
            QMessageBox.warning(self, "No input", "Add at least one .isyntax file.")
            return

        output_dir = Path(self.output_edit.text().strip()) if self.output_edit.text().strip() else None
        if output_dir:
            self.settings["last_output_dir"] = str(output_dir)
            _save_settings(self.settings)
        self.current_output_dir = output_dir

        self.worker = ConvertWorker(root, paths, output_dir, self.gather_options())
        self.worker.message.connect(self.append_log)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)

        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(0)
        self.append_log("Conversion started.")
        self.worker.start()

    def cancel_conversion(self):
        if self.worker is not None:
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def on_progress(self, done: int, total: int):
        self.progress.setMaximum(max(1, int(total)))
        self.progress.setValue(max(0, min(int(done), max(1, int(total)))))

    def on_finished(self, result: Dict[str, Any]):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.worker = None
        msg = "Finished. OK: {ok}, failed: {failed}. Log: {log_path}".format(**result)
        self.append_log(msg)
        QMessageBox.information(self, "Conversion finished", msg)
        if self.open_output_check.isChecked():
            log_path = Path(result.get("log_path", ""))
            if log_path.exists():
                _open_folder(log_path.parent)

    def on_failed(self, text: str):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.worker = None
        self.append_log("ERROR: %s" % text)
        QMessageBox.critical(self, "Conversion failed", text)


# ============================================================
# Main
# ============================================================

def main():
    # Avoid user-site packages interfering with PyInstaller/conda environments when run as script.
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
