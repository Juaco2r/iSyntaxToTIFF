# iSyntaxToTIFF

Standalone Windows tool to convert Philips `.isyntax` whole-slide images to pyramidal RGB OME-TIFF using OpenPhi and the Philips Pathology SDK.

This project is intentionally separated from TiffCropper so that the standard crop/preview/tile workflow can stay on modern Python builds, while iSyntax support remains isolated in a Windows/Python 3.7-compatible converter.

## What this app does

- Configure the Philips Pathology SDK path from the GUI.
- Test the required SDK imports in the correct order.
- Preview a small thumbnail of `.isyntax` files.
- Convert `.isyntax` to pyramidal `.ome.tif`.
- Use Deflate lossless compression by default.
- Optionally use JPEG compression with quality control.
- Save a CSV conversion log.

## What this app does not include

This repository and its release artifacts do **not** include the Philips Pathology SDK.

The app builds a `no-SDK` EXE. Users must obtain and configure the Philips Pathology SDK separately. Internal users may obtain it through institution-approved internal channels only when permitted by the applicable Philips license. External users should obtain it directly from Philips.

See [NOTICE_THIRD_PARTY.md](NOTICE_THIRD_PARTY.md).

## Recommended workflow for end users

1. Download `iSyntaxToTIFF-Windows-no-SDK.zip` from the GitHub release or Actions artifact.
2. Extract the ZIP.
3. Run `iSyntaxToTIFF.exe`.
4. Click **Select / Prepare SDK folder** and choose the Philips SDK root folder.
5. Click **Run SDK installer** if the SDK was not installed/prepared before.
6. Click **Test SDK**.
7. Add `.isyntax` files and convert them to `.ome.tif`.

Expected SDK test result:

```text
pixelengine OK
softwarerenderbackend OK
softwarerendercontext OK
OpenPhi OK
Ready for iSyntax conversion
```

## Recommended conversion settings

For maximum fidelity relative to the rendered RGB image produced by OpenPhi:

```text
Compression: Deflate lossless
Tile size: 512
Max pyramid levels: 8
Minimum pyramid dimension: 1024
View: display
```

JPEG is optional and smaller, but lossy. JPEG quality defaults to 100 when selected.

## Important modality note

The output is lossless only with respect to the rendered RGB image returned by OpenPhi. This is suitable for visual brightfield workflows such as H&E/IHC conversion, preview, tiling, annotation, and QuPath viewing.

Do not assume that raw fluorescence channels or quantitative intensities are preserved unless this is validated independently.

## Developer setup

This project is built with Python 3.7 because the tested Philips SDK binaries require Python 3.7 compatibility.

Create the conda environment:

```bat
conda env create -f environment.yml
conda activate isyntax_py37
```

Run from source:

```bat
python src\isyntax_to_tiff\app.py
```

Build the Windows EXE locally:

```bat
build_windows_exe.bat
```

The output will be:

```text
dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
```

Distribute the full folder:

```text
dist\iSyntaxToTIFF
```

not only the `.exe`, because PyInstaller `--onedir` builds need the adjacent dependency files.

## GitHub Actions build

The workflow in `.github/workflows/build-windows.yml` creates a Windows no-SDK ZIP automatically.

Manual build:

```text
GitHub → Actions → Build iSyntaxToTIFF Windows EXE → Run workflow
```

Release build:

```bat
git tag v1.0.0
git push origin v1.0.0
```

When a tag beginning with `v` is pushed, the workflow uploads `iSyntaxToTIFF-Windows-no-SDK.zip` to the GitHub Release.

## Suggested repository name

```text
iSyntaxToTIFF
```

## License

MIT License for this application code. The Philips Pathology SDK is separate and subject to Philips' own license terms.
