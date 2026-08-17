# CLAUDE.md

Guidance for AI assistants working in this repo.

## What this project is

Builds a portable Windows x64 Python (python.org embeddable zip + pip + user packages) via a
`workflow_dispatch` GitHub Actions workflow. A user opens the Actions tab, picks a version, fills
in requirements/packages, and downloads a zip artifact. See `README.md` for the user-facing docs.

## Layout

| Path | Role |
|---|---|
| `src/create_portable_python.py` | The entire build. Stdlib only. Download embed zip → patch `._pth` → drop `sitecustomize.py` → extract stdlib → get-pip → `pip install` per slot → write `requirements.txt`/`packages.txt` → zip. Only the steps that exec `python.exe` need Windows. |
| `src/sitecustomize.py` | Copied into the build; adds root dir and `Lib/site-packages` to `sys.path`. |
| `.github/workflows/build.yml` | The workflow. `workflow_dispatch` only, `windows-2025`. Inputs → env vars → script. Uploads `build/release_dir/portable_python_<X.Y.Z>.zip` as artifact `portable_python_<X.Y.Z>`. |
| `docs/index.html` | GitHub Pages encoder page: requirements.txt → single-line `b64gz:` value. Pure browser JS, no build step. Must stay in sync with `resolve_requirement_input()` in the script. |
| `README.md` | User docs. |

No tests directory; verification is the Linux checks below plus a real workflow run.

## Key design facts

- **Dependency slots:** env `REQUIREMENTS_1..5` / `PACKAGES_1..5` (`MAX_DEP_SLOTS`). Each slot with
  content becomes **one** `pip install -r <req> <packages…>`; slots run in ascending order; empty
  slots skipped. Do not merge slots or split a slot into multiple installs — order and per-slot
  resolution are the point.
- **`REQUIREMENTS_N` auto-detect order:** `b64gz:` → `b64:` → `http(s)://` → existing file path →
  inline text with literal `\n` expanded. Prefixes are unambiguous vs. real requirement syntax.
- **`PACKAGES_N`** is `shlex.split` straight onto `pip install` — flags like `--index-url` work.
- **Versions:** `PYTHONS_DEFAULT` pins the latest patch that *actually has* an
  `embed-amd64.zip`. 3.11 and 3.12 are security-only and python.org stopped shipping Windows
  binaries at 3.11.9 / 3.12.10 — do not "update" those to a newer patch without checking
  `https://www.python.org/ftp/python/<ver>/` for the zip. Minimum supported is 3.11.
- **Workflow inputs** all pass through `env:`; never interpolate `${{ inputs.* }}` inside `run:`.
- GitHub `workflow_dispatch` limits: 25 inputs, 65,535 chars total. Currently 13 inputs.
- Free-text booleans (`NO_ZIP`, `KEEP_FILES`) go through `bool_env`; `""` means false.
- Zipping is stdlib `zipfile` with an explicit archive root — no `7z` dependency.

## Verifying changes

Linux (before pushing):
```
python3 -m compileall -q src/
# import the module and exercise resolve_version / resolve_requirement_input /
# collect_pip_commands / bool_env / zip_dir directly — see git history of this
# file's introduction for the check script that was used.
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest   # workflow lint
```
The download/unpack/`._pth`/stdlib steps also run fine on Linux; only get-pip and pip need Windows.

Real test: push the branch, run the workflow on it (the Run-workflow dialog has a branch picker),
download the artifact, and on Windows run
`portable_python_<ver>\python.exe -c "import <pkg>, sys; print(sys.version)"`.

Note: the Codespace `GITHUB_TOKEN` cannot fire `workflow_dispatch` (403). Trigger runs from the
browser, or `gh auth login` with a personal token first. `gh run list/view/download` do work.

## Git workflow (required)

- **All development happens on a new branch.** Never commit directly to `master`.
- **Never, ever push `master`.** Not `git push origin master`, not `--force`, not via any other
  route. `master` only changes through an approved PR merged on GitHub. Pushing other branches
  is fine and expected (e.g. to run CI on them).
- **Default loop: make the requested changes, then ask for feedback.**
  Do not push, open PRs, or merge on your own initiative.
- **Only push the non master branch when actually needed** — e.g. to trigger a workflow run on it — or when
  asked. Pushing is not part of "done".
- **Do not create PRs on your own.** The repo owner decides when and whether to open a PR. Only
  create one if explicitly asked to.
- **Do not merge to `master` without explicit approval** from the repo owner.
- **Stay on the branch.** Do not switch back to `master`; the working tree should remain on the
  feature branch so feedback can be addressed with follow-up commits until it is approved and
  merged.
- **Merge method: squash** by default.
- **No AI co-author trailers** in commit messages — omit `Co-Authored-By: Claude …` lines entirely.
