"""
Standalone Binary Builder for NonRoot (PyInstaller).
Builds standalone single-file executables for Windows, macOS, and Linux.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def build():
    base_dir = Path(__file__).parent.resolve()
    print("\n=== Building NonRoot Standalone Executable ===")

    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    sep = ";" if sys.platform == "win32" else ":"
    ui_folder = base_dir / "nonroot" / "ui"
    assets_folder = base_dir / "assets"

    add_data_ui = f"{str(ui_folder)}{sep}nonroot/ui"
    add_data_assets = f"{str(assets_folder)}{sep}assets"

    entry_point = base_dir / "nonroot.py"
    bin_name = "NonRoot"

    icon_path = None
    if sys.platform == "darwin":
        icns_file = assets_folder / "app.icns"
        if icns_file.exists():
            icon_path = str(icns_file)
    else:
        ico_file = assets_folder / "app.ico"
        if ico_file.exists():
            icon_path = str(ico_file)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        f"--name={bin_name}",
        "--onefile",
        "--clean",
        f"--add-data={add_data_ui}",
        f"--add-data={add_data_assets}",
        "--hidden-import=json",
        "--hidden-import=queue",
        "--hidden-import=threading",
        "--hidden-import=urllib.request",
        "--hidden-import=urllib.parse",
        "--hidden-import=http.server",
        "--hidden-import=mimetypes"
    ]

    if icon_path:
        cmd.append(f"--icon={icon_path}")

    cmd.append(str(entry_point))

    print(f"Running command: {' '.join(cmd)}\n")
    subprocess.check_call(cmd, cwd=str(base_dir))

    ext = ".exe" if sys.platform == "win32" else ""
    dist_file = base_dir / "dist" / f"{bin_name}{ext}"
    print(f"\n[+] Build successful!")
    print(f"[+] Output binary: {dist_file}")
    return dist_file

if __name__ == "__main__":
    build()
