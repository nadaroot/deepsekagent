#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== NonRoot Autonomous AI Agent - Linux Setup ==="

# 1. Install CLI in ~/.local/bin
mkdir -p "$HOME/.local/bin"
cat << WRAPPER > "$HOME/.local/bin/nonroot"
#!/usr/bin/env bash
python3 "$BASE_DIR/nonroot.py" "\$@"
WRAPPER
chmod +x "$HOME/.local/bin/nonroot"
echo "[+] Installed 'nonroot' CLI to $HOME/.local/bin/nonroot"

# 2. Desktop Entry
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat << DESKTOP > "$DESKTOP_DIR/nonroot.desktop"
[Desktop Entry]
Type=Application
Name=NonRoot AI
Comment=Autonomous AI Agent
Exec=$HOME/.local/bin/nonroot
Icon=$BASE_DIR/assets/logo.png
Terminal=false
Categories=Development;Utility;
DESKTOP
chmod +x "$DESKTOP_DIR/nonroot.desktop"
echo "[+] Created Linux Desktop entry: $DESKTOP_DIR/nonroot.desktop"
