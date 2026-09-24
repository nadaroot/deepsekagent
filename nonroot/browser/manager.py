"""
NonRoot Chromium Browser Automation & Visual Controller.
Manages headless/headed Chromium via Playwright, streams live visual updates
and animated AI cursor coordinates to the NonRoot interface.
"""

import os
import sys
import time
import base64
import queue
import logging
import threading
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple

# Ensure user site packages are accessible for Playwright across Python versions
_paths_to_check = [
    Path.home() / "Library" / "Python" / f"{sys.version_info.major}.{sys.version_info.minor}" / "lib" / "python" / "site-packages",
    Path.home() / "Library" / "Python" / "3.9" / "lib" / "python" / "site-packages",
    Path.home() / ".local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
    Path("/usr/local/lib/python3.9/site-packages"),
    Path("/opt/homebrew/lib/python3.9/site-packages")
]
for _p in _paths_to_check:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserManager:
    """
    Dedicated thread-safe manager for Chromium browser instances.
    Maintains a dedicated background worker thread for Playwright event loop compatibility.
    """

    def __init__(self, on_event: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.on_event = on_event
        self.cmd_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.current_url = "about:blank"
        self.current_title = "Новая вкладка"
        self.last_screenshot_b64 = ""
        self.cursor_pos = {"x": 640, "y": 400}
        self.viewport_size = {"width": 1280, "height": 800}
        self._lock = threading.Lock()

        # Worker thread starts lazily upon first command

    def _start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="BrowserWorker")
        self.worker_thread.start()

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.on_event:
            try:
                payload = {"type": event_type, **data}
                self.on_event(payload)
            except Exception:
                pass

    def _emit_cursor(self, x: int, y: int, action: str = "Действие", ripple: bool = False):
        self.cursor_pos = {"x": x, "y": y}
        self._emit("browser_cursor", {
            "x": x,
            "y": y,
            "action": action,
            "label": "NonRoot AI",
            "ripple": ripple,
            "timestamp": time.time()
        })

    def _emit_state(self, is_loading: bool = False, error: Optional[str] = None):
        self._emit("browser_state", {
            "url": self.current_url,
            "title": self.current_title,
            "screenshot": self.last_screenshot_b64,
            "is_loading": is_loading,
            "error": error,
            "viewport": self.viewport_size,
            "cursor": self.cursor_pos,
            "timestamp": time.time()
        })



    def _auto_dismiss_consent(self, page):
        """Auto-clicks Google/Yandex cookie and privacy consent barriers."""
        try:
            for sel in [
                'button:has-text("Принять все")',
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                'button:has-text("Alle akzeptieren")',
                'button#L2AGLb',
                'form[action*="consent"] button',
                'div[role="none"] button:has-text("Принять")',
                'button:has-text("Понятно")',
                'button:has-text("Согласен")',
                'button:has-text("Got it")'
            ]:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=800):
                    loc.click(timeout=1000)
                    time.sleep(0.3)
                    break
        except Exception:
            pass

    def _solve_captcha_worker(self, page) -> Dict[str, Any]:
        """Detects and automatically interacts with Cloudflare Turnstile, reCAPTCHA v2, hCaptcha."""
        # 1. Cloudflare Turnstile
        for frame in [page] + page.frames:
            try:
                cf = frame.locator('input[type="checkbox"], div.ctp-checkbox-label, #challenge-stage input, .cf-turnstile-wrapper iframe').first
                if cf.is_visible(timeout=800):
                    box = cf.bounding_box()
                    if box:
                        cx, cy = int(box["x"] + box["width"]/2), int(box["y"] + box["height"]/2)
                        self._smooth_mouse_move(page, self.cursor_pos["x"], self.cursor_pos["y"], cx, cy)
                        time.sleep(0.2)
                        page.mouse.click(cx, cy)
                        time.sleep(1.5)
                        return {"success": True, "type": "turnstile", "message": "Нажат чекбокс Cloudflare Turnstile"}
            except Exception:
                pass

        # 2. Google reCAPTCHA v2
        for frame in page.frames:
            try:
                rc = frame.locator('.recaptcha-checkbox-border, #recaptcha-anchor, span[role="checkbox"]').first
                if rc.is_visible(timeout=800):
                    rc.click(timeout=1500)
                    time.sleep(1.5)
                    return {"success": True, "type": "recaptcha_v2", "message": "Нажат чекбокс Google reCAPTCHA"}
            except Exception:
                pass

        # 3. hCaptcha
        for frame in page.frames:
            try:
                hc = frame.locator('#checkbox, div[aria-label*="captcha"]').first
                if hc.is_visible(timeout=800):
                    hc.click(timeout=1500)
                    time.sleep(1.5)
                    return {"success": True, "type": "hcaptcha", "message": "Нажат чекбокс hCaptcha"}
            except Exception:
                pass

        # 4. Audio challenge fallback
        for frame in page.frames:
            try:
                ab = frame.locator('#recaptcha-audio-button, button[title*="звук"], button[title*="audio"]').first
                if ab.is_visible(timeout=800):
                    ab.click(timeout=1500)
                    time.sleep(1.0)
                    return {"success": True, "type": "audio_challenge", "message": "Активирована аудио-капча"}
            except Exception:
                pass

        # 5. Generic submit on sorry pages
        try:
            sb = page.locator('input[type="submit"], button[type="submit"]').first
            if sb.is_visible(timeout=800):
                sb.click(timeout=1500)
                time.sleep(1.0)
                return {"success": True, "type": "submit", "message": "Отправлена форма проверки"}
        except Exception:
            pass

        return {"success": False, "message": "Активные элементы капчи не обнаружены"}

    def _smooth_mouse_move(self, page, from_x: int, from_y: int, to_x: int, to_y: int, steps: int = 12):
        """Move mouse smoothly from one point to another with curved trajectory."""
        import math, random
        # Add slight randomness to path (bezier-like)
        mid_x = (from_x + to_x) / 2 + random.randint(-30, 30)
        mid_y = (from_y + to_y) / 2 + random.randint(-20, 20)
        for i in range(1, steps + 1):
            t = i / steps
            # Quadratic bezier: B(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
            x = int((1-t)**2 * from_x + 2*(1-t)*t * mid_x + t**2 * to_x)
            y = int((1-t)**2 * from_y + 2*(1-t)*t * mid_y + t**2 * to_y)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.01, 0.025))
        self._emit_cursor(x=to_x, y=to_y)

    def _ensure_chromium_installed(self) -> bool:
        """Verifies or auto-installs Chromium if needed."""
        cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
        if cache_dir.exists():
            for p in cache_dir.iterdir():
                if "chromium" in p.name:
                    return True
        try:
            p = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=180
            )
            return p.returncode == 0
        except Exception:
            return False

    def _worker_loop(self):
        """Dedicated thread executing all Playwright operations."""
        playwright_instance = None
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            if not PLAYWRIGHT_AVAILABLE:
                logging.warning("Playwright is not installed. Browser will operate in fallback mode.")
                self._emit_state(is_loading=False, error="Playwright не установлен")
                while self.is_running:
                    try:
                        cmd_data = self.cmd_queue.get(timeout=1.0)
                        if cmd_data is None:
                            break
                        cmd_name, args, reply_q = cmd_data
                        if reply_q:
                            reply_q.put({"success": False, "error": "Playwright не установлен в системе. Установите: pip install playwright && playwright install chromium"})
                    except queue.Empty:
                        pass
                return

            self._ensure_chromium_installed()

            p_ctx = sync_playwright()
            playwright_instance = p_ctx.start()

            # Launch Chromium with anti-bot evasion & stealth flags
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--hide-scrollbars",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--window-size=1280,800",
                "--lang=ru-RU,ru"
            ]

            browser = None
            if Path("/Applications/Google Chrome.app").exists() or shutil.which("google-chrome"):
                try:
                    browser = playwright_instance.chromium.launch(
                        channel="chrome",
                        headless=True,
                        args=launch_args,
                        ignore_default_args=["--enable-automation"]
                    )
                except Exception as c_err:
                    logging.warning(f"Failed to launch system Google Chrome, falling back: {c_err}")

            if browser is None:
                browser = playwright_instance.chromium.launch(
                    headless=True,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"]
                )
            context = browser.new_context(
                viewport=self.viewport_size,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                color_scheme="dark",
                device_scale_factor=1
            )

            # Deep stealth JavaScript spoofing to eliminate automation footprint
            stealth_js = """
            // 1. Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            try { delete navigator.__proto__.webdriver; } catch(e){}

            // 2. Mock chrome runtime object
            window.chrome = {
                app: { isInstalled: false },
                runtime: { OnInstalledReason: {}, OnRestartRequiredReason: {}, PlatformArch: {}, PlatformNaclArch: {}, PlatformOs: {}, RequestUpdateCheckStatus: {} },
                csi: function(){},
                loadTimes: function(){}
            };

            // 3. Mock languages
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'language', { get: () => 'ru-RU' });

            // 4. Mock plugins & mimeTypes
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ]
            });

            // 5. Mock permissions
            const origQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (origQuery) {
                window.navigator.permissions.query = (params) => (
                    params.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : origQuery(params)
                );
            }

            // 6. Mock WebGL vendor & renderer
            try {
                const getParam = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Google Inc. (Apple)';
                    if (parameter === 37446) return 'ANGLE (Apple, Apple M1, OpenGL 4.1)';
                    return getParam.apply(this, arguments);
                };
            } catch(e){}
            """
            context.add_init_script(stealth_js)
            page = context.new_page()

            while self.is_running:
                try:
                    action, args, result_queue = self.cmd_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                try:
                    res = None
                    if action == "navigate":
                        url = args["url"]
                        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://") and not url.startswith("data:") and not url.startswith("about:"):
                            url = "https://" + url

                        self._emit_state(is_loading=True)
                        self._emit_cursor(x=self.viewport_size["width"] // 2, y=60, action=f"Переход на {url}")

                        try:
                            page.goto(url, timeout=args.get("timeout_ms", 30000), wait_until="load")
                        except Exception:
                            page.goto(url, timeout=args.get("timeout_ms", 30000), wait_until="domcontentloaded")
                        time.sleep(1.0)
                        self._auto_dismiss_consent(page)

                        self.current_url = page.url
                        self.current_title = page.title() or url
                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")

                        self._emit_state(is_loading=False)
                        res = {
                            "success": True,
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot": self.last_screenshot_b64,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "click":
                        x = args.get("x")
                        y = args.get("y")
                        selector = args.get("selector")
                        desc = args.get("description", "Клик")

                        if selector:
                            try:
                                loc = page.locator(selector).first
                                loc.scroll_into_view_if_needed(timeout=3000)
                                box = loc.bounding_box()
                                if box:
                                    x = int(box["x"] + box["width"] / 2)
                                    y = int(box["y"] + box["height"] / 2)
                                else:
                                    loc.click(timeout=2000)
                            except Exception as loc_err:
                                logging.warning(f"Locator click failed for {selector}: {loc_err}")

                        if x is not None and y is not None:
                            self._emit_cursor(x=x, y=y, action=desc, ripple=True)
                            self._smooth_mouse_move(page, self.cursor_pos["x"], self.cursor_pos["y"], x, y)
                            page.mouse.click(x, y)
                            time.sleep(0.4)

                        self.current_url = page.url
                        self.current_title = page.title()
                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()

                        res = {
                            "success": True,
                            "clicked_at": {"x": x, "y": y},
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "type":
                        text = args.get("text", "")
                        selector = args.get("selector")
                        press_enter = args.get("press_enter", False)

                        if selector:
                            try:
                                loc = page.locator(selector).first
                                loc.scroll_into_view_if_needed(timeout=3000)
                                loc.click(timeout=2000)
                                box = loc.bounding_box()
                                if box:
                                    x = int(box["x"] + box["width"] / 2)
                                    y = int(box["y"] + box["height"] / 2)
                                    self._smooth_mouse_move(page, self.cursor_pos["x"], self.cursor_pos["y"], x, y)
                                    self._emit_cursor(x=x, y=y, action=f"Ввод: {text[:20]}...", ripple=True)
                            except Exception as loc_err:
                                logging.warning(f"Could not focus selector {selector}: {loc_err}")
                        else:
                            self._emit_cursor(x=self.cursor_pos["x"], y=self.cursor_pos["y"], action=f"Ввод: {text[:20]}...")

                        page.keyboard.type(text, delay=25)
                        if press_enter:
                            page.keyboard.press("Enter")
                            time.sleep(0.5)

                        self.current_url = page.url
                        self.current_title = page.title()
                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()

                        res = {
                            "success": True,
                            "typed": text,
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "scroll":
                        direction = args.get("direction", "down")
                        amount = args.get("amount", 500)
                        delta_y = amount if direction == "down" else -amount

                        self._emit_cursor(
                            x=self.cursor_pos["x"],
                            y=self.cursor_pos["y"],
                            action=f"Скролл {direction} ({amount}px)"
                        )
                        page.mouse.wheel(0, delta_y)
                        time.sleep(0.3)

                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()

                        res = {
                            "success": True,
                            "direction": direction,
                            "amount": amount,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "screenshot":
                        full_page = args.get("full_page", False)
                        shot = page.screenshot(type="jpeg", quality=85, full_page=full_page)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()
                        res = {
                            "success": True,
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "get_dom":
                        # Return semantic summary of headings, links, inputs, and interactive elements
                        summary = page.evaluate("""() => {
                            const elements = [];
                            document.querySelectorAll('h1, h2, h3, p, a, button, input, textarea, [role="button"]').forEach((el, idx) => {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    const text = (el.innerText || el.value || el.placeholder || '').trim();
                                    if (text) {
                                        elements.push({
                                            tag: el.tagName.toLowerCase(),
                                            id: el.id || null,
                                            class: el.className || null,
                                            text: text.slice(0, 100),
                                            x: Math.round(rect.x + rect.width / 2),
                                            y: Math.round(rect.y + rect.height / 2),
                                            width: Math.round(rect.width),
                                            height: Math.round(rect.height)
                                        });
                                    }
                                }
                            });
                            return {
                                title: document.title,
                                url: window.location.href,
                                element_count: elements.length,
                                interactive: elements.slice(0, 80)
                            };
                        }""")
                        res = {
                            "success": True,
                            "dom": summary,
                            "elements": summary.get("interactive", []),
                            "title": summary.get("title", ""),
                            "url": summary.get("url", "")
                        }

                    elif action == "get_html":
                        content = page.content()
                        res = {"success": True, "html": content}

                    elif action == "evaluate_js":
                        script = args.get("script", "")
                        js_arg = args.get("arg", None)
                        eval_res = page.evaluate(script, js_arg)
                        res = {"success": True, "result": eval_res}


                    elif action == "solve_captcha":
                        self._emit_cursor(x=self.cursor_pos["x"], y=self.cursor_pos["y"], action="Обход капчи...")
                        solve_info = self._solve_captcha_worker(page)
                        time.sleep(1.0)
                        self._auto_dismiss_consent(page)
                        self.current_url = page.url
                        self.current_title = page.title() or ""
                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()
                        res = {
                            "success": solve_info.get("success", False),
                            "message": solve_info.get("message", ""),
                            "type": solve_info.get("type", "unknown"),
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "key_press":
                        key = args.get("key", "Enter")
                        self._emit_cursor(x=self.cursor_pos["x"], y=self.cursor_pos["y"], action=f"Клавиша: {key}")
                        # Handle combo keys like Control+a
                        if "+" in key:
                            parts = key.split("+")
                            modifiers = parts[:-1]
                            main_key = parts[-1]
                            for mod in modifiers:
                                page.keyboard.down(mod)
                            page.keyboard.press(main_key)
                            for mod in reversed(modifiers):
                                page.keyboard.up(mod)
                        else:
                            page.keyboard.press(key)
                        time.sleep(0.25)

                        self.current_url = page.url
                        self.current_title = page.title()
                        shot = page.screenshot(type="jpeg", quality=80)
                        self.last_screenshot_b64 = "data:image/jpeg;base64," + base64.b64encode(shot).decode("utf-8")
                        self._emit_state()
                        res = {
                            "success": True,
                            "key": key,
                            "url": self.current_url,
                            "title": self.current_title,
                            "screenshot_b64": self.last_screenshot_b64
                        }

                    elif action == "close":
                        self.is_running = False
                        res = {"success": True}

                    result_queue.put(res)

                except Exception as e:
                    err_msg = str(e)
                    self._emit_state(is_loading=False, error=err_msg)
                    result_queue.put({"success": False, "error": err_msg})

        except Exception as outer_e:
            logging.error(f"Fatal error in Playwright browser worker: {outer_e}")
        finally:
            try:
                if page:
                    page.close()
                if context:
                    context.close()
                if browser:
                    browser.close()
                if playwright_instance:
                    playwright_instance.stop()
            except Exception:
                pass

    def _dispatch_command(self, action: str, args: Dict[str, Any], timeout: float = 35.0) -> Dict[str, Any]:
        """Dispatches an action to the worker thread and waits for the result."""
        self._start_worker()
        res_q = queue.Queue()
        self.cmd_queue.put((action, args, res_q))
        try:
            return res_q.get(timeout=timeout)
        except queue.Empty:
            return {"success": False, "error": f"Browser action '{action}' timed out after {timeout}s"}

    def navigate(self, url: str) -> Dict[str, Any]:
        return self._dispatch_command("navigate", {"url": url}, timeout=35.0)

    def click(self, x: Optional[int] = None, y: Optional[int] = None, selector: Optional[str] = None, description: str = "Клик") -> Dict[str, Any]:
        return self._dispatch_command("click", {"x": x, "y": y, "selector": selector, "description": description}, timeout=20.0)

    def type_text(self, text: str, selector: Optional[str] = None, press_enter: bool = False) -> Dict[str, Any]:
        return self._dispatch_command("type", {"text": text, "selector": selector, "press_enter": press_enter}, timeout=20.0)

    def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        return self._dispatch_command("scroll", {"direction": direction, "amount": amount}, timeout=15.0)

    def take_screenshot(self, full_page: bool = False) -> Dict[str, Any]:
        return self._dispatch_command("screenshot", {"full_page": full_page}, timeout=20.0)


    def solve_captcha(self) -> Dict[str, Any]:
        return self._dispatch_command("solve_captcha", {}, timeout=25.0)

    def key_press(self, key: str) -> Dict[str, Any]:
        return self._dispatch_command("key_press", {"key": key}, timeout=15.0)

    def get_dom_summary(self) -> Dict[str, Any]:
        return self._dispatch_command("get_dom", {}, timeout=15.0)

    def get_html_content(self) -> Dict[str, Any]:
        return self._dispatch_command("get_html", {}, timeout=15.0)

    def evaluate_js(self, script: str, arg: Any = None, timeout: float = 25.0) -> Dict[str, Any]:
        return self._dispatch_command("evaluate_js", {"script": script, "arg": arg}, timeout=timeout)

    def get_state(self) -> Dict[str, Any]:
        return {
            "url": self.current_url,
            "title": self.current_title,
            "screenshot": self.last_screenshot_b64,
            "cursor": self.cursor_pos,
            "viewport": self.viewport_size
        }

    def close(self):
        self._dispatch_command("close", {})


# Global browser manager singleton
_global_browser_manager: Optional[BrowserManager] = None

def get_browser_manager(on_event: Optional[Callable[[Dict[str, Any]], None]] = None) -> BrowserManager:
    global _global_browser_manager
    if _global_browser_manager is None:
        _global_browser_manager = BrowserManager(on_event=on_event)
    elif on_event and _global_browser_manager.on_event is None:
        _global_browser_manager.on_event = on_event
    return _global_browser_manager
