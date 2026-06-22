# Third-party dependency notice

## Philips Pathology SDK

**iSyntaxToTIFF** requires the Philips Pathology SDK to read Philips `.isyntax` whole-slide images.

The Philips Pathology SDK is a separate third-party dependency. It is not part of this repository, and it is not distributed as part of this application code.

Users should obtain the Philips Pathology SDK directly from Philips and comply with the applicable Philips license terms.

As of June 2026, the Philips Pathology SDK can be accessed from:

```text
https://philips.mizecx.com/login.html
```

A possible access route is to enter as `GuestUser`, search for `PathologySDK`, and download:

```text
PathologySDK_2.0-L1_Packages
```

Inside that package, use the research Python SDK package matching the operating system:

```text
Windows: Philips Pathology SDK for Windows / Python 3.7 research package
Linux:   Philips Pathology SDK for Ubuntu 20.04 / Python 3.8 research package
```

## OpenPhi

This software uses OpenPhi to access Philips `.isyntax` images through the Philips Pathology SDK.

OpenPhi is an external open-source package and remains subject to its own license and citation requirements.

## Python dependencies

Other Python dependencies are listed in the repository requirement files and remain subject to their own licenses.
