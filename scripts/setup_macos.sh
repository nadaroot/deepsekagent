#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== NonRoot Autonomous AI Agent - macOS Setup ==="

# 1. Install nonroot CLI wrapper in ~/.local/bin
mkdir -p "$HOME/.local/bin"
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
    echo "[-] Error: python3 not found. Please install Python 3."
    exit 1
fi

exec "$PYTHON_EXEC" "$HOME/Documents/strim/playerok/nonroot/nonroot.py" "$@"
WRAPPER
chmod +x "$HOME/.local/bin/nonroot"

# Try /usr/local/bin if writable
if [ -w "/usr/local/bin" ]; then
    ln -sf "$HOME/.local/bin/nonroot" "/usr/local/bin/nonroot" 2>/dev/null || true
    echo "[+] Installed 'nonroot' CLI command to /usr/local/bin/nonroot"
else
    echo "[+] Installed 'nonroot' CLI command to $HOME/.local/bin/nonroot"
fi

# 2. Create macOS Application Bundle in ~/Applications
APP_DIR="$HOME/Applications/NonRoot.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

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
    <key>CFBundleExecutable</key>
    <string>nonroot_launcher</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST

cat << 'LAUNCHER' > "$APP_DIR/Contents/MacOS/nonroot_launcher"
#!/usr/bin/env bash
export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Developer/CommandLineTools/usr/bin:$HOME/.local/bin:$PATH"

PYTHON_EXEC=""
for p in "/usr/local/bin/python3" "/opt/homebrew/bin/python3" "$(command -v python3 2>/dev/null)" "/Library/Developer/CommandLineTools/usr/bin/python3" "/usr/bin/python3"; do
    if [ -n "$p" ] && [ -x "$p" ]; then
        PYTHON_EXEC="$p"
        break
    fi
done

if [ -z "$PYTHON_EXEC" ]; then
    osascript -e 'display dialog "Python 3 is required to run NonRoot. Please install Python 3." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

TARGET_SCRIPT="$HOME/Documents/strim/playerok/nonroot/nonroot.py"
if [ ! -f "$TARGET_SCRIPT" ]; then
    TARGET_SCRIPT="$(cd "$(dirname "$0")/../../../../Documents/strim/playerok/nonroot" 2>/dev/null && pwd)/nonroot.py"
fi

exec "$PYTHON_EXEC" "$TARGET_SCRIPT"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/nonroot_launcher"

if [ -f "$BASE_DIR/assets/app.icns" ]; then
    cp "$BASE_DIR/assets/app.icns" "$APP_DIR/Contents/Resources/app.icns"
fi

chmod -R 755 "$APP_DIR"
touch "$APP_DIR"

echo "[+] Created/Updated macOS App: $APP_DIR"
echo "[+] Setup complete! You can now type 'nonroot' in terminal or launch NonRoot from Applications."

