"""
Tool Implementations for NonRoot Autonomous Agent.
"""

import os
import sys
import re
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

class ToolExecutor:
    def __init__(self, workspace: Path, file_history: Optional[Any] = None):
        ws = Path(workspace).resolve()
        if ws == Path("/"):
            ws = (Path.home() / "Desktop").resolve()
        self.workspace = ws
        self.file_history = file_history

    def resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            if p.parent == Path("/"):
                # Writing directly to / on macOS is read-only APFS system snapshot
                safe_base = (Path.home() / "Desktop").resolve()
                return (safe_base / p.name).resolve()
            return p
        return (self.workspace / p).resolve()

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"tool_{tool_name}", None)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown tool: '{tool_name}'",
                "output": ""
            }
        try:
            return handler(**arguments)
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "output": ""
            }

    def tool_run_command(self, command: str, cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
        target_cwd = self.resolve_path(cwd) if cwd else self.workspace
        if not target_cwd.exists():
            return {"success": False, "error": f"Directory not found: {target_cwd}", "output": ""}

        shell_exe = "/bin/zsh" if sys.platform == "darwin" and os.path.exists("/bin/zsh") else ("/bin/bash" if os.path.exists("/bin/bash") else None)
        env = os.environ.copy()
        env["PAGER"] = "cat"
        env["TERM"] = "xterm-256color"

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=str(target_cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                executable=shell_exe,
                env=env,
                text=True,
                errors="replace"
            )
            out = (res.stdout or "") + (res.stderr or "")
            if len(out) > 50000:
                out = out[:50000] + "\n... [Output truncated after 50,000 chars]"

            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "output": out if out else "(Command executed with no output)"
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout} seconds", "output": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_read_file(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> Dict[str, Any]:
        p = self.resolve_path(path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {p}", "output": ""}
        if not p.is_file():
            return {"success": False, "error": f"Path is a directory, not a file: {p}", "output": ""}

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_idx = max(1, int(start_line))
            e_idx = min(total_lines, int(end_line)) if end_line else total_lines

            formatted = []
            for i in range(s_idx - 1, e_idx):
                formatted.append(f"{i + 1:4d}: {lines[i]}")

            return {
                "success": True,
                "path": str(p),
                "total_lines": total_lines,
                "showing_range": f"{s_idx}-{e_idx}",
                "output": "".join(formatted)
            }
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_write_file(self, path: str, content: str) -> Dict[str, Any]:
        p = self.resolve_path(path)
        try:
            if self.file_history:
                self.file_history.record_file_before_change(p)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "path": str(p),
                "bytes_written": len(content.encode("utf-8")),
                "output": f"Successfully wrote {len(content.splitlines())} lines to {p}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_edit_file(self, path: str, search_target: str, replacement: str) -> Dict[str, Any]:
        p = self.resolve_path(path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {p}", "output": ""}

        try:
            with open(p, "r", encoding="utf-8") as f:
                file_text = f.read()

            if search_target not in file_text:
                return {
                    "success": False,
                    "error": "Target string not found in file. Ensure exact match including indentation and whitespace.",
                    "output": ""
                }

            count = file_text.count(search_target)
            if count > 1:
                return {
                    "success": False,
                    "error": f"Target string found {count} times. Please provide a more specific unique context snippet.",
                    "output": ""
                }

            if self.file_history:
                self.file_history.record_file_before_change(p)

            new_text = file_text.replace(search_target, replacement, 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_text)

            return {
                "success": True,
                "path": str(p),
                "output": f"Successfully replaced target block in {p}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_list_dir(self, path: str = ".") -> Dict[str, Any]:
        p = self.resolve_path(path)
        if not p.exists():
            return {"success": False, "error": f"Directory not found: {p}", "output": ""}
        if not p.is_dir():
            return {"success": False, "error": f"Path is not a directory: {p}", "output": ""}

        try:
            items = []
            for item in sorted(p.iterdir()):
                rel = item.relative_to(self.workspace) if item.is_relative_to(self.workspace) else item.name
                if item.is_dir():
                    items.append(f"[DIR]  {rel}/")
                else:
                    size = item.stat().st_size
                    items.append(f"[FILE] {rel} ({size} bytes)")

            return {
                "success": True,
                "path": str(p),
                "count": len(items),
                "output": "\n".join(items) if items else "(Empty directory)"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_grep_search(self, query: str, path: str = ".", is_regex: bool = False) -> Dict[str, Any]:
        target_dir = self.resolve_path(path)
        if not target_dir.exists():
            return {"success": False, "error": f"Directory not found: {target_dir}", "output": ""}

        matches = []
        pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)

        try:
            for root, dirs, files in os.walk(str(target_dir)):
                dirs[:] = [d for d in dirs if not d.startswith((".", "node_modules", "dist", "build", "__pycache__", "venv"))]
                for file_name in files:
                    if file_name.startswith("."):
                        continue
                    file_path = Path(root) / file_name
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f):
                                if pattern.search(line):
                                    rel = file_path.relative_to(self.workspace) if file_path.is_relative_to(self.workspace) else file_path
                                    matches.append(f"{rel}:{idx+1}: {line.strip()}")
                                    if len(matches) >= 100:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= 100:
                        break
                if len(matches) >= 100:
                    break

            out = "\n".join(matches)
            if len(matches) >= 100:
                out += "\n... [Truncated at 100 matches]"
            return {
                "success": True,
                "match_count": len(matches),
                "output": out if matches else f"No matches found for '{query}'"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def tool_web_fetch(self, url: str) -> Dict[str, Any]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Strip HTML tags simply to clean markdown text
            clean = re.sub(r'<script[\s\S]*?</script>', '', raw, flags=re.IGNORECASE)
            clean = re.sub(r'<style[\s\S]*?</style>', '', clean, flags=re.IGNORECASE)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()

            if len(clean) > 20000:
                clean = clean[:20000] + "\n... [Content truncated after 20,000 chars]"

            return {
                "success": True,
                "url": url,
                "output": clean
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to fetch URL: {str(e)}", "output": ""}

    def tool_google_search(self, query: str) -> Dict[str, Any]:
        """Search Google via embedded browser with stealth, auto-consent, and fallback."""
        import urllib.parse
        import time
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded}&hl=ru"
        res = bm.navigate(search_url)
        if not res.get("success"):
            return {"success": False, "error": res.get("error", "Failed to navigate to Google")}

        time.sleep(0.5)

        # Check if Google returned a CAPTCHA or 'sorry' page
        cur_url = res.get("url", "").lower()
        if "sorry/index" in cur_url or "recaptcha" in cur_url:
            bm.solve_captcha()
            time.sleep(1.0)
            res = bm.take_screenshot()
            cur_url = bm.current_url.lower()

            # If still blocked by Google network CAPTCHA, fallback to Yandex
            if "sorry/index" in cur_url or "recaptcha" in cur_url:
                yandex_url = f"https://ya.ru/search/?text={encoded}"
                res = bm.navigate(yandex_url)
                time.sleep(0.5)

        dom_res = bm.get_dom_summary()
        elements = dom_res.get("elements", []) if dom_res.get("success") else []

        search_results = []
        for el in elements:
            txt = el.get("text", "").strip()
            if txt and len(txt) > 6 and el.get("tag") in ["h3", "a"]:
                search_results.append({
                    "title": txt[:120],
                    "tag": el.get("tag"),
                    "x": el.get("x"),
                    "y": el.get("y")
                })

        summary = f"Результаты поиска по запросу '{query}' (URL: {res.get('url')}):\nнайдено элементов: {len(search_results)}.\n\n"
        for i, item in enumerate(search_results[:10], 1):
            summary += f"{i}. [{item['tag']}] {item['title']} (клик: x={item['x']}, y={item['y']})\n"

        return {
            "success": True,
            "query": query,
            "url": res.get("url"),
            "title": res.get("title"),
            "screenshot": res.get("screenshot_b64"),
            "output": summary
        }

    def tool_browser_solve_captcha(self) -> Dict[str, Any]:
        """Detect and solve or click CAPTCHA checkbox (Cloudflare Turnstile, Google reCAPTCHA, hCaptcha) on current page."""
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.solve_captcha()
        if res.get("success"):
            return {
                "success": True,
                "output": f"Успешно обработан элемент капчи: {res.get('message')} (тип: {res.get('type')})",
                "screenshot": res.get("screenshot_b64"),
                "url": res.get("url")
            }
        return {
            "success": False,
            "error": res.get("message", "Элементы капчи не найдены или проверка не требует клика"),
            "screenshot": res.get("screenshot_b64"),
            "url": res.get("url")
        }

    def tool_web_search(self, query: str) -> Dict[str, Any]:
        return self.tool_google_search(query=query)

    def tool_browser_open(self, url: str) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.navigate(url)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Открыта страница в Chromium: {res.get('title')} ({res.get('url')})",
                "url": res.get("url"),
                "title": res.get("title"),
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Failed to navigate")}

    def tool_browser_click(self, x: Optional[int] = None, y: Optional[int] = None, selector: Optional[str] = None, description: str = "Клик") -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.click(x=x, y=y, selector=selector, description=description)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Выполнен клик: {res.get('clicked_at')} на странице '{res.get('title')}'",
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Click failed")}

    def tool_browser_type(self, text: str, selector: Optional[str] = None, press_enter: bool = False) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.type_text(text=text, selector=selector, press_enter=press_enter)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Введен текст: '{text}' (Enter: {press_enter})",
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Type failed")}

    def tool_browser_scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.scroll(direction=direction, amount=amount)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Прокрутка страницы {direction} на {amount}px",
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Scroll failed")}

    def tool_browser_screenshot(self, full_page: bool = False) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.take_screenshot(full_page=full_page)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Скриншот успешно получен для {res.get('title')} ({res.get('url')})",
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Screenshot failed")}

    def tool_browser_key(self, key: str) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.key_press(key=key)
        if res.get("success"):
            return {
                "success": True,
                "output": f"Нажата клавиша: {key}",
                "screenshot": res.get("screenshot_b64")
            }
        return {"success": False, "error": res.get("error", "Key press failed")}


    def tool_browser_inspect(self, selector: Optional[str] = None) -> Dict[str, Any]:
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        res = bm.get_dom_summary()
        if res.get("success"):
            dom = res.get("dom", {})
            return {
                "success": True,
                "output": f"DOM структура: {dom.get('title')} ({dom.get('url')}), элементов: {dom.get('element_count')}\n" +
                          json.dumps(dom.get("interactive", [])[:35], ensure_ascii=False, indent=2)
            }
        return {"success": False, "error": res.get("error", "Inspect failed")}

    def tool_browser_clone_site(self, url: Optional[str] = None, output_folder: str = "cloned_site") -> Dict[str, Any]:
        from nonroot.browser.cloner import SiteCloner
        from nonroot.browser.manager import get_browser_manager
        bm = get_browser_manager()
        target_url = url or bm.current_url
        if not target_url or target_url == "about:blank":
            return {"success": False, "error": "Не указан URL для клонирования"}

        cloner = SiteCloner(workspace=self.workspace, file_history=self.file_history)
        res = cloner.clone(url=target_url, output_folder=output_folder)
        if res.get("success"):
            return {
                "success": True,
                "output": res.get("message"),
                "target_dir": res.get("target_dir"),
                "index_html": res.get("index_html")
            }
        return {"success": False, "error": res.get("error", "Clone failed")}

    def tool_finish_task(self, summary: str) -> Dict[str, Any]:
        return {
            "success": True,
            "is_finish": True,
            "summary": summary,
            "output": f"Task accomplished: {summary}"
        }
