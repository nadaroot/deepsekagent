"""
NonRoot Command Line Interface and Application Launcher.
"""

import os
import sys
import time
import argparse
import webbrowser
import subprocess
from pathlib import Path

from nonroot.config import config_manager
from nonroot.server import start_server

def launch_app_in_browser(url: str):
    """Launches Chrome/Chromium in borderless app mode if available, or default browser."""
    system = sys.platform
    launched = False

    if system == "darwin":
        chrome_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        ]
        for c in chrome_candidates:
            if os.path.exists(c):
                try:
                    subprocess.Popen([c, f"--app={url}", "--no-first-run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                    subprocess.Popen([c, f"--app={url}", "--no-first-run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    args = parser.parse_args()

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
    url = f"http://{host}:{actual_port}"

    print(r'''
  _  _           ___            _   
 | \| |___ _ _  | _ \___  ___ _| |_ 
 | .` / _ \ ' \ |   / _ \/ _ \  _|
 |_|\_\___/_||_||_|_\___/\___/\__|
 Autonomous AI Agent Engine · v1.0.0
    ''')
    print(f"[*] Workspace: {config_manager.get('workspace')}")
    print(f"[*] Model: {config_manager.get('model')}")
    print(f"[*] Server running at: {url}")

    if not args.no_browser:
        time.sleep(0.3)
        launch_app_in_browser(url)

    print("[+] NonRoot is active. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down NonRoot...")
        server.shutdown()

if __name__ == "__main__":
    main()

