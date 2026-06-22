# Changelog

All notable changes to **iSyntaxToTIFF** are documented in this file.

## v1.0.0 - 2026-06-22

### Added

- Initial public release of iSyntaxToTIFF.
- Standalone graphical interface for Philips `.isyntax` to pyramidal RGB OME-TIFF conversion.
- Philips Pathology SDK configuration from the application menu.
- SDK preparation from ZIP archive or extracted SDK folder.
- SDK import testing for `pixelengine`, `softwarerenderbackend`, `softwarerendercontext`, and OpenPhi.
- Thumbnail preview for selected `.isyntax` files.
- Tiled conversion workflow to reduce memory usage during whole-slide export.
- Deflate lossless compression as the default output option.
- Optional JPEG compression with configurable quality.
- CSV conversion log.
- Windows and Linux build files.
- User documentation and third-party dependency notice.

### Notes

- The output OME-TIFF is lossless relative to the rendered RGB image provided by OpenPhi when Deflate compression is used.
- Raw fluorescence channels or quantitative intensity preservation should not be assumed without independent validation.
- The Philips Pathology SDK is a separate third-party dependency and must be obtained directly from Philips.
