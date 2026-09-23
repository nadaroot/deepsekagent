#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== NonRoot Autonomous AI Agent - macOS Setup ==="

# 1. Install nonroot CLI wrapper in ~/.local/bin
mkdir -p "$HOME/.local/bin"
cat << 'WRAPPER' > "$HOME/.local/bin/nonroot"
#!/usr/bin/env bash
SCRIPT_DIR="$(dirname "$0")"
python3 -u "$HOME/Documents/strim/playerok/nonroot/nonroot.py" "$@"
WRAPPER
chmod +x "$HOME/.local/bin/nonroot"

# Try /usr/local/bin if writable
if [ -w "/usr/local/bin" ]; then
    ln -sf "$HOME/.local/bin/nonroot" "/usr/local/bin/nonroot"
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
    <key>CFBundleExecutable</key>
    <string>nonroot_launcher</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
</dict>
</plist>
PLIST

cat << LAUNCHER > "$APP_DIR/Contents/MacOS/nonroot_launcher"
#!/usr/bin/env bash
python3 "$BASE_DIR/nonroot.py"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/nonroot_launcher"

if [ -f "$BASE_DIR/assets/app.icns" ]; then
    cp "$BASE_DIR/assets/app.icns" "$APP_DIR/Contents/Resources/app.icns"
fi

echo "[+] Created macOS App: $APP_DIR"
echo "[+] Setup complete! You can now type 'nonroot' in terminal or launch NonRoot from Applications."
