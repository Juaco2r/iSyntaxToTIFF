# iSyntaxToTIFF

Standalone tool to convert Philips `.isyntax` whole-slide images to pyramidal RGB OME-TIFF using OpenPhi and the Philips Pathology SDK.

The application is designed as a focused iSyntax converter, separate from TiffCropper, so that iSyntax support can remain isolated from the standard crop, preview, tile, merge, and visualization workflows.

## What this app does

- Configure the Philips Pathology SDK path from the graphical interface.
- Test the required SDK imports in the correct order.
- Preview a small thumbnail of `.isyntax` files.
- Convert `.isyntax` files to pyramidal `.ome.tif` files.
- Use Deflate lossless compression by default.
- Optionally use JPEG compression with quality control.
- Save a CSV conversion log.
- Support Windows and Linux builds, depending on the corresponding Philips Pathology SDK package.

## Philips Pathology SDK requirement

This application requires the Philips Pathology SDK to read `.isyntax` files. The SDK should be obtained separately from Philips and configured from the application menu.

As of June 2026, the Philips Pathology SDK can be accessed from:

```text
https://philips.mizecx.com/login.html
```

A possible access route is to enter as `GuestUser`, search for `PathologySDK`, and download the package named:

```text
PathologySDK_2.0-L1_Packages
```

Inside that package, Philips provides operating-system-specific SDK archives. Use the research Python package that matches your operating system and Python compatibility:

```text
Windows: Philips Pathology SDK for Windows / Python 3.7 research package
Linux:   Philips Pathology SDK for Ubuntu 20.04 / Python 3.8 research package
```

After downloading and extracting the appropriate SDK package, open iSyntaxToTIFF and configure the SDK folder from:

```text
File > Select / Prepare SDK folder
```

Then run:

```text
File > Test SDK
```

Expected SDK test result:

```text
pixelengine OK
softwarerenderbackend OK
softwarerendercontext OK
OpenPhi OK
Ready for iSyntax conversion
```

## Recommended workflow for end users

1. Download the latest iSyntaxToTIFF release for your operating system.
2. Extract the downloaded archive.
3. Run the application.
4. Download and extract the Philips Pathology SDK package that matches your operating system.
5. In the app, go to `File > Select / Prepare SDK folder`.
6. Select the Philips SDK root folder.
7. Use `File > Run SDK installer` if the SDK has not been installed or prepared before.
8. Use `File > Test SDK`.
9. Add `.isyntax` files.
10. Preview selected files if desired.
11. Convert them to pyramidal OME-TIFF.

If no output folder is selected, the converted `.ome.tif` file will be saved beside each input `.isyntax` file. To set a specific output folder, use:

```text
File > Set output folder
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

JPEG compression is optional and produces smaller files, but it is lossy. JPEG quality defaults to 100 when selected.

## Important modality note

The output is lossless only with respect to the rendered RGB image returned by OpenPhi. This is suitable for visual brightfield workflows such as H&E/IHC conversion, preview, tiling, annotation, and QuPath viewing.

Do not assume that raw fluorescence channels or quantitative intensities are preserved unless this is validated independently against the original acquisition data and metadata.

## Developer setup: Windows

The Windows build uses Python 3.7 because the tested Philips Pathology SDK Windows binaries require Python 3.7 compatibility.

Create the conda environment:

```bat
conda env create -f environment-windows.yml
conda activate isyntax_py37
```

Alternatively, install dependencies manually:

```bat
conda activate isyntax_py37
python -m pip install --upgrade "pip<24"
pip install -r requirements-windows-py37.txt
```

Run from source:

```bat
python src\isyntax_to_tiff\app.py
```

Build the Windows application locally:

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

not only the `.exe`, because PyInstaller `--onedir` builds require adjacent dependency files.

## Developer setup: Linux

The Linux build targets the Ubuntu 20.04 / Python 3.8 Philips Pathology SDK research package.

Install Python dependencies in a Python 3.8 environment:

```bash
python3.8 -m venv .venv-isyntax-linux
source .venv-isyntax-linux/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-linux-py38.txt
```

Run from source:

```bash
python src/isyntax_to_tiff/app.py
```

Build the Linux application locally:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

The output will be:

```text
dist/iSyntaxToTIFF/iSyntaxToTIFF
```

Package the Linux build:

```bash
tar -czf iSyntaxToTIFF-Linux.tar.gz -C dist iSyntaxToTIFF
```

## GitHub Actions build

The workflow in `.github/workflows/build.yml` creates Windows and Linux application builds automatically.

Manual build:

```text
GitHub > Actions > Build iSyntaxToTIFF > Run workflow
```

Release build:

```bat
git tag v1.0.0
git push origin v1.0.0
```

When a tag beginning with `v` is pushed, the workflow uploads the release artifacts, for example:

```text
iSyntaxToTIFF-Windows.zip
iSyntaxToTIFF-Linux.tar.gz
```

## Suggested repository name

```text
iSyntaxToTIFF
```

## License

MIT License for this application code.

The Philips Pathology SDK is separate software provided by Philips and is subject to Philips' own license terms.
