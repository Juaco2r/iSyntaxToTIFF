# User guide

## First-time SDK setup

1. Open `iSyntaxToTIFF.exe`.
2. Click **Select / Prepare SDK folder**.
3. Select the root folder of the Philips Pathology SDK, for example:

```text
C:\PhilipsSDK\SDK2
```

or the downloaded SDK folder, for example:

```text
C:\Users\<user>\Downloads\Philips\philips-pathologysdk-2.0-L1-windows10-py37-research
```

4. Click **Run SDK installer** if the SDK has not yet been installed/prepared on that computer. This may require administrator permissions.
5. Click **Test SDK**.

The expected result is:

```text
pixelengine OK
softwarerenderbackend OK
softwarerendercontext OK
OpenPhi OK
Ready for iSyntax conversion
```

The SDK path is saved in the user settings folder and normally only needs to be selected once.

## Conversion

1. Click **Add iSyntax files**.
2. Select one or more `.isyntax` files.
3. Optionally click **Preview selected** to generate a thumbnail.
4. Choose the output folder.
5. Use **Deflate lossless** for maximum fidelity relative to the RGB image rendered by OpenPhi.
6. Click **Convert**.

The output is a pyramidal RGB OME-TIFF file.

## Important limitation

The converter writes a rendered RGB OME-TIFF from the Philips SDK/OpenPhi output. It is intended primarily for brightfield/H&E/IHC visual conversion and downstream workflows such as preview, tiling, annotation, and QuPath viewing.

Do not assume raw fluorescence channels or original quantitative intensities are preserved unless you validate this against the acquisition metadata and a trusted reference export.
