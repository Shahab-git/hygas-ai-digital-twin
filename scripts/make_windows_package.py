"""P5-1: builds the portable Windows demo package (a zip) from this repository. Run it from the repository root:

    python scripts/make_windows_package.py --out dist                  # package without packages (needs internet on first start)
    python scripts/make_windows_package.py --out dist --download-wheels   # also downloads the wheels for THIS machine's Python and platform,
                                                                        # so the demo installs offline (run it on the Windows machine)

What goes in: app.py, requirements.txt, requirements.lock.txt, python/, assets/, data/, docs/ (an allowlist; tests, scripts, .git, .github,
web3d, CLAUDE.md and every secrets file stay out), plus the three files of packaging/windows/ and a MANIFEST.sha256. NO KEYS: before the zip is
written the staged tree is scanned for key-like text (SUPABASE_* assignments, JWTs, private keys, project URLs); a hit stops the build.
The demo sets HYGAS_ALLOW_DB_WRITES=0 and HYGAS_LOCAL_DEMO=1 (run_demo.bat), has no .streamlit/secrets.toml and writes to no database.
"""
import argparse
import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INCLUDE_FILES = ("app.py", "requirements.txt", "requirements.lock.txt")
INCLUDE_DIRS = ("python", "assets", "data", "docs")
PACKAGING = ("run_demo.bat", "README_DEMO.txt")
SKIP_DIR_NAMES = {"__pycache__", ".git", ".venv", "node_modules", "outputs"}
SKIP_SUFFIXES = (".pyc",)
SECRET_PATTERNS = (
    ("SUPABASE assignment", re.compile(r"SUPABASE_[A-Z_]*\s*[=:]\s*[\"'][^\"']{8,}[\"']")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("Supabase project URL", re.compile(r"https://[a-z0-9]{15,}\.supabase\.co")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
STREAMLIT_CONFIG = "[browser]\ngatherUsageStats = false\n\n[server]\nheadless = false\n"


def stage(dest, root=ROOT):
    """Copies the allowlist into `dest` and returns the sorted list of relative paths."""
    out = []
    for name in INCLUDE_FILES:
        src = os.path.join(root, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, name))
            out.append(name)
    for d in INCLUDE_DIRS:
        for base, dirs, files in os.walk(os.path.join(root, d)):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIR_NAMES)
            for f in sorted(files):
                if f.endswith(SKIP_SUFFIXES):
                    continue
                rel = os.path.relpath(os.path.join(base, f), root)
                os.makedirs(os.path.join(dest, os.path.dirname(rel)), exist_ok=True)
                shutil.copy2(os.path.join(base, f), os.path.join(dest, rel))
                out.append(rel.replace(os.sep, "/"))
    for f in PACKAGING:
        with open(os.path.join(root, "packaging", "windows", f), "rb") as fh:
            data = fh.read()
        if f.endswith(".bat"):                       # cmd.exe needs CRLF; a Linux or CI checkout may hold LF (core.autocrlf)
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        with open(os.path.join(dest, f), "wb") as fh:
            fh.write(data)
        out.append(f)
    os.makedirs(os.path.join(dest, ".streamlit"), exist_ok=True)
    with open(os.path.join(dest, ".streamlit", "config.toml"), "w", encoding="utf-8") as fh:
        fh.write(STREAMLIT_CONFIG)
    out.append(".streamlit/config.toml")
    return sorted(out)


def scan_for_secrets(tree):
    """-> list of (relative path, pattern name) for every key-like match in a text file of `tree` (binary files are skipped)."""
    hits = []
    for base, _dirs, files in os.walk(tree):
        for f in files:
            path = os.path.join(base, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            for name, pat in SECRET_PATTERNS:
                if pat.search(text):
                    hits.append((os.path.relpath(path, tree).replace(os.sep, "/"), name))
    return sorted(hits)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def download_wheels(dest, root=ROOT):
    """pip download of requirements.txt for the Python and platform running this script (so run it on the Windows machine)."""
    subprocess.check_call([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "-r",
                           os.path.join(root, "requirements.txt"), "-d", dest])


def build(out_dir, wheels=False, root=ROOT, today=None):
    """Builds `out_dir/hygas-demo-<date>.zip` and returns its path; raises SystemExit if the scan finds a key-like string."""
    today = today or datetime.date.today().isoformat()
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tree = os.path.join(tmp, "hygas-demo")
        os.makedirs(tree)
        files = stage(tree, root)
        if wheels:
            download_wheels(os.path.join(tree, "wheels"), root)
            files += sorted("wheels/" + w for w in os.listdir(os.path.join(tree, "wheels")))
            with open(os.path.join(tree, "README_DEMO.txt"), "a", encoding="utf-8") as fh:
                fh.write(f"\nOFFLINE PACKAGES: the \"wheels\" folder was built for Python {sys.version_info.major}.{sys.version_info.minor} "
                         f"on {sys.platform}. The offline install works only with that Python version; with another one, "
                         "delete the wheels folder to install from the internet instead.\n")
        hits = scan_for_secrets(tree)
        if hits:
            raise SystemExit("Refusing to build: key-like text found in " + ", ".join(f"{p} ({n})" for p, n in hits))
        with open(os.path.join(tree, "MANIFEST.sha256"), "w", encoding="utf-8") as fh:
            for rel in files:
                fh.write(f"{_sha256(os.path.join(tree, rel))}  {rel}\n")
        zpath = os.path.join(out_dir, f"hygas-demo-{today}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _dirs, fs in os.walk(tree):
                for f in sorted(fs):
                    full = os.path.join(base, f)
                    z.write(full, os.path.join("hygas-demo", os.path.relpath(full, tree)))
    return zpath


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="dist")
    ap.add_argument("--download-wheels", action="store_true")
    a = ap.parse_args(argv)
    z = build(a.out, wheels=a.download_wheels)
    print(f"wrote {z} ({os.path.getsize(z) / 1e6:.1f} MB), sha256 {_sha256(z)}")


if __name__ == "__main__":
    main()
