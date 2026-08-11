#!/bin/bash
# Install ask-cosma into the current user's shell.
# Adds an alias so they can type `ask-cosma "question"` from any node.
#
# Each user (you and your colleagues) runs this once on their own account.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_PATH="${REPO_ROOT}/install/config.sh"
CLIENT_PATH="${REPO_ROOT}/client/ask-cosma.py"

if [[ ! -f "${CONFIG_PATH}" ]]; then
    echo "ERROR: config.sh not found at ${CONFIG_PATH}"
    exit 1
fi

if [[ ! -f "${CLIENT_PATH}" ]]; then
    echo "ERROR: ask-cosma.py not found at ${CLIENT_PATH}"
    exit 1
fi

chmod +x "${CLIENT_PATH}" 2>/dev/null || true

# Append to user's bashrc if not already there.
MARKER="# >>> COSMA AI Helpdesk >>>"
END_MARKER="# <<< COSMA AI Helpdesk <<<"

if grep -q "${MARKER}" "${HOME}/.bashrc" 2>/dev/null; then
    echo "ask-cosma already installed in ~/.bashrc - skipping."
else
    cat >> "${HOME}/.bashrc" <<EOF

${MARKER}
# Sources the helpdesk config and provides the ask-cosma command.
# Auto-added by install-user.sh - safe to remove.
if [[ -f "${CONFIG_PATH}" ]]; then
    source "${CONFIG_PATH}"
    alias ask-cosma="python3 ${CLIENT_PATH}"
fi
${END_MARKER}
EOF
    echo "==> Added ask-cosma to ~/.bashrc"
fi

echo ""
echo "==> Install complete."
echo ""
echo "Open a new shell (or run: source ~/.bashrc) then try:"
echo "    ask-cosma \"How do I check my disk quota?\""
echo ""
