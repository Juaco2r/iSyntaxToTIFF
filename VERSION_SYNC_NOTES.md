# Version synchronization notes

Before tagging the Zenodo release, keep the same version in all relevant places.

For the first public Zenodo release, use:

```text
1.0.0
```

## Files to check

### `src/isyntax_to_tiff/__init__.py`

Expected:

```python
__version__ = "1.0.0"
```

### `src/isyntax_to_tiff/app.py`

Expected:

```python
APP_VERSION = "1.0.0"
```

### Git tag

Expected:

```text
v1.0.0
```

If you prefer to keep the current internal development version, change all metadata files accordingly before release.
