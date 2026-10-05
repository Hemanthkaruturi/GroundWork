#!/bin/bash
# GroundWork Installation Script
# This script installs GroundWork into a project without requiring plugin marketplace access

set -e

# Configuration
GROUNDWORK_REPO="https://github.com/Hemanthkaruturi/GroundWork.git"
TEMP_DIR=".tmp-groundwork"
SKILLS_DIR=".devin/skills"

echo "Installing GroundWork..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Warning: Not in a git repository. Initializing one..."
    git init
fi

# Clone GroundWork to temporary directory
if [ -d "$TEMP_DIR" ]; then
    echo "Removing existing temporary directory..."
    rm -rf "$TEMP_DIR"
fi

echo "Cloning GroundWork repository..."
git clone "$GROUNDWORK_REPO" "$TEMP_DIR"

# Create skills directory
mkdir -p "$SKILLS_DIR"

# Copy plugin files
echo "Copying GroundWork plugin to .devin/skills/..."
rm -rf "$SKILLS_DIR/groundwork-specflow"
cp -r "$TEMP_DIR/plugins/groundwork-specflow" "$SKILLS_DIR/groundwork-specflow"

# Copy README for reference
cp "$TEMP_DIR/README.md" ".devin/groundwork-README.md"

# Configure .devin/config.json
echo "Configuring .devin/config.json..."
if [ ! -f ".devin/config.json" ]; then
    echo '{"requiredPlugins": []}' > .devin/config.json
fi

# Add GroundWork to requiredPlugins using Python
python3 << 'EOF'
import json
import os

config_path = '.devin/config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

plugin_path = '.devin/skills/groundwork-specflow'
if 'requiredPlugins' not in config:
    config['requiredPlugins'] = []

if plugin_path not in config['requiredPlugins']:
    config['requiredPlugins'].append(plugin_path)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print("Added GroundWork to requiredPlugins")
else:
    print("GroundWork already in requiredPlugins")
EOF

# Version tracking
echo "Recording version information..."
GW_SHA=$(cd "$TEMP_DIR" && git rev-parse HEAD)
GW_BRANCH=$(cd "$TEMP_DIR" && git rev-parse --abbrev-ref HEAD)
GW_DATE=$(date +%Y-%m-%d)
cat > .devin/groundwork-version << EOF
# GroundWork sync metadata -- do not edit manually
source=https://github.com/Hemanthkaruturi/GroundWork.git
branch=${GW_BRANCH}
commit=${GW_SHA}
synced=${GW_DATE}
EOF

# Clean up
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo ""
echo "GroundWork installed successfully!"
echo ""
echo "Next steps:"
echo "1. Run: python3 .devin/skills/groundwork-specflow/engine/groundwork.py bootstrap"
echo "2. Or in Devin: /hooks (to verify installation)"
echo "3. Then: /groundwork-specflow:bootstrap"
echo ""
echo "See .devin/groundwork-README.md for complete usage instructions."
