"""
Embedded Web Server and REST/SSE API for NonRoot Agent.
Zero external server dependencies (uses standard library http.server and threading).
"""

import os
import sys
import json
import time
import queue
import threading
import mimetypes
import subprocess
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict, Any, List

from nonroot.config import config_manager
from nonroot.engine.agent import AutonomousAgent
from nonroot.auth import (
    ensure_default_auth,
    get_auth_info,
    get_browser_auth_status,
    launch_browser_auth,
    revert_to_backup,
    restore_factory_default,
    save_custom_token
)

try:
    ensure_default_auth()
except Exception:
    pass

if getattr(sys, '_MEIPASS', None):
    UI_DIR = Path(sys._MEIPASS) / "nonroot" / "ui"
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    UI_DIR = Path(__file__).parent / "ui"
    ASSETS_DIR = Path(__file__).parent.parent / "assets"

def pick_folder_native(initial_dir: Optional[str] = None) -> Optional[str]:
    """Opens a native operating system folder selection dialog."""
    system = sys.platform

    if system == "darwin":
        script = 'POSIX path of (choose folder with prompt "Выберите рабочую папку проекта NonRoot:")'
        try:
            p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                res = p.stdout.strip()
                if res:
                    return res
        except Exception:
            pass

    elif system == "win32":
        ps_script = '''
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.Description = "Выберите рабочую папку для NonRoot"
        $f.ShowNewFolderButton = $true
        if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            Write-Output $f.SelectedPath
        }
        '''
        try:
            p = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=60)
            if p.returncode == 0:
                res = p.stdout.strip()
                if res:
                    return res
        except Exception:
            pass

    elif system.startswith("linux"):
        for cmd in [
            ["zenity", "--file-selection", "--directory", "--title=Выберите рабочую папку для NonRoot"],
            ["kdialog", "--getexistingdirectory", "--title", "Выберите рабочую папку для NonRoot"]
        ]:
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if p.returncode == 0:
                    res = p.stdout.strip()
                    if res:
                        return res
            except Exception:
                continue

    # NOTE: Tkinter is NOT used as fallback on macOS — it attempts to create a second
    # NSApplication from a background thread inside our Cocoa app, causing SIGABRT.
    if system != "darwin":
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(title="Выберите рабочую папку для NonRoot", initialdir=initial_dir)
            root.destroy()
            if selected:
                return selected
        except Exception:
            pass

    return None

class EventBroadcaster:
    def __init__(self):
        self._lock = threading.Lock()
        self.listeners: List[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=200)
        with self._lock:
            self.listeners.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def broadcast(self, event: Dict[str, Any]):
        with self._lock:
            listeners = list(self.listeners)

        dead = []
        for q in listeners:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    dead.append(q)
            except Exception:
                dead.append(q)

        if dead:
            with self._lock:
                for q in dead:
                    if q in self.listeners:
                        self.listeners.remove(q)

broadcaster = EventBroadcaster()

# Global Autonomous Agent instance
active_agent = AutonomousAgent(
    workspace=Path(config_manager.get("workspace")),
    api_base_url=config_manager.get("api_base_url"),
    api_key=config_manager.get("api_key"),
    model=config_manager.get("model"),
    auto_accept=config_manager.get("auto_accept_tools"),
    max_steps=config_manager.get("max_steps"),
    system_prompt=config_manager.get("system_prompt", ""),
    custom_providers=config_manager.get("custom_providers", []),
    on_event=broadcaster.broadcast
)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class NonRootHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP request logs in console
        pass

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, mime_type: Optional[str] = None):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File Not Found")
            return
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. SSE Events Stream
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = broadcaster.subscribe()
            try:
                # Send initial ping & state
                init_msg = json.dumps({
                    "type": "init",
                    "is_running": active_agent.is_running,
                    "model": active_agent.model,
                    "auto_accept": active_agent.auto_accept,
                    "workspace": str(active_agent.workspace),
                    "subagents": active_agent.subagent_manager.list_all()
                })
                self.wfile.write(f"data: {init_msg}\n\n".encode("utf-8"))
                self.wfile.flush()

                while True:
                    try:
                        event = q.get(timeout=20)
                        data_str = json.dumps(event, ensure_ascii=False)
                        self.wfile.write(f"data: {data_str}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive ping
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                broadcaster.unsubscribe(q)
            return

        # 2. API Endpoints
        if path == "/api/settings":
            self._send_json(config_manager.config)
            return

        if path == "/api/auth/status":
            self._send_json(get_auth_info())
            return

        if path == "/api/auth/browser/status":
            self._send_json(get_browser_auth_status())
            return

        if path == "/api/update/check":
            try:
                from nonroot.updater import check_for_updates
                self._send_json(check_for_updates())
            except Exception as e:
                self._send_json({"has_update": False, "error": str(e)})
            return

        if path == "/api/models":
            models = active_agent.client.list_models()
            self._send_json({"models": models})
            return

        if path == "/api/subagents":
            self._send_json({"subagents": active_agent.subagent_manager.list_all()})
            return

        if path == "/api/workspace":
            try:
                files = []
                for p in sorted(active_agent.workspace.iterdir()):
                    if not p.name.startswith("."):
                        files.append({"name": p.name, "is_dir": p.is_dir()})
                self._send_json({"workspace": str(active_agent.workspace), "files": files})
            except Exception as e:
                self._send_json({"workspace": str(active_agent.workspace), "files": [], "error": str(e)})
            return

        # 3. Static Assets & UI
        if path in ["/", "/index.html"]:
            self._send_file(UI_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/style.css":
            self._send_file(UI_DIR / "style.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_file(UI_DIR / "app.js", "application/javascript; charset=utf-8")
        elif path in ["/favicon.ico", "/favicon.png", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"]:
            fav = ASSETS_DIR / "favicon.png"
            if not fav.exists():
                fav = UI_DIR / "favicon.png"
            self._send_file(fav, "image/png")
        elif path == "/logo.png":
            logo = ASSETS_DIR / "logo.png"
            if not logo.exists():
                logo = UI_DIR / "logo.png"
            self._send_file(logo, "image/png")
        elif path == "/icon.svg":
            svg = ASSETS_DIR / "icon.svg"
            if not svg.exists():
                svg = UI_DIR / "icon.svg"
            self._send_file(svg, "image/svg+xml")
        elif path == "/version.json":
            ver_file = ASSETS_DIR / "version.json"
            if ver_file.exists():
                self._send_file(ver_file, "application/json; charset=utf-8")
            else:
                self._send_json({"version": "1.1.0", "commit": "unknown"})
        else:
            cand = (UI_DIR / path.lstrip("/")).resolve()
            try:
                cand.relative_to(UI_DIR.resolve())
                if cand.exists() and cand.is_file():
                    self._send_file(cand)
                else:
                    self.send_error(404, "Not Found")
            except (ValueError, Exception):
                self.send_error(403, "Forbidden")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            body = json.loads(body_raw)
        except Exception:
            body = {}

        if path == "/api/chat":
            prompt = body.get("prompt", "").strip()
            images = body.get("images", [])
            model = body.get("model")
            workspace = body.get("workspace")
            if model:
                active_agent.model = model
            if workspace:
                active_agent.update_settings(workspace=workspace)
                config_manager.set("workspace", str(active_agent.workspace))
            
            if not prompt:
                self._send_json({"error": "Prompt cannot be empty"}, status=400)
                return

            success, msg = active_agent.run_task(prompt=prompt, images=images)
            self._send_json({"success": success, "message": msg, "workspace": str(active_agent.workspace)})
            return

        if path == "/api/stop":
            active_agent.stop()
            self._send_json({"success": True, "message": "Agent stopped"})
            return

        if path == "/api/workspace/set":
            new_ws = body.get("workspace", "/").strip()
            if not new_ws:
                new_ws = "/"
            ws_path = Path(new_ws).resolve()
            active_agent.update_settings(workspace=str(ws_path))
            config_manager.set("workspace", str(ws_path))
            broadcaster.broadcast({
                "type": "workspace_updated",
                "workspace": str(ws_path)
            })
            self._send_json({"success": True, "workspace": str(ws_path)})
            return

        if path == "/api/workspace/pick":
            picked = pick_folder_native()
            if picked:
                ws_path = Path(picked).resolve()
                active_agent.update_settings(workspace=str(ws_path))
                config_manager.set("workspace", str(ws_path))
                broadcaster.broadcast({
                    "type": "workspace_updated",
                    "workspace": str(ws_path)
                })
                self._send_json({"success": True, "workspace": str(ws_path)})
            else:
                self._send_json({"success": False, "cancelled": True, "workspace": str(active_agent.workspace)})
            return

        if path == "/api/tools/confirm":
            approved = bool(body.get("approved", True))
            active_agent.confirm_tool(approved=approved)
            self._send_json({"success": True, "approved": approved})
            return

        if path == "/api/subagents/kill":
            sub_id = body.get("id")
            if sub_id:
                killed = active_agent.subagent_manager.kill(sub_id)
                self._send_json({"success": killed})
            else:
                active_agent.subagent_manager.kill_all()
                self._send_json({"success": True})
            return

        if path == "/api/settings":
            config_manager.update(body)
            active_agent.update_settings(
                api_base_url=config_manager.get("api_base_url"),
                api_key=config_manager.get("api_key"),
                model=config_manager.get("model"),
                auto_accept=config_manager.get("auto_accept_tools"),
                max_steps=config_manager.get("max_steps"),
                workspace=config_manager.get("workspace"),
                custom_providers=config_manager.get("custom_providers", [])
            )
            self._send_json({"success": True, "config": config_manager.config})
            return

        if path == "/api/update/apply":
            try:
                from nonroot.updater import apply_update
                res = apply_update()
                self._send_json(res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            return

        if path == "/api/auth/browser":
            res = launch_browser_auth()
            self._send_json(res)
            return

        if path == "/api/auth/revert":
            res = revert_to_backup()
            self._send_json(res)
            return

        if path == "/api/auth/restore-default":
            res = restore_factory_default()
            self._send_json(res)
            return

        if path == "/api/auth/custom":
            raw_token = body.get("token", "")
            res = save_custom_token(raw_token)
            self._send_json(res)
            return

        self.send_error(404, "Not Found")

def start_server(port: int = 8765, host: str = "127.0.0.1"):
    server = None
    actual_port = port
    for offset in range(20):
        try:
            actual_port = port + offset
            server = ThreadedHTTPServer((host, actual_port), NonRootHTTPHandler)
            break
        except OSError as e:
            if offset == 19:
                raise e
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server, actual_port

