#!/bin/zsh

# Augur Environment Cleanup Utility
# This script helps remove hardcoded environment variables from your shell profile
# to enable the fully dynamic path discovery system.

SHELL_PROFILE=""
if [[ -f "$HOME/.zshrc" ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [[ -f "$HOME/.bash_profile" ]]; then
    SHELL_PROFILE="$HOME/.bash_profile"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
fi

if [[ -z "$SHELL_PROFILE" ]]; then
    echo "❌ No shell profile found (.zshrc, .bash_profile, or .bashrc)"
    exit 1
fi

echo "🔍 Checking $SHELL_PROFILE for AUGUR environment variables..."

VARS_TO_REMOVE=(
    "AUGUR_ROOT"
    "AUGUR_PLUGINS"
    "AUGUR_ROOT"
    "AUGUR_RUNTIME"
    "AUGUR_USER"
)

FOUND=false
for var in "${VARS_TO_REMOVE[@]}"; do
    if grep -q "export $var=" "$SHELL_PROFILE"; then
        echo "Found: export $var=..."
        FOUND=true
    fi
done

if ! $FOUND; then
    echo "✅ No hardcoded AUGUR variables found in $SHELL_PROFILE."
    echo "Your system is already set up for dynamic discovery!"
    exit 0
fi

echo ""
echo "⚠️ IMPORTANT: We recommend removing these hardcoded variables to allow the"
echo "system to automatically find its paths when you move the folder."
echo ""
echo "To clean up your profile, you can run:"
for var in "${VARS_TO_REMOVE[@]}"; do
    echo "sed -i '' '/export $var=/d' $SHELL_PROFILE"
done
echo ""
echo "Then restart your terminal or run: source $SHELL_PROFILE"
echo ""
echo "Would you like to perform the cleanup now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    for var in "${VARS_TO_REMOVE[@]}"; do
        sed -i '' "/export $var=/d" "$SHELL_PROFILE"
        unset "$var"
    done
    echo "✅ Cleanup complete! Please restart your terminal."
else
    echo "Skipped cleanup."
fi
