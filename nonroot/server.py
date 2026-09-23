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
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict, Any, List

from nonroot.config import config_manager
from nonroot.engine.agent import AutonomousAgent

if getattr(sys, '_MEIPASS', None):
    UI_DIR = Path(sys._MEIPASS) / "nonroot" / "ui"
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    UI_DIR = Path(__file__).parent / "ui"
    ASSETS_DIR = Path(__file__).parent.parent / "assets"

class EventBroadcaster:
    def __init__(self):
        self.listeners: List[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        self.listeners.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        if q in self.listeners:
            self.listeners.remove(q)

    def broadcast(self, event: Dict[str, Any]):
        dead = []
        for q in self.listeners:
            try:
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

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
    on_event=broadcaster.broadcast
)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

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
        elif path == "/favicon.png":
            self._send_file(ASSETS_DIR / "favicon.png", "image/png")
        elif path == "/logo.png":
            self._send_file(ASSETS_DIR / "logo.png", "image/png")
        else:
            cand = UI_DIR / path.lstrip("/")
            if cand.exists():
                self._send_file(cand)
            else:
                self.send_error(404, "Not Found")

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
            if model:
                active_agent.model = model
            
            if not prompt:
                self._send_json({"error": "Prompt cannot be empty"}, status=400)
                return

            success, msg = active_agent.run_task(prompt=prompt, images=images)
            self._send_json({"success": success, "message": msg})
            return

        if path == "/api/stop":
            active_agent.stop()
            self._send_json({"success": True, "message": "Agent stopped"})
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
                workspace=config_manager.get("workspace")
            )
            self._send_json({"success": True, "config": config_manager.config})
            return

        self.send_error(404, "Not Found")

def start_server(port: int = 8765, host: str = "127.0.0.1") -> HTTPServer:
    server = ThreadedHTTPServer((host, port), NonRootHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server
