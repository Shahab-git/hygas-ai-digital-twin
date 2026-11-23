"""P5-1: scripts/make_windows_package.py and packaging/windows/. The package must carry no key-like text and no secrets file, run the demo with
the database writes off and the local-demo flag on, and contain what app.py needs. The .bat file itself is only read as text here (it can be run
only on Windows); the zip is built and unzipped in a temporary directory, nothing else is executed."""
import os
import sys
import tempfile
import zipfile

import test_app_smoke as smoke

sys.path.insert(0, os.path.join(smoke.ROOT, "scripts"))
import make_windows_package as mwp


def _build(tmp):
    return mwp.build(tmp, today="2026-01-01")


def test_the_zip_has_the_runtime_files_and_none_of_the_excluded_ones():
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(_build(tmp)) as z:      # closed before the directory is removed (Windows cannot delete an open file)
            names = set(z.namelist())
    for need in ("app.py", "requirements.txt", "run_demo.bat", "README_DEMO.txt", "MANIFEST.sha256", ".streamlit/config.toml",
                 "assets/plant3d.bundle.js", "data/equipment_registry.json", "data/thermo_nasa9.json", "python/live_runner.py"):
        assert "hygas-demo/" + need in names, need
    bad = [n for n in names if any(x in n for x in ("secrets", ".env", "/tests/", "/scripts/", "/.git", "/.github/", "web3d", "__pycache__", "CLAUDE.md"))]
    assert bad == []


def test_a_planted_key_stops_the_build_and_the_repository_itself_is_clean():
    with tempfile.TemporaryDirectory() as tmp:
        for text in ('SUPABASE_KEY = "abcdefghijklmnop1234"', "token eyJhbGciOiJIUzI1NiIsInR5cCI6.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6.abcdefghij1234567890",
                     "https://abcdefghijklmnopqrst.supabase.co", "-----BEGIN RSA PRIVATE KEY-----"):
            with open(os.path.join(tmp, "x.txt"), "w", encoding="utf-8") as fh:
                fh.write(text)
            assert mwp.scan_for_secrets(tmp), text
    with tempfile.TemporaryDirectory() as tmp:
        tree = os.path.join(tmp, "t")
        os.makedirs(tree)
        mwp.stage(tree)
        assert mwp.scan_for_secrets(tree) == []


def test_the_manifest_matches_the_files_and_the_bat_sets_the_safe_environment():
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(_build(tmp)) as z:
            rows = [l.split("  ", 1) for l in z.read("hygas-demo/MANIFEST.sha256").decode().splitlines()]
            assert len(rows) > 50
            for digest, rel in rows[:25]:
                assert mwp._sha256_bytes(z.read("hygas-demo/" + rel)) == digest, rel
            raw = z.read("hygas-demo/run_demo.bat")
        bat = raw.decode()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), "the .bat must have CRLF line endings only"
    assert 'set "HYGAS_ALLOW_DB_WRITES=0"' in bat and 'set "HYGAS_LOCAL_DEMO=1"' in bat
    assert "--no-index --find-links wheels" in bat and "secrets" not in bat.lower()


def test_the_bat_finds_python_without_where_and_checks_the_version():
    """Found on a real laptop (2026-11-20): the machine PATH lacked the Windows folder, so `where` failed and the
    old launcher reported "Python not found" although Python 3.14 was installed. The launcher must not use `where`,
    must restore the Windows folders for its own process, and must accept only a Python >= 3.11 that really runs.
    Not executed here (no Windows in this environment): this checks the text only."""
    bat = open(os.path.join(smoke.ROOT, "packaging", "windows", "run_demo.bat")).read()
    assert "where " not in bat
    assert 'set "PATH=%SystemRoot%\\System32;%SystemRoot%;%PATH%"' in bat
    assert "sys.version_info >= (3, 11)" in bat and "py -3" in bat and "%LocalAppData%" in bat


def _bat_text():
    return open(os.path.join(smoke.ROOT, "packaging", "windows", "run_demo.bat")).read()


def test_every_goto_and_call_in_the_bat_has_exactly_one_label():
    """A text-level control-flow check. The first P5-3 draft inserted a block at the wrong place and left a goto
    without a label and a label twice; a text-only 'contains' test did not see it. Not a substitute for running the
    file on Windows (not done here)."""
    import re
    bat = _bat_text()
    labels = re.findall(r"^:(\w+)\s*$", bat, flags=re.M)
    assert len(labels) == len(set(labels)), "a label is defined twice: " + str(labels)
    for target in re.findall(r"\b(?:goto|call)\s+:(\w+)", bat, flags=re.I):
        if target.lower() != "eof":
            assert target in labels, "goto/call without a label: " + target


def test_the_bat_and_readme_tell_a_zip_user_to_extract_first():
    """Found on a real laptop (2026-11-20): a double-click inside the zip window copies only the .bat to a temp
    folder, so requirements.txt is missing and pip fails with an obscure message."""
    bat = _bat_text()
    lines = [l.strip() for l in bat.splitlines()]
    i_check = lines.index('if not exist "requirements.txt" goto :notextracted')
    i_py = lines.index('set "PY="')
    assert i_check < i_py, "the extract check must run before any Python search"
    # the hint block sits after :notextracted and ends with goto :end, not in the main path
    i_label = lines.index(":notextracted")
    assert i_label > lines.index(":run") and "Extract All" in lines[i_label + 1] and lines[i_label + 2] == "goto :end"
    readme = open(os.path.join(smoke.ROOT, "packaging", "windows", "README_DEMO.txt")).read()
    assert "Extract All" in readme.split("WHAT THIS IS")[0]

