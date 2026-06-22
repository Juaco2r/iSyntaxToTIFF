# Zenodo release checklist for iSyntaxToTIFF

Use this checklist before creating the GitHub release that will be archived by Zenodo.

## Repository metadata

- [ ] Add `.zenodo.json` to the repository root.
- [ ] Add `CITATION.cff` to the repository root.
- [ ] Add `AUTHORS.md` to the repository root.
- [ ] Add `CHANGELOG.md` to the repository root.
- [ ] Add `RELEASE_NOTES.md` to the repository root.
- [ ] Replace `NOTICE_THIRD_PARTY.md` with the updated version.
- [ ] Add the citation section from `README_CITATION_SNIPPET.md` into `README.md`.

## Version consistency

- [ ] Confirm `src/isyntax_to_tiff/__init__.py` uses the release version.
- [ ] Confirm `APP_VERSION` in `src/isyntax_to_tiff/app.py` uses the release version.
- [ ] Confirm the Git tag matches the release version.

Recommended first public release version:

```text
v1.0.0
```

## README checks

- [ ] Confirm the README does not use the term `no-SDK` in user-facing artifact names.
- [ ] Confirm the README states that the Philips Pathology SDK should be obtained directly from Philips.
- [ ] Confirm the README points to the correct environment file name.

If the repository contains `environment.yml`, the developer command should be:

```bat
conda env create -f environment.yml
```

not:

```bat
conda env create -f environment-windows.yml
```

unless `environment-windows.yml` is actually added.

## Release steps

```bat
git status
git add .
git commit -m "Prepare repository for Zenodo release"
git tag v1.0.0
git push origin main
git push origin v1.0.0
```

Then create or confirm the GitHub release for `v1.0.0` and verify the Zenodo record after ingestion.

## After Zenodo DOI is generated

- [ ] Add the Zenodo DOI to the README citation section.
- [ ] Add the Zenodo DOI to `CITATION.cff` if desired.
- [ ] Confirm the Zenodo record has the correct title, creator, ORCID, license, keywords, and description.
