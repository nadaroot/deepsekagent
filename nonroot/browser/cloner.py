"""
NonRoot 1:1 Website Cloner.
Clones full websites with complete HTML, computed CSS styles, fonts, images and SVG assets,
producing a standalone, responsive, pixel-perfect project in the workspace.
"""

import os
import re
import time
import json
import base64
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, List

from nonroot.browser.manager import get_browser_manager

REAL_CHROME_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

JS_EXTRACT_STYLES_AND_ASSETS = """
() => {
    // 1. Computed base styles of html and body
    const rootEl = document.documentElement;
    const bodyEl = document.body || document.documentElement;
    const rootComp = window.getComputedStyle(rootEl);
    const bodyComp = window.getComputedStyle(bodyEl);

    const baseStyles = {
        htmlBg: rootComp.backgroundColor || "",
        htmlColor: rootComp.color || "",
        htmlFont: rootComp.fontFamily || "",
        bodyBg: bodyComp.backgroundColor || "",
        bodyColor: bodyComp.color || "",
        bodyFont: bodyComp.fontFamily || "",
        bodyLineHeight: bodyComp.lineHeight || "",
        bodyMargin: bodyComp.margin || "",
        bodyPadding: bodyComp.padding || ""
    };

    // 2. CSS variables from :root, html, and body
    const cssVars = {};
    try {
        for (let i = 0; i < document.styleSheets.length; i++) {
            try {
                const sheet = document.styleSheets[i];
                const rules = sheet.cssRules || sheet.rules;
                if (rules) {
                    for (let j = 0; j < rules.length; j++) {
                        const r = rules[j];
                        if (r.selectorText && (r.selectorText.includes(':root') || r.selectorText === 'html' || r.selectorText === 'body')) {
                            if (r.style) {
                                for (let k = 0; k < r.style.length; k++) {
                                    const prop = r.style[k];
                                    if (prop && prop.startsWith('--')) {
                                        cssVars[prop] = r.style.getPropertyValue(prop).trim();
                                    }
                                }
                            }
                        }
                    }
                }
            } catch (_) {}
        }
    } catch (_) {}

    // 3. Extracted stylesheets & external links
    const extractedSheets = [];
    const externalHrefs = [];
    for (let i = 0; i < document.styleSheets.length; i++) {
        try {
            const sheet = document.styleSheets[i];
            let sheetText = '';
            try {
                const rules = sheet.cssRules || sheet.rules;
                if (rules) {
                    for (let j = 0; j < rules.length; j++) {
                        sheetText += rules[j].cssText + '\\n';
                    }
                }
            } catch (e) {
                if (sheet.href) externalHrefs.push(sheet.href);
            }
            if (sheetText.trim()) {
                extractedSheets.push({ href: sheet.href || null, css: sheetText });
            } else if (sheet.href) {
                externalHrefs.push(sheet.href);
            }
        } catch (_) {}
    }

    // 4. Inline styles from <style> tags
    const inlineStyles = [];
    document.querySelectorAll('style').forEach(st => {
        if (st.textContent && st.textContent.trim()) {
            inlineStyles.push(st.textContent.trim());
        }
    });

    // 5. Images and background images
    const images = [];
    document.querySelectorAll('img').forEach(img => {
        const src = img.currentSrc || img.getAttribute('src');
        if (src && !src.startsWith('data:')) images.push(src);
    });
    document.querySelectorAll('picture source').forEach(source => {
        const srcset = source.getAttribute('srcset');
        if (srcset) {
            const firstUrl = srcset.split(',')[0].trim().split(' ')[0];
            if (firstUrl && !firstUrl.startsWith('data:')) images.push(firstUrl);
        }
    });

    // Extract background images from elements
    const bgImages = [];
    try {
        const allEls = document.querySelectorAll('*');
        const limit = Math.min(allEls.length, 600);
        for (let i = 0; i < limit; i++) {
            const bg = window.getComputedStyle(allEls[i]).backgroundImage;
            if (bg && bg !== 'none' && bg.includes('url(')) {
                const m = bg.match(/url\\(['"]?(.*?)['"]?\\)/);
                if (m && m[1] && !m[1].startsWith('data:')) {
                    bgImages.push(m[1]);
                }
            }
        }
    } catch (_) {}

    // 6. External fonts & stylesheets (<link rel="stylesheet">)
    const fontLinks = [];
    document.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
        const href = l.getAttribute('href');
        if (href && (href.includes('font') || href.includes('typekit') || href.includes('gstatic'))) {
            fontLinks.push(href);
        }
    });

    return {
        baseStyles: baseStyles,
        cssVars: cssVars,
        extractedSheets: extractedSheets,
        externalHrefs: [...new Set(externalHrefs)],
        inlineStyles: inlineStyles,
        images: [...new Set(images)],
        bgImages: [...new Set(bgImages)],
        fontLinks: [...new Set(fontLinks)],
        title: document.title || ""
    };
}
"""


class SiteCloner:
    def __init__(self, workspace: Path, file_history: Optional[Any] = None):
        self.workspace = Path(workspace).resolve()
        self.file_history = file_history

    def _download_asset(self, url: str, base_url: str, dest_path: Path, timeout: int = 7) -> bool:
        """Downloads an asset with realistic browser headers."""
        full_url = urllib.parse.urljoin(base_url, url)
        try:
            req = urllib.request.Request(
                full_url,
                headers={
                    "User-Agent": REAL_CHROME_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": base_url
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                dest_path.write_bytes(data)
                return True
        except Exception:
            return False

    def clone(self, url: str, output_folder: Optional[str] = None) -> Dict[str, Any]:
        """
        Clones the website at `url` 1:1 into `output_folder` inside the workspace.
        Extracts computed theme styles, root variables, DOM, stylesheets, and assets.
        """
        browser = get_browser_manager()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://") and not url.startswith("data:"):
            url = "https://" + url

        # 1. Open page in browser
        nav_res = browser.navigate(url)
        if not nav_res.get("success"):
            return {"success": False, "error": f"Failed to navigate to {url}: {nav_res.get('error')}"}

        # Wait for page assets and fonts to load
        time.sleep(1.0)

        # 2. Determine target folder
        parsed = urllib.parse.urlparse(url)
        domain_clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', parsed.netloc or "website")
        if not output_folder:
            output_folder = f"cloned_{domain_clean}"

        ws = self.workspace
        if ws == Path("/") or not os.access(ws, os.W_OK):
            ws = (Path.home() / "Desktop").resolve()
        target_dir = ws / output_folder
        if self.file_history:
            self.file_history.record_dir_before_create(target_dir)

        assets_dir = target_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 3. Capture original visual screenshot
        shot_res = browser.take_screenshot(full_page=False)
        orig_shot_b64 = shot_res.get("screenshot_b64", "")
        if orig_shot_b64 and orig_shot_b64.startswith("data:image/jpeg;base64,"):
            raw_shot = orig_shot_b64.split(",", 1)[1]
            try:
                (target_dir / "original_preview.jpg").write_bytes(base64.b64decode(raw_shot))
            except Exception:
                pass

        # 4. Extract styles, CSS variables, and asset lists via live JavaScript execution
        eval_res = browser.evaluate_js(JS_EXTRACT_STYLES_AND_ASSETS)
        page_data = eval_res.get("result", {}) if eval_res.get("success") else {}

        base_styles = page_data.get("baseStyles", {})
        css_vars = page_data.get("cssVars", {})
        extracted_sheets = page_data.get("extractedSheets", [])
        external_hrefs = page_data.get("externalHrefs", [])
        inline_styles = page_data.get("inlineStyles", [])
        images_to_download = page_data.get("images", [])
        bg_images_to_download = page_data.get("bgImages", [])
        font_links = page_data.get("fontLinks", [])

        # 5. Extract rendered DOM
        html_res = browser.get_html_content()
        raw_html = html_res.get("html", "")
        if not raw_html:
            return {"success": False, "error": "Could not extract rendered DOM from page."}

        # Also regex extract any img and stylesheet links from raw_html as fallback
        html_img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html, re.I)
        all_images = list(set(images_to_download + bg_images_to_download + html_img_srcs))

        html_css_links = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', raw_html, re.I)
        html_css_links += re.findall(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']', raw_html, re.I)
        all_external_css = list(set(external_hrefs + html_css_links))

        # 6. Download external stylesheets that were blocked from direct cssRules extraction
        asset_map = {}
        downloaded_count = 0
        combined_css_parts = []

        for css_href in all_external_css:
            full_css_url = urllib.parse.urljoin(url, css_href)
            clean_css_name = "style_" + re.sub(r'[^a-zA-Z0-9_\-\.]', '_', Path(urllib.parse.urlparse(full_css_url).path).name or "ext.css")
            if not clean_css_name.endswith(".css"):
                clean_css_name += ".css"

            dest_file = assets_dir / clean_css_name
            if self._download_asset(css_href, url, dest_file):
                asset_map[css_href] = f"assets/{clean_css_name}"
                downloaded_count += 1
                try:
                    text_content = dest_file.read_text(encoding="utf-8", errors="replace")
                    combined_css_parts.append(f"/* Extracted from: {css_href} */\n" + text_content)
                except Exception:
                    pass

        # Add rules extracted directly from Chromium's parsed styleSheets
        for item in extracted_sheets:
            sheet_css = item.get("css", "").strip()
            if sheet_css:
                origin_comment = f"/* Sheet: {item.get('href') or 'inline'} */\n"
                combined_css_parts.append(origin_comment + sheet_css)

        # Add inline <style> blocks
        for st in inline_styles:
            if st.strip():
                combined_css_parts.append("/* Inline <style> block */\n" + st.strip())

        # 7. Download images and background images
        for img_url in all_images:
            if not img_url or img_url.startswith("data:"):
                continue
            full_img_url = urllib.parse.urljoin(url, img_url)
            clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', Path(urllib.parse.urlparse(full_img_url).path).name or "img.png")
            if not any(clean_name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico", ".avif"]):
                clean_name += ".png"

            dest_file = assets_dir / clean_name
            if dest_file.exists() or self._download_asset(img_url, url, dest_file):
                asset_map[img_url] = f"assets/{clean_name}"
                downloaded_count += 1

        # 8. Resolve relative URLs inside consolidated CSS
        full_css_combined = "\n\n".join(combined_css_parts)

        # Replace any relative url(...) in CSS with local asset if downloaded, or absolute URL
        def _css_url_replacer(match):
            raw_target = match.group(1).strip("'\"")
            if raw_target.startswith("data:"):
                return match.group(0)
            if raw_target in asset_map:
                return f"url('{asset_map[raw_target]}')"
            full_resolved = urllib.parse.urljoin(url, raw_target)
            return f"url('{full_resolved}')"

        full_css_combined = re.sub(r'url\((?!data:)(.*?)\)', _css_url_replacer, full_css_combined)

        # 9. Build master style.css with root variables and base document styles
        css_header_lines = [
            "/* ==========================================================================",
            "   NonRoot 1:1 Cloned Stylesheet",
            f"   Source: {url}",
            f"   Cloned at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "   ========================================================================== */\n"
        ]

        # Add root CSS variables
        if css_vars:
            css_header_lines.append("/* Root Theme Variables */")
            css_header_lines.append(":root {")
            for var_name, var_val in sorted(css_vars.items()):
                css_header_lines.append(f"  {var_name}: {var_val};")
            css_header_lines.append("}\n")

        # Add computed base styles
        html_bg = base_styles.get("htmlBg") or "#ffffff"
        html_color = base_styles.get("htmlColor") or "#111827"
        html_font = base_styles.get("htmlFont") or "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        body_bg = base_styles.get("bodyBg") or html_bg
        body_color = base_styles.get("bodyColor") or html_color
        body_font = base_styles.get("bodyFont") or html_font
        body_lh = base_styles.get("bodyLineHeight") or "1.5"

        css_header_lines.append("/* Preserved Document Base Colors & Typography */")
        css_header_lines.append(f"""html {{
  background-color: {html_bg};
  color: {html_color};
  font-family: {html_font};
  box-sizing: border-box;
}}

body {{
  background-color: {body_bg};
  color: {body_color};
  font-family: {body_font};
  line-height: {body_lh};
  margin: 0;
  padding: 0;
  min-height: 100vh;
}}

*, *::before, *::after {{
  box-sizing: inherit;
}}
""")

        master_css = "\n".join(css_header_lines) + "\n\n" + full_css_combined
        (target_dir / "style.css").write_text(master_css, encoding="utf-8")

        # 10. Clean and enhance index.html
        clean_html = raw_html

        # Replace downloaded asset references in HTML
        for orig, local_path in asset_map.items():
            clean_html = clean_html.replace(f'"{orig}"', f'"{local_path}"').replace(f"'{orig}'", f"'{local_path}'")

        # Strip third-party tracking, analytics, and telemetry scripts
        clean_html = re.sub(r'<script[^>]*google-analytics\.com[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*googletagmanager\.com[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*yandex\.ru[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*mc\.yandex\.ru[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*facebook\.net[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)
        clean_html = re.sub(r'<script[^>]*sentry\.io[^>]*>.*?</script>', '', clean_html, flags=re.S | re.I)

        # Ensure <link rel="stylesheet" href="style.css"> is injected into <head>
        style_link_tag = '<link rel="stylesheet" href="style.css">'
        if "</head>" in clean_html:
            clean_html = clean_html.replace("</head>", f"    {style_link_tag}\n</head>", 1)
        elif "<body" in clean_html:
            clean_html = re.sub(r'<body', f'{style_link_tag}\n<body', clean_html, count=1, flags=re.I)
        else:
            clean_html = style_link_tag + "\n" + clean_html

        # Ensure viewport meta tag is present
        if "name=\"viewport\"" not in clean_html and "<head>" in clean_html:
            clean_html = clean_html.replace("<head>", "<head>\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">", 1)

        (target_dir / "index.html").write_text(clean_html, encoding="utf-8")

        # 11. Create README.md
        readme = f"""# 1:1 Website Clone: {domain_clean}

- **Source URL**: [{url}]({url})
- **Cloned At**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Cloned by**: NonRoot Autonomous AI Agent (Chromium Engine)
- **Downloaded Assets**: {downloaded_count} files
- **Extracted Stylesheets**: {len(extracted_sheets)} sheets

## Structure:
- `index.html` — Full responsive structure linked to consolidated `style.css`
- `style.css` — Consolidated stylesheet with preserved theme variables and computed colors
- `assets/` — Images, background graphics, SVG icons, and stylesheets
- `original_preview.jpg` — Visual reference screenshot of the live website
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
            "message": f"Сайт успешно клонирован 1 в 1 в '{output_folder}'. Созданы index.html, style.css (с оригинальными цветами и CSS-переменными) и скачано {downloaded_count} ассетов."
        }
