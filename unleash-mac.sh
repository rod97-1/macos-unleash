#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME=$(system_profiler SPHardwareDataType | awk -F': ' '/Model Name/ {print $2}')
TOTAL_RAM_GB=$(sysctl -n hw.memsize | awk '{print int($1/1073741824)}')

echo "----------------------------------------------------------------"
echo " Detected Hardware : $MODEL_NAME"
echo " Unified Memory    : ${TOTAL_RAM_GB} GB"
echo "----------------------------------------------------------------"

sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

echo "[1/5] Applying WindowServer and UI optimizations..."
defaults write com.apple.dock magnification -bool false
defaults write com.apple.dock autohide-time-modifier -float 0
defaults write com.apple.dock autohide-delay -float 0
defaults write com.apple.dock launchanim -bool false
defaults write com.apple.finder DisableAllAnimations -bool true
defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
defaults write NSGlobalDomain NSAppSleepDisabled -bool true
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 10
killall Dock Finder 2>/dev/null || true

echo "[2/5] Disabling Apple telemetry and Bonjour advertising..."
sudo launchctl disable system/com.apple.analyticsd 2>/dev/null || true
sudo launchctl disable system/com.apple.diagnosticd 2>/dev/null || true
sudo defaults write /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements -bool YES
sudo killall -HUP mDNSResponder 2>/dev/null || true

echo "[3/5] Installing persistent boot daemon..."
PLIST_PATH="/Library/LaunchDaemons/com.custom.unleash.plist"
if [ "$TOTAL_RAM_GB" -ge 90 ]; then
    VRAM_CMD="/usr/sbin/sysctl -w iogpu.wired_limit_mb=90112; /usr/sbin/sysctl -w iogpu.wired_lwm_mb=86016"
else
    VRAM_CMD="true"
fi

sudo tee "$PLIST_PATH" > /dev/null <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.custom.unleash</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>/sbin/ifconfig awdl0 down; /sbin/ifconfig llw0 down; $VRAM_CMD</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST

sudo chown root:wheel "$PLIST_PATH"
sudo chmod 644 "$PLIST_PATH"
sudo launchctl bootout system "$PLIST_PATH" 2>/dev/null || true
sudo launchctl bootstrap system "$PLIST_PATH"

echo "[4/5] Applying power management rules..."
if [[ "$MODEL_NAME" == *"Mac Studio"* ]]; then
    sudo pmset -a sleep 0 disksleep 0 displaysleep 15 womp 1 autorestart 1 powernap 0
else
    sudo pmset -c sleep 0 disksleep 0 displaysleep 20 womp 1 powernap 0
    sudo pmset -b sleep 15 disksleep 10 displaysleep 10 powernap 0 lowpowermode 0
fi

echo "[5/5] Checking Homebrew & installing software stack..."
if ! command -v brew &>/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if ! grep -q "/opt/homebrew/bin/brew" ~/.zprofile 2>/dev/null; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if [ -f "$SCRIPT_DIR/Brewfile" ]; then
    brew bundle --file="$SCRIPT_DIR/Brewfile"
fi

if command -v npm &>/dev/null && ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
fi

echo "================================================================"
echo " MACOS-UNLEASH COMPLETE: System is locked and optimized."
echo "================================================================"
