"""
NonRoot Auto-Updater.
Checks remote Git repository or GitHub API for updates and applies them safely.
Supports:
1. Local git repository (git fetch, git rev-parse, git pull).
2. Standalone App / Non-git installation (GitHub REST API + zip download / extraction).
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import datetime
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

GITHUB_REPO = "nadaroot/deepsekagent"
GITHUB_API_COMMITS = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
GITHUB_ZIP_URL = f"https://codeload.github.com/{GITHUB_REPO}/zip/refs/heads/main"

def get_repo_dir() -> Optional[Path]:
    """Finds the true NonRoot git repository directory, avoiding random user workspaces."""
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path.home() / ".nonroot" / "repo",
        Path("/Users/mac/Documents/strim/playerok/nonroot"),
        Path.home() / "Documents" / "strim" / "playerok" / "nonroot",
        Path.cwd()
    ]
    for p in candidates:
        if (p / ".git").exists() and (p / "nonroot").exists():
            return p
    return None

def get_installed_app_dir() -> Optional[Path]:
    """Returns ~/.nonroot/app directory if it exists."""
    app_dir = Path.home() / ".nonroot" / "app"
    if app_dir.exists():
        return app_dir
    return None

def get_macos_app_bundle() -> Optional[Path]:
    """Returns /Users/.../Applications/NonRoot.app or /Applications/NonRoot.app if present."""
    candidates = [
        Path.home() / "Applications" / "NonRoot.app",
        Path("/Applications/NonRoot.app")
    ]
    for p in candidates:
        if p.exists() and (p / "Contents" / "Resources" / "app").exists():
            return p
    return None

def get_current_version_info() -> Dict[str, str]:
    """Reads current commit hash and version tag from assets/version.json or git."""
    repo = get_repo_dir()
    commit = ""
    version = "1.1.0"

    candidates = [
        Path(__file__).resolve().parent.parent / "assets" / "version.json",
        Path.home() / ".nonroot" / "app" / "assets" / "version.json"
    ]
    bundle = get_macos_app_bundle()
    if bundle:
        candidates.append(bundle / "Contents" / "Resources" / "app" / "assets" / "version.json")

    for c in candidates:
        if c.exists():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                commit = data.get("commit", "")
                version = data.get("version", version)
                if commit:
                    break
            except Exception:
                pass

    if not commit and repo and (repo / ".git").exists():
        try:
            p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=5)
            if p.returncode == 0:
                commit = p.stdout.strip()[:7]
        except Exception:
            pass

    return {"commit": commit[:7] if commit else "unknown", "version": version}

def _update_version_file(path: Path, commit: str):
    """Safely updates or creates assets/version.json with the given commit hash."""
    try:
        data = {"version": "1.1.0"}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        data["commit"] = commit[:7] if commit else "latest"
        data["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _sync_tree(src: Path, dst: Path):
    """Recursively copies files from src to dst excluding cache and dotfiles."""
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        dest_item = dst / item.name
        if item.is_dir():
            _sync_tree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)

def check_for_updates() -> Dict[str, Any]:
    """
    Checks for updates via git fetch if running from a git repo,
    or via GitHub REST API if running in standalone/bundle mode.
    """
    ver_info = get_current_version_info()
    current_commit = ver_info["commit"]
    repo = get_repo_dir()

    # Strategy 1: Git repository check
    if repo and (repo / ".git").exists():
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            p_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=6)
            if p_head.returncode == 0:
                current_commit = p_head.stdout.strip()[:7]

            p_fetch = subprocess.run(
                ["git", "fetch", "origin", "main", "--quiet"],
                cwd=str(repo), capture_output=True, text=True, timeout=10, env=env
            )
            if p_fetch.returncode == 0:
                # Count commits where origin/main is strictly ahead of local HEAD
                p_ahead = subprocess.run(
                    ["git", "rev-list", "HEAD..origin/main", "--count"],
                    cwd=str(repo), capture_output=True, text=True, timeout=6
                )
                ahead_count = int(p_ahead.stdout.strip()) if (p_ahead.returncode == 0 and p_ahead.stdout.strip().isdigit()) else 0

                p_remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(repo), capture_output=True, text=True, timeout=6)
                remote_short = p_remote.stdout.strip()[:7] if p_remote.returncode == 0 else ""

                if ahead_count > 0:
                    p_log = subprocess.run(["git", "log", "-1", "--pretty=%s", "origin/main"], cwd=str(repo), capture_output=True, text=True, timeout=6)
                    msg = p_log.stdout.strip() if p_log.returncode == 0 else "Новое обновление"
                    return {
                        "has_update": True,
                        "current_commit": current_commit,
                        "latest_commit": remote_short,
                        "ahead_count": ahead_count,
                        "message": msg,
                        "method": "git"
                    }
                else:
                    return {
                        "has_update": False,
                        "current_commit": current_commit,
                        "method": "git"
                    }
        except Exception:
            pass

    # Strategy 2: GitHub REST API
    try:
        req = urllib.request.Request(
            GITHUB_API_COMMITS,
            headers={
                "User-Agent": f"NonRoot-Agent/{ver_info['version']}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                remote_sha = data.get("sha", "")
                remote_short = remote_sha[:7]
                commit_msg = data.get("commit", {}).get("message", "Новое обновление").split("\n")[0]
                has_update = bool(remote_short and current_commit != "unknown" and current_commit != remote_short)
                return {
                    "has_update": has_update,
                    "current_commit": current_commit,
                    "latest_commit": remote_short,
                    "message": commit_msg,
                    "method": "github_api"
                }
    except Exception as e:
        return {
            "has_update": False,
            "current_commit": current_commit,
            "error": f"Проверка обновлений недоступна: {str(e)}"
        }

    return {"has_update": False, "current_commit": current_commit}

def apply_update() -> Dict[str, Any]:
    """
    Applies updates.
    If git repo: performs git pull, updates assets/version.json, and runs setup_macos.sh.
    If standalone: downloads zip from GitHub, extracts, and updates ~/.nonroot/app and NonRoot.app.
    """
    repo = get_repo_dir()

    # Strategy 1: Git repository pull
    if repo and (repo / ".git").exists():
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            subprocess.run(["git", "stash"], cwd=str(repo), capture_output=True, text=True, timeout=10, env=env)
            p_pull = subprocess.run(["git", "pull", "origin", "main"], cwd=str(repo), capture_output=True, text=True, timeout=30, env=env)
            if p_pull.returncode != 0:
                err_text = p_pull.stderr.strip() or p_pull.stdout.strip()
                return {"success": False, "error": f"Ошибка git pull: {err_text}"}

            p_new_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=6)
            new_commit = p_new_head.stdout.strip()[:7] if p_new_head.returncode == 0 else "latest"

            # Update assets/version.json in source repo
            _update_version_file(repo / "assets" / "version.json", new_commit)

            # Re-sync macOS bundle and ~/.nonroot/app if setup_macos.sh exists
            setup_script = repo / "scripts" / "setup_macos.sh"
            if sys.platform == "darwin" and setup_script.exists():
                subprocess.run(["bash", str(setup_script)], cwd=str(repo), capture_output=True, text=True, timeout=60)

            return {
                "success": True,
                "commit": new_commit,
                "message": f"Обновление {new_commit} успешно установлено!"
            }
        except Exception as e:
            return {"success": False, "error": f"Ошибка обновления через git: {str(e)}"}

    # Strategy 2: Download ZIP from GitHub and unpack
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_dest = tmp_path / "update.zip"

            req = urllib.request.Request(GITHUB_ZIP_URL, headers={"User-Agent": "NonRoot-Agent"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(zip_dest, "wb") as f:
                    f.write(resp.read())

            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(tmp_path)

            extracted_root = None
            for p in tmp_path.iterdir():
                if p.is_dir() and p.name.startswith("deepsekagent"):
                    extracted_root = p
                    break

            if not extracted_root:
                return {"success": False, "error": "Не удалось распаковать архив обновления"}

            # Fetch latest commit SHA from GitHub API
            try:
                req_c = urllib.request.Request(GITHUB_API_COMMITS, headers={"User-Agent": "NonRoot-Agent"})
                with urllib.request.urlopen(req_c, timeout=6) as c_resp:
                    c_data = json.loads(c_resp.read().decode("utf-8"))
                    new_commit = c_data.get("sha", "")[:7]
            except Exception:
                new_commit = "latest"

            _update_version_file(extracted_root / "assets" / "version.json", new_commit)

            # Sync to ~/.nonroot/app
            target_app = Path.home() / ".nonroot" / "app"
            target_app.mkdir(parents=True, exist_ok=True)
            _sync_tree(extracted_root / "nonroot", target_app / "nonroot")
            _sync_tree(extracted_root / "assets", target_app / "assets")
            if (extracted_root / "nonroot.py").exists():
                shutil.copy2(extracted_root / "nonroot.py", target_app / "nonroot.py")

            # Sync to macOS app bundle if present
            bundle = get_macos_app_bundle()
            if bundle:
                bundle_app = bundle / "Contents" / "Resources" / "app"
                if bundle_app.exists():
                    _sync_tree(extracted_root / "nonroot", bundle_app / "nonroot")
                    _sync_tree(extracted_root / "assets", bundle_app / "assets")
                    if (extracted_root / "nonroot.py").exists():
                        shutil.copy2(extracted_root / "nonroot.py", bundle_app / "nonroot.py")

            return {
                "success": True,
                "commit": new_commit,
                "message": f"Обновление {new_commit} успешно установлено!"
            }
    except Exception as e:
        return {"success": False, "error": f"Ошибка скачивания обновления: {str(e)}"}
