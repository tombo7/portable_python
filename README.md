# portable_python

Builds a self-contained, portable Python for **Windows x64** with your pip packages baked in.
Based on the python.org embeddable zips. Unzip anywhere, run `python.exe` — no installer, no admin, no registry.

## Quick start

1. **Actions** tab → **Build portable Python** → **Run workflow**.
2. Pick a Python version, fill in packages/requirements (see below), press **Run workflow**.
3. When the run finishes, download the zip from the run's **Artifacts** section
   (e.g. `portable_python_3.13.15`).

## Inputs

| Input | What goes in |
|---|---|
| `python_version` | dropdown: 3.13, 3.14, 3.12, 3.11 |
| `python_version_exact` | optional `X.Y.Z` override, e.g. `3.13.9` |
| `requirements_1` … `requirements_5` | a requirements.txt — encoded (see next section), a `http(s)://` URL to one, or short inline text |
| `packages_1` … `packages_5` | plain `pip install` arguments, exactly as you'd type them, e.g. `torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0` or `--index-url https://download.pytorch.org/whl/cu124 torch` |
| `keep_unzipped` | also upload the unzipped tree as a second artifact (slow) |
| `no_build_isolation` | pre-install setuptools+wheel and pass `--no-build-isolation` to pip (helps legacy sdist-only packages) |

**Install order:** slot 1 → 5. Each slot's `requirements_N` and `packages_N` are combined into
**one** `pip install` (`pip install -r <requirements_N> <packages_N…>`), so pip resolves them together.
Empty slots are skipped. Use separate slots when order matters (e.g. torch from a custom index in
slot 1, everything else in slot 2). Note pip does not resolve *across* slots — a later slot can
change what an earlier one installed; the shipped `requirements.txt` (`pip freeze`) records what
actually landed.

### Big requirements files → the encoder page

The run form's text boxes are single-line and strip newlines when you paste a multi-line file. Use the
encoder page (enable **GitHub Pages** once in repo Settings → Pages → source: branch `master`, folder `/docs`):

    https://<user>.github.io/portable_python/

Paste your requirements.txt, copy the one-line `b64gz:…` output into `requirements_N`. Everything runs
in the browser. GitHub allows 65,535 characters across all inputs; a compressed 200-line file is ~1.5 KB.

`requirements_N` accepts, auto-detected:

| Value | Meaning |
|---|---|
| `b64gz:…` | base64 of gzip of the file (what the encoder emits) |
| `b64:…` | base64 of the file |
| `https://…` | downloaded |
| an existing file path | used directly (local CLI use) |
| anything else | inline requirements text; the literal two characters `\n` become a newline, e.g. `numpy\npandas>=2` |

## Supported Python versions

| Version | Builds |
|---|---|
| 3.14 | 3.14.7 |
| 3.13 | 3.13.15 |
| 3.12 | 3.12.10 * |
| 3.11 | 3.11.9 * |

\* 3.11 and 3.12 are security-only: python.org stopped publishing Windows binaries after these
patches, so these are the newest embeddable builds that exist. Anything below 3.11 is not supported.
Any exact `X.Y.Z` that has an `embed-amd64.zip` on python.org can be given via `python_version_exact`.

## What you get

```
portable_python_3.13.15/
  python.exe, python313.dll, ...
  python313.zip/          stdlib (extracted into a folder of that name)
  python313._pth          with `import site` enabled
  sitecustomize.py        adds ./ and Lib/site-packages to sys.path
  Lib/site-packages/      your packages
  Scripts/                console entry points (not on PATH; call python.exe -m ... instead)
  requirements.txt        pip freeze of the result
  packages.txt            the pip install commands that were run
```

**Gotcha:** the embeddable distribution has no compiler or headers, so packages without a wheel for
your Python version fail to build. Add `--only-binary=:all:` to a `packages_N` slot for a fast, clear
failure instead of a slow confusing one.

## Local / CLI use

Windows only for the full build (it runs the downloaded `python.exe`); host Python 3.11+.

```
set REQUIREMENTS_1=my_requirements.txt
set PACKAGES_1=requests
python src\create_portable_python.py --python-version 3.13 --output-dir build
```

Result: `build\release_dir\portable_python_3.13.15.zip`.

Flags: `-p/--python-version`, `-u/--url` (override download URL), `-o/--output-dir` (default `build`),
`-S/--stdlib {extract,original}`, `--no-zip`, `--keep-files`, `--no-build-isolation`, `--keep-download`.

Environment variables: `PYTHON_VERSION`, `REQUIREMENTS_1..5`, `PACKAGES_1..5`, `STDLIB`,
`NO_ZIP`, `KEEP_FILES`, `NO_BUILD_ISOLATION` (booleans: `1/true/yes/on` or `0/false/no/off`).
