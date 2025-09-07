import os
import sys
import subprocess
import importlib.util
from pathlib import Path
from shutil import which

REQUIREMENTS = ["PyQt5", "camoufox[geoip]"]

HERE = Path(__file__).resolve().parent       # directory containing install.py
# Candidate entry files for your app (first one found is used)
ENTRY_CANDIDATES = [
    "main_window.py",
]

def run(cmd, cwd=None):
    print(f"[~] Running: {' '.join(map(str, cmd))}")
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)

def pip_install(pkg):
    run([sys.executable, "-m", "pip", "install", pkg], cwd=HERE)

def check_and_install():
    try:
        import pip  # noqa
    except ImportError:
        print("[x] pip is not installed. Please install pip and re-run.")
        sys.exit(1)

    for spec in REQUIREMENTS:
        base = spec.split("[", 1)[0]
        if importlib.util.find_spec(base) is None:
            print(f"[!] Missing {spec}, installing…")
            pip_install(spec)
        else:
            print(f"[✓] {base} already installed")

def ensure_camoufox_browser():
    try:
        from camoufox.sync_api import Camoufox  # noqa
        print("[✓] camoufox already installed")
    except ImportError:
        print("[!] Installing camoufox…")
        pip_install("camoufox[geoip]")

    # Try to locate the browser binary
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "camoufox", "path"],
            text=True, cwd=str(HERE)
        ).strip()
    except Exception:
        out = ""

    def looks_like_browser_dir(p: Path) -> bool:
        return p.exists() and p.is_dir()

    def find_exe_in(dir_path: Path) -> Path | None:
        exe_name = "camoufox.exe" if os.name == "nt" else "camoufox"
        for path in dir_path.rglob(exe_name):
            return path
        return None

    exe_path: Path | None = None
    if out:
        p = Path(out)
        if p.is_file():
            exe_path = p
        elif looks_like_browser_dir(p):
            exe_path = find_exe_in(p)

    if exe_path and exe_path.exists():
        print(f"[✓] Camoufox binary present at {exe_path}")
        return

    print("[!] Camoufox browser binary not found. Fetching…")
    run([sys.executable, "-m", "camoufox", "fetch"], cwd=HERE)

def find_entry_file() -> Path:
    for name in ENTRY_CANDIDATES:
        candidate = HERE / name
        if candidate.exists():
            return candidate
    print("[x] Could not find an entry file. Expected one of:")
    for n in ENTRY_CANDIDATES:
        print(f"    - {n} (in {HERE})")
    sys.exit(2)

def main():
    check_and_install()
    ensure_camoufox_browser()

    entry = find_entry_file()
    print("\n[✓] Environment ready. Launching Camoufox Manager…\n")
    try:
        # Ensure we run from the project root so relative assets (.ui/.qss) resolve
        run([sys.executable, str(entry.name)], cwd=HERE)
    except subprocess.CalledProcessError as e:
        print("\n[x] Failed to launch the app.")
        print(f"    Command: {' '.join(map(str, e.cmd))}")
        print(f"    Exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
