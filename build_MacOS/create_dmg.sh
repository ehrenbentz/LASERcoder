#!/bin/bash
# create_dmg.sh
# Creates a distributable DMG from the Nuitka .app bundle

APP_NAME="LaserTAG"
APP_PATH="main.app"
DMG_NAME="${APP_NAME}Installer.dmg"
VOLUME_NAME="${APP_NAME}"
STAGING_DIR="dmg_staging"

# Rename the app if Nuitka named it main.app
if [ -d "main.app" ] && [ ! -d "${APP_NAME}.app" ]; then
    mv main.app "${APP_NAME}.app"
    APP_PATH="${APP_NAME}.app"
fi

# Clean up any previous staging
rm -rf "$STAGING_DIR"
rm -f "$DMG_NAME"

# Create staging directory
mkdir -p "$STAGING_DIR"

# Copy the app
cp -R "$APP_PATH" "$STAGING_DIR/"

# Create a symlink to /Applications so users can drag-and-drop
ln -s /Applications "$STAGING_DIR/Applications"

# Create the DMG
hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_NAME"

# Clean up
rm -rf "$STAGING_DIR"

echo "Created: $DMG_NAME"