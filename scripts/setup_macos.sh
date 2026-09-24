#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== NonRoot Autonomous AI Agent - macOS Setup ==="

APP_DIR="$HOME/Applications/NonRoot.app"
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/Applications"
mkdir -p "$HOME/.nonroot/app"

# 1. Record exact current git commit into assets/version.json
GIT_COMMIT=$(git -C "$BASE_DIR" rev-parse HEAD 2>/dev/null | cut -c1-7 || echo "latest")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat << VER_EOF > "$BASE_DIR/assets/version.json"
{
  "version": "1.1.0",
  "commit": "$GIT_COMMIT",
  "updated_at": "$BUILD_TIME"
}
VER_EOF

# 1. Sync self-contained bundle & ~/.nonroot/app
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources/app"

cp -R "$BASE_DIR/nonroot" "$APP_DIR/Contents/Resources/app/"
cp "$BASE_DIR/nonroot.py" "$APP_DIR/Contents/Resources/app/"
cp -R "$BASE_DIR/assets" "$APP_DIR/Contents/Resources/app/"
cp "$BASE_DIR/requirements.txt" "$APP_DIR/Contents/Resources/app/"
cp "$BASE_DIR/assets/app.icns" "$APP_DIR/Contents/Resources/app.icns"

if [ -d "$BASE_DIR/../deepseek-api" ]; then
    rsync -a --exclude='.git' "$BASE_DIR/../deepseek-api" "$APP_DIR/Contents/Resources/" 2>/dev/null || cp -R "$BASE_DIR/../deepseek-api" "$APP_DIR/Contents/Resources/" 2>/dev/null || true
    rsync -a --exclude='.git' "$BASE_DIR/../deepseek-api" "$HOME/.nonroot/" 2>/dev/null || cp -R "$BASE_DIR/../deepseek-api" "$HOME/.nonroot/" 2>/dev/null || true
fi

cp -R "$BASE_DIR/nonroot" "$HOME/.nonroot/app/"
cp "$BASE_DIR/nonroot.py" "$HOME/.nonroot/app/"
cp -R "$BASE_DIR/assets" "$HOME/.nonroot/app/"

# 2. Compile Native Cocoa + WebKit Mach-O Binary
echo "[*] Compiling native macOS Cocoa + WebKit executable..."
clang -O2 -fobjc-arc -framework Cocoa -framework WebKit "$BASE_DIR/src/macos_app.m" -o "$APP_DIR/Contents/MacOS/NonRoot"
chmod +x "$APP_DIR/Contents/MacOS/NonRoot"

# 3. Write Info.plist
cat << 'PLIST' > "$APP_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>NonRoot</string>
    <key>CFBundleName</key>
    <string>NonRoot</string>
    <key>CFBundleIdentifier</key>
    <string>ai.nonroot.agent</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>NonRoot</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# 4. CLI wrapper in ~/.local/bin/nonroot
cat << 'WRAPPER' > "$HOME/.local/bin/nonroot"
#!/usr/bin/env bash
export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Developer/CommandLineTools/usr/bin:$PATH"

PYTHON_EXEC=""
for p in "/usr/local/bin/python3" "/opt/homebrew/bin/python3" "$(command -v python3 2>/dev/null)" "/Library/Developer/CommandLineTools/usr/bin/python3" "/usr/bin/python3"; do
    if [ -n "$p" ] && [ -x "$p" ]; then
        PYTHON_EXEC="$p"
        break
    fi
done

if [ -z "$PYTHON_EXEC" ]; then
    echo "[-] Error: python3 not found."
    exit 1
fi

exec "$PYTHON_EXEC" -u "$HOME/.nonroot/app/nonroot.py" "$@"
WRAPPER
chmod +x "$HOME/.local/bin/nonroot"

if [ -w "/usr/local/bin" ]; then
    ln -sf "$HOME/.local/bin/nonroot" "/usr/local/bin/nonroot" 2>/dev/null || true
    echo "[+] Installed 'nonroot' CLI command to /usr/local/bin/nonroot"
else
    echo "[+] Installed 'nonroot' CLI command to $HOME/.local/bin/nonroot"
fi

chmod -R 755 "$APP_DIR"
touch "$APP_DIR"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_DIR" 2>/dev/null || true

echo "[+] Created/Updated macOS App: $APP_DIR"
echo "[+] Setup complete! You can now type 'nonroot' in terminal or launch NonRoot from Applications."


