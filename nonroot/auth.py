"""
DeepSeek Authentication & Token Manager for NonRoot.
Handles bundled default tokens, browser-based re-authentication,
token backups, reverting, and custom token import.
"""

import os
import sys
import json
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

HOME_DIR = Path.home() / ".nonroot"
CANONICAL_AUTH_FILE = HOME_DIR / "deepseek-auth.json"
BACKUP_AUTH_FILE = HOME_DIR / "deepseek-auth.backup.json"

DEFAULT_BUNDLED_AUTH = {
    "token": "NNqBskEPJF1LIREb1JjXS02NSumQbP9RnjZHHf3DDiHefo8MjPCACzcBDcG2NM4w",
    "hif_dliq": "",
    "hif_leim": "",
    "cookie": "aws-waf-token=40f490ba-ca0b-4939-ae9c-b7cabbff9ed0:CQoAaqlBb8DfEQAA:avcZGD6IB3t5Is/4bHbdm6jIQm6M7it3CBkSU8hEcWUtEv4am0X1wpB79BI/3da0Bo0XYdI/hyW1bOcL8DAQuXEtFmBN2UPb2D3Y/jngY8ri4aNRiT8OEHLYnYhaAfbCJy+CjXNdUJk8UR73yaGIsC/emNVsHAbu4X2EBeKwqyBihIITTCg13eG6cpmBmSd14yaMROBCJfRFVqLVo4oiZog9acpteW7lzAL1HgUwI8qeAem9CzvcAIF+II02cvhmJJcK4IDC; smidV2=20260917135142ab8206e02fd036401834c7942a0f7d9b00436ca066114f500; .thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae=DNtZpKCESHLGie99OwZLC2h1b6JV60OROi/TfmwVCWYjoPwmRjBLsJqte5e6HPrRoE1bi2dvyftduj7cRoIOlQ%3D%3D; ds_session_id=c3227ceebc254b1698f6255d3a925d9d; ds_cookie_preference=%257B%2522level%2522%253A%2522all%2522%257D",
    "wasmUrl": "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm"
}

def get_auth_paths():
    paths = [
        CANONICAL_AUTH_FILE,
        HOME_DIR / "deepseek-api" / "deepseek-auth.json",
        Path(__file__).resolve().parent.parent.parent / "deepseek-api" / "deepseek-auth.json",
        Path.home() / "Applications" / "NonRoot.app" / "Contents" / "Resources" / "deepseek-api" / "deepseek-auth.json"
    ]
    return [p for p in paths if p.parent.exists()]

def get_bundled_auth_data() -> Dict[str, Any]:
    asset_file = Path(__file__).resolve().parent.parent / "assets" / "default_deepseek_auth.json"
    if asset_file.exists():
        try:
            with open(asset_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_BUNDLED_AUTH.copy()

def ensure_default_auth():
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    bundled = get_bundled_auth_data()

    if not CANONICAL_AUTH_FILE.exists() or CANONICAL_AUTH_FILE.stat().st_size < 10:
        try:
            with open(CANONICAL_AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(bundled, f, indent=2)
        except Exception:
            pass

    for p in get_auth_paths():
        if p != CANONICAL_AUTH_FILE and (not p.exists() or p.stat().st_size < 10):
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(CANONICAL_AUTH_FILE, p)
            except Exception:
                pass

def get_auth_info() -> Dict[str, Any]:
    ensure_default_auth()
    token = ""
    cookie = ""
    has_auth = False

    for p in [CANONICAL_AUTH_FILE] + get_auth_paths():
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    token = data.get("token", "")
                    cookie = data.get("cookie", "")
                    if token:
                        has_auth = True
                        break
            except Exception:
                pass

    backup_token = ""
    if BACKUP_AUTH_FILE.exists():
        try:
            with open(BACKUP_AUTH_FILE, "r", encoding="utf-8") as f:
                b_data = json.load(f)
                backup_token = b_data.get("token", "")
        except Exception:
            pass

    bundled_token = get_bundled_auth_data().get("token", "")
    is_default = (token == bundled_token) if token else False

    token_preview = (token[:10] + "..." + token[-6:]) if (token and len(token) > 16) else (token or "Не задан")
    backup_preview = (backup_token[:10] + "..." + backup_token[-6:]) if (backup_token and len(backup_token) > 16) else (backup_token or "Нет")

    return {
        "has_token": bool(token),
        "token_preview": token_preview,
        "token_length": len(token),
        "has_cookie": bool(cookie),
        "is_default": is_default,
        "has_backup": bool(backup_token),
        "backup_preview": backup_preview
    }

def backup_current_auth():
    if CANONICAL_AUTH_FILE.exists():
        try:
            shutil.copy2(CANONICAL_AUTH_FILE, BACKUP_AUTH_FILE)
        except Exception:
            pass

def sync_auth_data(data: Dict[str, Any]):
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    with open(CANONICAL_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    for p in get_auth_paths():
        if p != CANONICAL_AUTH_FILE:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(CANONICAL_AUTH_FILE, p)
            except Exception:
                pass

def restart_deepseek_proxy():
    try:
        from nonroot.engine.deepseek_client import auto_start_deepseek_proxy
        # kill existing node process on port 9655 if any
        subprocess.run(["pkill", "-f", "deepseek-api/server.js"], capture_output=True)
        auto_start_deepseek_proxy(9655)
    except Exception:
        pass

def revert_to_backup() -> Dict[str, Any]:
    if not BACKUP_AUTH_FILE.exists():
        return {"success": False, "error": "Резервная копия токена не найдена"}

    try:
        with open(BACKUP_AUTH_FILE, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        current_data = {}
        if CANONICAL_AUTH_FILE.exists():
            with open(CANONICAL_AUTH_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)

        if current_data:
            with open(BACKUP_AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)

        sync_auth_data(backup_data)
        restart_deepseek_proxy()
        return {"success": True, "message": "Предыдущий токен успешно восстановлен!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def restore_factory_default() -> Dict[str, Any]:
    try:
        backup_current_auth()
        bundled = get_bundled_auth_data()
        sync_auth_data(bundled)
        restart_deepseek_proxy()
        return {"success": True, "message": "Встроенный заводской токен успешно восстановлен!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_custom_token(raw_input: str) -> Dict[str, Any]:
    raw = (raw_input or "").strip()
    if not raw:
        return {"success": False, "error": "Введен пустой токен"}

    try:
        backup_current_auth()
        if raw.startswith("{"):
            data = json.loads(raw)
            if "token" not in data:
                return {"success": False, "error": "В JSON отсутствует поле token"}
        else:
            data = {
                "token": raw,
                "hif_dliq": "",
                "hif_leim": "",
                "cookie": "",
                "wasmUrl": "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm"
            }

        sync_auth_data(data)
        restart_deepseek_proxy()
        return {"success": True, "message": "Пользовательский токен успешно установлен!"}
    except Exception as e:
        return {"success": False, "error": f"Ошибка обработки токена: {e}"}

_browser_auth_thread = None
_browser_auth_status = {"running": False, "message": ""}

def launch_browser_auth() -> Dict[str, Any]:
    global _browser_auth_thread, _browser_auth_status
    if _browser_auth_status["running"]:
        return {"success": False, "error": "Авторизация в браузере уже запущена"}

    candidates = [
        Path.home() / ".nonroot" / "deepseek-api" / "scripts" / "deepseek_chrome_auth.js",
        Path(__file__).resolve().parent.parent.parent / "deepseek-api" / "scripts" / "deepseek_chrome_auth.js",
        Path.home() / "Applications" / "NonRoot.app" / "Contents" / "Resources" / "deepseek-api" / "scripts" / "deepseek_chrome_auth.js"
    ]

    script_path = None
    for cand in candidates:
        if cand.exists():
            script_path = cand
            break

    if not script_path:
        return {"success": False, "error": "Скрипт deepseek_chrome_auth.js не найден"}

    node_exec = None
    for n in ["/usr/local/bin/node", "/opt/homebrew/bin/node", "/usr/bin/node"]:
        if os.path.exists(n) and os.access(n, os.X_OK):
            node_exec = n
            break

    if not node_exec:
        return {"success": False, "error": "Node.js не найден в системе"}

    def _worker():
        global _browser_auth_status
        _browser_auth_status["running"] = True
        _browser_auth_status["message"] = "Браузер запущен. Авторизуйтесь на странице DeepSeek..."

        try:
            backup_current_auth()
            env = os.environ.copy()
            env["NON_INTERACTIVE"] = "1"
            env["DEEPSEEK_AUTH_PATH"] = str(CANONICAL_AUTH_FILE)

            p = subprocess.run(
                [node_exec, str(script_path)],
                cwd=str(script_path.parent.parent),
                env=env,
                capture_output=True,
                text=True,
                timeout=180
            )

            if p.returncode == 0:
                _browser_auth_status["message"] = "Авторизация успешна! Новый токен сохранен."
                # Sync new token to mirrors
                if CANONICAL_AUTH_FILE.exists():
                    try:
                        with open(CANONICAL_AUTH_FILE, "r", encoding="utf-8") as f:
                            sync_auth_data(json.load(f))
                    except Exception:
                        pass
                restart_deepseek_proxy()
            else:
                _browser_auth_status["message"] = f"Авторизация отменена или не завершена: {p.stderr[:200]}"
        except Exception as e:
            _browser_auth_status["message"] = f"Ошибка запуска браузера: {e}"
        finally:
            _browser_auth_status["running"] = False

    _browser_auth_thread = threading.Thread(target=_worker, daemon=True)
    _browser_auth_thread.start()

    return {"success": True, "message": "Браузер открывается для входа в DeepSeek..."}

def get_browser_auth_status() -> Dict[str, Any]:
    return dict(_browser_auth_status)
