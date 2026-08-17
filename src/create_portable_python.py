"""Create a portable Windows Python (python.org embeddable zip + pip + your packages).

Configured via CLI flags and/or environment variables. Dependencies are given as up to
MAX_DEP_SLOTS pairs of REQUIREMENTS_<N> / PACKAGES_<N>; each pair becomes one `pip install`,
run in ascending N.

Only the pip-install / get-pip steps require Windows (they execute the downloaded python.exe);
everything else is platform independent.
"""

import argparse
import base64
import gzip
import os
import shlex
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

MIN_SUPPORTED = (3, 11)
MAX_DEP_SLOTS = 5

# Latest patch that actually ships python-X.Y.Z-embed-amd64.zip.
# python.org stops publishing Windows binaries once a minor goes security-only,
# so for those this is NOT the newest patch on python.org.
PYTHONS_DEFAULT = {
	"3.11": "3.11.9",   # security-only since 3.11.10 -> source only
	"3.12": "3.12.10",  # security-only since 3.12.11 -> source only
	"3.13": "3.13.15",
	"3.14": "3.14.7",
}

TRUE_VALS = {"1", "true", "yes", "on"}
FALSE_VALS = {"0", "false", "no", "off", ""}


def eprint(*args, **kwargs):
	print(*args, **kwargs, file = sys.stderr)


def die(msg: str, code = 1):
	eprint(f"error: {msg}")
	sys.exit(code)


def bool_env(name: str, default = False) -> bool:
	raw = os.environ.get(name)
	if raw is None:
		return default
	val = raw.strip().lower()
	if val in TRUE_VALS:
		return True
	if val in FALSE_VALS:
		return False
	die(f"invalid boolean value for {name}: {raw!r}")


def download_file(url: str, write_path: Path, tries = 5):
	for i in range(max(1, tries)):
		try:
			return urllib.request.urlretrieve(url, str(write_path))
		except Exception as ex:
			print(f"error downloading {url!r}: {ex!r}")
			if i == tries - 1:
				raise


# ---------------------------------------------------------------- versions

def resolve_version(spec: str) -> str:
	"""'3.13' -> pinned patch from PYTHONS_DEFAULT; '3.13.15' -> as is. Rejects < MIN_SUPPORTED."""
	spec = spec.strip()
	if spec.count(".") == 1:
		if spec not in PYTHONS_DEFAULT:
			die(f"unsupported python version {spec!r}; supported: {', '.join(PYTHONS_DEFAULT)}")
		version = PYTHONS_DEFAULT[spec]
	else:
		version = spec
	parts = version.split(".")
	if len(parts) != 3 or not all(p.isdigit() for p in parts):
		die(f"invalid version {version!r}, expected X.Y or X.Y.Z")
	if tuple(int(p) for p in parts[:2]) < MIN_SUPPORTED:
		die(f"python {version} is not supported, minimum is {'.'.join(map(str, MIN_SUPPORTED))}")
	return version


def embed_url(version: str) -> str:
	return f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"


# ------------------------------------------------------------ dependencies

def resolve_requirement_input(value: str, work_dir: Path, slot: int) -> Path:
	"""Turn a REQUIREMENTS_<N> value into a requirements file path.

	Accepted forms (checked in this order):
	  b64gz:<base64 of gzip>   what the encoder page emits
	  b64:<base64>             plain base64 fallback
	  http(s)://...            downloaded
	  <existing file path>     used directly
	  anything else            inline requirements text, literal "\\n" expanded to newlines
	"""
	value = value.strip()
	dest = work_dir / f"requirements_{slot}.txt"

	if value.startswith("b64gz:"):
		dest.write_bytes(gzip.decompress(base64.b64decode(value[len("b64gz:"):])))
	elif value.startswith("b64:"):
		dest.write_bytes(base64.b64decode(value[len("b64:"):]))
	elif value.startswith(("http://", "https://")):
		download_file(value, dest)
	elif Path(value).is_file():
		return Path(value).resolve()
	else:
		dest.write_text(value.replace("\\n", "\n") + "\n", encoding = "utf-8")
	return dest


def collect_pip_commands(work_dir: Path):
	"""One argv (the part after `pip install`) per non-empty REQUIREMENTS_<N>/PACKAGES_<N> slot."""
	commands = []
	for n in range(1, MAX_DEP_SLOTS + 1):
		req = os.environ.get(f"REQUIREMENTS_{n}", "").strip()
		pkgs = os.environ.get(f"PACKAGES_{n}", "").strip()
		if not req and not pkgs:
			continue
		argv = []
		if req:
			argv += ["-r", str(resolve_requirement_input(req, work_dir, n))]
		if pkgs:
			argv += shlex.split(pkgs)
		commands.append(argv)
	return commands


def pip_install(python_bin: Path, commands, no_build_isolation: bool = False):
	print(f"running {len(commands)} pip install command(s)")
	for argv in commands:
		args = [str(python_bin), "-m", "pip", "install"]
		if no_build_isolation:
			args.append("--no-build-isolation")
		args.extend(argv)
		print(f"running {shlex.join(args)}")
		subprocess.check_call(args)


# ------------------------------------------------------------------- build

def zip_dir(src_dir: Path, zip_path: Path, arcroot: str):
	with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64 = True) as zf:
		for p in sorted(src_dir.rglob("*")):
			zf.write(p, str(Path(arcroot) / p.relative_to(src_dir)))


def write_github_output(**kv):
	path = os.environ.get("GITHUB_OUTPUT")
	if path:
		with open(path, "a", encoding = "utf-8") as f:
			for k, v in kv.items():
				f.write(f"{k}={v}\n")


def main(args):
	spec = args.python_version or os.environ.get("PYTHON_VERSION")
	if not spec:
		die("no python version given (use --python-version or PYTHON_VERSION)")
	version = resolve_version(spec)
	version_short = "".join(version.split(".")[:2])   # "313"
	url = args.url or embed_url(version)
	name = f"portable_python_{version}"

	p_output_dir = Path(args.output_dir).resolve()
	p_work_dir = p_output_dir / "work"
	p_python_dir = p_output_dir / "python"
	p_python_bin = p_python_dir / "python.exe"
	p_release_dir = p_output_dir / "release_dir"
	p_embedded_zip = p_work_dir / "python_embedded.zip"

	print(f"creating {name} from {url!r} in {str(p_output_dir)!r}")
	for p in (p_work_dir, p_release_dir):
		p.mkdir(parents = True, exist_ok = True)
	if p_python_dir.exists():
		shutil.rmtree(p_python_dir)

	if not p_embedded_zip.is_file():
		print(f"downloading {url!r}")
		download_file(url, p_embedded_zip)
	print(f"unpacking to {str(p_python_dir)!r}")
	with zipfile.ZipFile(p_embedded_zip) as zf:
		zf.extractall(p_python_dir)

	# ._pth: 'import site' re-enables site/sitecustomize (and therefore pip) in the embeddable build
	(p_python_dir / f"python{version_short}._pth").write_text(
		f"python{version_short}.zip\n.\nimport site\n")
	shutil.copy(Path(__file__).with_name("sitecustomize.py"), p_python_dir / "sitecustomize.py")

	if args.stdlib == "extract":
		# unpack the stdlib zip into a *directory* of the same name; the ._pth entry keeps working
		print("extracting stdlib")
		p_stdlib_zip = p_python_dir / f"python{version_short}.zip"
		p_tmp = p_stdlib_zip.with_suffix(".tmp")
		with zipfile.ZipFile(p_stdlib_zip) as zf:
			zf.extractall(p_tmp)
		p_stdlib_zip.unlink()
		p_tmp.rename(p_stdlib_zip)

	commands = collect_pip_commands(p_work_dir)

	print("setting up pip")
	p_getpip = p_work_dir / "get-pip.py"
	download_file("https://bootstrap.pypa.io/get-pip.py", p_getpip)
	subprocess.check_call([str(p_python_bin), str(p_getpip)])

	if args.no_build_isolation:
		print("pre-installing setuptools and wheel")
		subprocess.check_call([str(p_python_bin), "-m", "pip", "install", "setuptools", "wheel"])

	pip_install(p_python_bin, commands, no_build_isolation=args.no_build_isolation)

	(p_python_dir / "requirements.txt").write_bytes(
		subprocess.check_output([str(p_python_bin), "-m", "pip", "freeze"]))
	(p_python_dir / "packages.txt").write_text(
		"".join(f"pip install {shlex.join(argv)}\n" for argv in commands))

	if not args.no_zip:
		p_zip = p_release_dir / f"{name}.zip"
		print(f"creating {str(p_zip)!r}")
		zip_dir(p_python_dir, p_zip, arcroot = name)
	if args.keep_files:
		shutil.move(str(p_python_dir), str(p_release_dir / name))
	if not args.keep_download:
		shutil.rmtree(p_work_dir)

	write_github_output(version = version, name = name)
	print(f"done: {name}")


def make_parser():
	parser = argparse.ArgumentParser(description = __doc__, formatter_class = argparse.RawDescriptionHelpFormatter)
	parser.add_argument("-p", "--python-version", help = "e.g. 3.13 or 3.13.15 (env PYTHON_VERSION)")
	parser.add_argument("-u", "--url", help = "override the embeddable zip download url")
	parser.add_argument("-o", "--output-dir", default = "build")
	parser.add_argument("-S", "--stdlib", choices = ["extract", "original"],
		default = os.environ.get("STDLIB", "extract"))
	parser.add_argument("--no-zip", action = "store_true", default = bool_env("NO_ZIP"))
	parser.add_argument("--keep-files", action = "store_true", default = bool_env("KEEP_FILES"),
		help = "also put the unzipped tree into release_dir")
	parser.add_argument("--no-build-isolation", action = "store_true", default = bool_env("NO_BUILD_ISOLATION"),
		help = "pre-install setuptools and wheel, pass --no-build-isolation to pip (for legacy sdists)")
	parser.add_argument("--keep-download", action = "store_true", help = "keep the work dir (downloaded zips)")
	return parser


if __name__ == "__main__":
	main(make_parser().parse_args())
