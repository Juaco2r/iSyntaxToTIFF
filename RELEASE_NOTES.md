# Release notes - iSyntaxToTIFF v1.0.0

DOI: https://doi.org/10.5281/zenodo.20798592

This is the initial public release of **iSyntaxToTIFF**, a standalone research tool for converting Philips `.isyntax` whole-slide images to pyramidal RGB OME-TIFF using OpenPhi and the Philips Pathology SDK.

## Main features

- Convert Philips `.isyntax` files to pyramidal `.ome.tif` files.
- Configure the Philips Pathology SDK from the graphical interface.
- Prepare the SDK from a ZIP archive or an extracted SDK folder.
- Test SDK imports directly from the app.
- Preview thumbnails before conversion.
- Use Deflate lossless compression by default.
- Optionally use JPEG compression with quality control.
- Save conversion logs as CSV.
- Provide Windows and Linux build workflows.

## Recommended use

This tool is intended for visual brightfield workflows such as H&E/IHC conversion, preview, annotation, tiling, and viewing in OME-TIFF-compatible software.

## Important note

The Philips Pathology SDK is a separate third-party dependency and is not part of this repository. Users should obtain it directly from Philips and comply with the applicable Philips license terms.
