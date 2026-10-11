"""Build the tester release zip of the add-on.

    python tools/build_release.py

Output: archive/modwall_gn_<version>.zip with one top-level folder
`modwall_gn/` holding the runtime modules, README.md, CHANGELOG.md and
LICENSE.txt. Only the files listed below go into the release; any other
top-level *.py file or folder stops the build until it is classified here, so
nothing from development leaks into a release by accident.
"""
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "modwall_gn"

# Runtime modules of the add-on (each one is imported by __init__.py).
RUNTIME_MODULES = [
    "__init__.py",
    "bmesh_baker.py",
    "callbacks.py",
    "cylinder.py",
    "ops_cylinder.py",
    "ops_tile_grid.py",
    "ops_uvw.py",
    "ops_vertex_paint.py",
    "panels.py",
    "preview_mat.py",
    "props.py",
    "tile_grid.py",
    "uv_geom.py",
    "uvw.py",
    "vertex_paint.py",
]
DOC_FILES = ["README.md", "CHANGELOG.md", "LICENSE.txt"]

# Known development-only items at the repository root (never released).
DEV_FILES = {"test_tile_cutter.py", "TODO.md", ".gitignore"}
DEV_DIRS = {"docs", "tools", "archive", ".git", ".github", ".claude", "__pycache__"}


def fail(message):
    sys.exit(f"build_release: {message}")


def read_version():
    init = ROOT / "__init__.py"
    if not init.exists():
        fail("__init__.py is missing")
    text = init.read_text(encoding="utf-8")
    match = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', text)
    if not match:
        fail("bl_info version not found in __init__.py")
    return ".".join(match.groups())


def check_tree():
    known = set(RUNTIME_MODULES) | set(DOC_FILES) | DEV_FILES | DEV_DIRS
    unknown = sorted(p.name for p in ROOT.iterdir() if p.name not in known)
    if unknown:
        fail("unclassified item(s) in the repository root: "
             + ", ".join(unknown)
             + " (add them to RUNTIME_MODULES, DOC_FILES, DEV_FILES or DEV_DIRS)")
    for name in RUNTIME_MODULES + DOC_FILES:
        if not (ROOT / name).is_file():
            fail(f"{name} is missing")


# Working material must never reach testers: links to the issue tracker or the
# repository, names of work tools, internal ticket words.
LEAK_PATTERN = re.compile(
    r"github|olegivanov|issues?/|issue tracker|ticket|tracker|project board|codex|deepseek|todo",
    re.IGNORECASE,
)


def check_leaks():
    found = []
    for name in RUNTIME_MODULES + DOC_FILES:
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        for match in LEAK_PATTERN.finditer(text):
            line = text.count(chr(10), 0, match.start()) + 1
            found.append(f"{name}:{line}: {match.group(0)}")
    if found:
        fail("working references found in release files:" + chr(10) + "  "
             + (chr(10) + "  ").join(found))


def main():
    version = read_version()
    check_tree()
    check_leaks()

    out_dir = ROOT / "archive"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{PACKAGE}_{version}.zip"
    tmp_path = out_dir / f".{PACKAGE}_{version}.zip.tmp"

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in RUNTIME_MODULES + DOC_FILES:
                zf.write(ROOT / name, f"{PACKAGE}/{name}")
        with zipfile.ZipFile(tmp_path) as zf:
            bad = zf.testzip()
            if bad:
                fail(f"corrupt entry in the new archive: {bad}")
        os.replace(tmp_path, out_path)   # the old zip stays until the new one is complete
    except OSError as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        fail(f"could not write the archive: {exc}")

    print(f"built {out_path} ({out_path.stat().st_size} bytes, version {version})")
    with zipfile.ZipFile(out_path) as zf:
        for info in zf.infolist():
            print(f"  {info.filename}  {info.file_size}")


if __name__ == "__main__":
    main()
