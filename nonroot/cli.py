"""
NonRoot Command Line Interface and Application Launcher.
"""

import os
import sys
import time
import json
import argparse
import webbrowser
import subprocess
import threading
import logging
from pathlib import Path


from nonroot.config import config_manager
from nonroot.server import start_server

# Setup nonroot logging
try:
    log_dir = Path.home() / ".nonroot"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "nonroot.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
except Exception:
    log_dir = Path("/tmp")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
        sys.stdout.flush()
    except Exception:
        pass
    logging.info(" ".join(str(a) for a in args))

def check_existing_instance() -> bool:
    """Checks if another NonRoot server instance is already running and brings it to front."""
    state_file = log_dir / "active_server.json"
    if not state_file.exists():
        return False
    try:
        data = json.loads(state_file.read_text())
        port = data.get("port")
        if not port:
            return False
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", method="GET")
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                url = f"http://127.0.0.1:{port}"
                safe_print(f"[*] NonRoot is already active at {url}. Opening window...")
                launch_app_in_browser(url)
                return True
    except Exception:
        pass
    return False

def record_instance(port: int):
    state_file = log_dir / "active_server.json"
    try:
        state_file.write_text(json.dumps({"port": port, "pid": os.getpid()}))
    except Exception:
        pass

def launch_app_in_browser(url: str):
    """Launches Chrome/Chromium in standalone app window mode or default system browser."""
    system = sys.platform
    launched = False

    if system == "darwin":
        browser_candidates = [
            "/Applications/Google Chrome.app",
            os.path.expanduser("~/Applications/Google Chrome.app"),
            "/Applications/Brave Browser.app",
            "/Applications/Microsoft Edge.app",
            "/Applications/Chromium.app"
        ]
        for app_path in browser_candidates:
            if os.path.exists(app_path):
                try:
                    subprocess.Popen([
                        "open", "-a", app_path,
                        "--args",
                        f"--app={url}"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    launched = True
                    break
                except Exception:
                    pass

        if not launched:
            try:
                subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                launched = True
            except Exception:
                pass
    elif system == "win32":
        env_prog = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        env_prog86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        env_local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        
        candidates = [
            os.path.join(env_prog, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(env_prog86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(env_local, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(env_prog86, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(env_prog, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(env_local, "Programs\\Opera\\launcher.exe"),
            os.path.join(env_local, "BraveSoftware\\Brave-Browser\\Application\\brave.exe")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    subprocess.Popen([
                        c,
                        f"--app={url}"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    launched = True
                    break
                except Exception:
                    pass

    if not launched:
        try:
            webbrowser.open(url)
        except Exception:
            pass

def main():
    try:
        parser = argparse.ArgumentParser(
            prog="nonroot",
            description="NonRoot — Autonomous AI Agent (OpenCode 1:1 Aesthetic)"
        )
        parser.add_argument("--port", type=int, default=8765, help="Port to bind web server (default: 8765)")
        parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
        parser.add_argument("--workspace", type=str, default=None, help="Root workspace directory")
        parser.add_argument("--model", type=str, default=None, help="DeepSeek model (deepseek-chat, deepseek-reasoner)")
        parser.add_argument("--api-url", type=str, default=None, help="DeepSeek API Base URL")
        parser.add_argument("--api-key", type=str, default=None, help="API Key")
        parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
        parser.add_argument("--auto-accept", action="store_true", help="Enable auto-accept tool execution")
        parser.add_argument("--force", action="store_true", help="Force launch new server even if one exists")

        args = parser.parse_args()

        if not args.force and check_existing_instance():
            return

        # Update config from CLI flags
        updates = {}
        if args.workspace:
            updates["workspace"] = str(Path(args.workspace).resolve())
        if args.model:
            updates["model"] = args.model
        if args.api_url:
            updates["api_base_url"] = args.api_url
        if args.api_key:
            updates["api_key"] = args.api_key
        if args.auto_accept:
            updates["auto_accept_tools"] = True

        if updates:
            config_manager.update(updates)

        port = args.port or config_manager.get("port", 8765)
        host = args.host

        server, actual_port = start_server(port=port, host=host)
        record_instance(actual_port)
        url = f"http://{host}:{actual_port}"

        safe_print(r'''
  _  _           ___            _   
 | \| |___ _ _  | _ \___  ___ _| |_ 
 | .` / _ \ ' \ |   / _ \/ _ \  _|
 |_|\_\___/_||_||_|_\___/\___/\__|
 Autonomous AI Agent Engine · v1.0.0
        ''')
        safe_print(f"[*] Workspace: {config_manager.get('workspace')}")
        safe_print(f"[*] Model: {config_manager.get('model')}")
        safe_print(f"[*] Server running at: {url}")

        if not args.no_browser:
            time.sleep(0.3)
            launch_app_in_browser(url)

        safe_print("[+] NonRoot is active. Press Ctrl+C to stop.\n")
        
        shutdown_event = threading.Event()
        try:
            shutdown_event.wait()
        except (KeyboardInterrupt, SystemExit):
            safe_print("\n[*] Shutting down NonRoot...")
            server.shutdown()

    except Exception as e:
        logging.exception("Fatal error in NonRoot main()")
        safe_print(f"[-] Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()



