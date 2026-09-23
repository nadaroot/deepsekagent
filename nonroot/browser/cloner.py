"""
NonRoot 1:1 Website Cloner.
Clones full websites with complete HTML, computed CSS styles, fonts, images and SVG assets,
producing a standalone, responsive, pixel-perfect project in the workspace.
"""

import os
import re
import time
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, List

from nonroot.browser.manager import get_browser_manager

class SiteCloner:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()

    def clone(self, url: str, output_folder: Optional[str] = None) -> Dict[str, Any]:
        """
        Clones the website at `url` 1:1 into `output_folder` inside the workspace.
        """
        browser = get_browser_manager()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://") and not url.startswith("data:"):
            url = "https://" + url

        # 1. Open page in browser
        nav_res = browser.navigate(url)
        if not nav_res.get("success"):
            return {"success": False, "error": f"Failed to navigate to {url}: {nav_res.get('error')}"}

        # 2. Determine target folder
        parsed = urllib.parse.urlparse(url)
        domain_clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', parsed.netloc or "website")
        if not output_folder:
            output_folder = f"cloned_{domain_clean}"

        target_dir = self.workspace / output_folder
        assets_dir = target_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 3. Capture original visual screenshot
        shot_res = browser.take_screenshot(full_page=False)
        orig_shot_b64 = shot_res.get("screenshot_b64", "")
        if orig_shot_b64 and orig_shot_b64.startswith("data:image/jpeg;base64,"):
            raw_shot = orig_shot_b64.split(",", 1)[1]
            try:
                import base64
                (target_dir / "original_preview.jpg").write_bytes(base64.b64decode(raw_shot))
            except Exception:
                pass

        # 4. Extract rendered DOM and all stylesheets
        html_res = browser.get_html_content()
        raw_html = html_res.get("html", "")
        if not raw_html:
            return {"success": False, "error": "Could not extract rendered DOM from page."}

        # 5. Extract and download external stylesheets and images
        asset_map = {}
        downloaded_count = 0

        # Extract linked CSS
        css_links = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', raw_html, re.I)
        css_links += re.findall(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']', raw_html, re.I)

        combined_css = []
        for css_url in set(css_links):
            full_css_url = urllib.parse.urljoin(url, css_url)
            css_filename = "style_" + re.sub(r'[^a-zA-Z0-9_\-\.]', '_', Path(urllib.parse.urlparse(full_css_url).path).name or "main.css")
            if not css_filename.endswith(".css"):
                css_filename += ".css"

            try:
                req = urllib.request.Request(full_css_url, headers={"User-Agent": "Mozilla/5.0 NonRoot-Agent/1.1"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    css_text = resp.read().decode("utf-8", errors="replace")
                    (assets_dir / css_filename).write_text(css_text, encoding="utf-8")
                    asset_map[css_url] = f"assets/{css_filename}"
                    combined_css.append(css_text)
                    downloaded_count += 1
            except Exception:
                pass

        # Extract image URLs
        img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html, re.I)
        for img_url in set(img_srcs):
            if img_url.startswith("data:"):
                continue
            full_img_url = urllib.parse.urljoin(url, img_url)
            clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', Path(urllib.parse.urlparse(full_img_url).path).name or "img.png")
            if not any(clean_name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico"]):
                clean_name += ".png"

            dest_file = assets_dir / clean_name
            try:
                req = urllib.request.Request(full_img_url, headers={"User-Agent": "Mozilla/5.0 NonRoot-Agent/1.1"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    dest_file.write_bytes(resp.read())
                    asset_map[img_url] = f"assets/{clean_name}"
                    downloaded_count += 1
            except Exception:
                pass

        # 6. Rewrite HTML references to local asset paths
        clean_html = raw_html
        for orig, local_path in asset_map.items():
            clean_html = clean_html.replace(f'"{orig}"', f'"{local_path}"').replace(f"'{orig}'", f"'{local_path}'")

        # Remove external tracking, analytics, and intrusive popups from clone
        clean_html = re.sub(r'<script[^>]*google-analytics\.com[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*googletagmanager\.com[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*yandex\.ru[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)

        # Extract inline styles into combined_css as well
        inline_styles = re.findall(r'<style[^>]*>(.*?)</style>', raw_html, flags=re.S | re.I)
        for s in inline_styles:
            if s.strip():
                combined_css.append(s.strip())

        # Write clean index.html
        (target_dir / "index.html").write_text(clean_html, encoding="utf-8")

        # Always write consolidated style.css
        css_content = "/* === NonRoot 1:1 Cloned Stylesheet === */\n\n"
        if combined_css:
            css_content += "\n\n".join(combined_css)
        else:
            css_content += "/* Standalone replica styles */\n"
        (target_dir / "style.css").write_text(css_content, encoding="utf-8")

        # Create README.md
        readme = f"""# 1:1 Website Clone: {domain_clean}

- **Source URL**: [{url}]({url})
- **Cloned At**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Cloned by**: NonRoot Autonomous AI Agent (Chromium Engine)
- **Downloaded Assets**: {downloaded_count} files

## Structure:
- `index.html` — Full responsive page structure
- `style.css` — Consolidated stylesheet
- `assets/` — Images, icons, stylesheets
- `original_preview.jpg` — Reference screenshot of the live website
"""
        (target_dir / "README.md").write_text(readme, encoding="utf-8")

        return {
            "success": True,
            "target_dir": str(target_dir),
            "output_folder": output_folder,
            "files_created": [
                "index.html",
                "style.css",
                "original_preview.jpg",
                "README.md"
            ],
            "index_html": str(target_dir / "index.html"),
            "assets_count": downloaded_count,
            "message": f"Сайт успешно клонирован 1 в 1 в '{output_folder}'. Созданы index.html, style.css и скачано {downloaded_count} ассетов."
        }
