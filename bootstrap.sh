#!/usr/bin/env bash
# Install 'just' task runner — run this once before using the Justfile.
# After this, run: just init

set -euo pipefail

if command -v just &>/dev/null; then
    echo "just $(just --version) is already installed"
    exit 0
fi

echo "→ Installing just..."

# Prefer the official installer; fall back to cargo if curl is unavailable
if command -v curl &>/dev/null; then
    mkdir -p "$HOME/.local/bin"
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
        | bash -s -- --to "$HOME/.local/bin"
elif command -v cargo &>/dev/null; then
    cargo install just
else
    echo "Error: neither curl nor cargo found — install one and retry" >&2
    exit 1
fi

# Add ~/.local/bin to PATH for this session so 'just' is immediately usable
export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "✓ just $(just --version) installed"
echo ""
echo "If 'just' is not found in future shells, add this to your shell profile:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Next step: just init"
