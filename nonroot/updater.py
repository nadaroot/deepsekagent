"""
NonRoot Auto-Updater.
Checks remote Git repository for updates and applies them safely.
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

def get_repo_dir() -> Path:
    current = Path(__file__).resolve().parent.parent
    if (current / ".git").exists():
        return current
    if (Path.cwd() / ".git").exists():
        return Path.cwd()
    return current

def check_for_updates() -> Dict[str, Any]:
    repo = get_repo_dir()
    if not (repo / ".git").exists():
        return {"has_update": False, "error": "Не является git-репозиторием"}

    try:
        p_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=6)
        if p_head.returncode != 0:
            return {"has_update": False, "error": "Не удалось определить текущую версию"}
        current_hash = p_head.stdout.strip()

        # Fetch remote origin main
        p_fetch = subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=str(repo), capture_output=True, text=True, timeout=12)
        if p_fetch.returncode != 0:
            return {"has_update": False, "current_commit": current_hash[:7], "error": "Нет соединения с удаленным репозиторием"}

        # Compare with remote origin/main
        p_remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(repo), capture_output=True, text=True, timeout=6)
        if p_remote.returncode != 0:
            return {"has_update": False, "current_commit": current_hash[:7]}
        remote_hash = p_remote.stdout.strip()

        if current_hash != remote_hash:
            p_log = subprocess.run(["git", "log", "-1", "--pretty=%s", "origin/main"], cwd=str(repo), capture_output=True, text=True, timeout=6)
            msg = p_log.stdout.strip() if p_log.returncode == 0 else "Новое обновление"
            return {
                "has_update": True,
                "current_commit": current_hash[:7],
                "latest_commit": remote_hash[:7],
                "message": msg
            }
        else:
            return {
                "has_update": False,
                "current_commit": current_hash[:7]
            }
    except Exception as e:
        return {"has_update": False, "error": str(e)}

def apply_update() -> Dict[str, Any]:
    repo = get_repo_dir()
    if not (repo / ".git").exists():
        return {"success": False, "error": "Не является git-репозиторием"}

    try:
        subprocess.run(["git", "stash"], cwd=str(repo), capture_output=True, text=True, timeout=10)

        p_pull = subprocess.run(["git", "pull", "origin", "main"], cwd=str(repo), capture_output=True, text=True, timeout=30)
        if p_pull.returncode != 0:
            return {"success": False, "error": p_pull.stderr.strip() or "Ошибка при выполнении git pull"}

        setup_script = repo / "scripts" / "setup_macos.sh"
        if sys.platform == "darwin" and setup_script.exists():
            subprocess.run(["bash", str(setup_script)], cwd=str(repo), capture_output=True, text=True, timeout=60)

        p_new_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=6)
        new_commit = p_new_head.stdout.strip()[:7] if p_new_head.returncode == 0 else "latest"

        return {
            "success": True,
            "commit": new_commit,
            "message": "Обновление успешно установлено!"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
