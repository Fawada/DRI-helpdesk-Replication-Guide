#!/bin/bash
# One-time setup: prepare shared filesystem, copy the existing index over.
# Run this ONCE on any node that can see both ~/hpc-helpdesk and the shared FS.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/config.sh"

echo "==> Setting up COSMA Helpdesk infrastructure"
echo ""
echo "    HELPDESK_ROOT  = ${HELPDESK_ROOT}"
echo "    INDEX_DIR      = ${HELPDESK_INDEX_DIR}"
echo "    QUEUE_DIR      = ${HELPDESK_QUEUE_DIR}"
echo ""

# 1. Create the shared root and subdirectories
echo "==> Creating shared directories..."
mkdir -p "${HELPDESK_ROOT}"
mkdir -p "${HELPDESK_QUEUE_DIR}/requests"
mkdir -p "${HELPDESK_QUEUE_DIR}/claimed"
mkdir -p "${HELPDESK_QUEUE_DIR}/responses"

# Make queue dirs world-writable so other COSMA users can submit requests.
# Sticky bit so users can only delete their own files.
chmod 1777 "${HELPDESK_QUEUE_DIR}/requests" || true
chmod 1777 "${HELPDESK_QUEUE_DIR}/responses" || true
chmod 0755 "${HELPDESK_QUEUE_DIR}/claimed" || true

# 2. Copy existing index from home if not already present on shared FS
if [[ -d "${HELPDESK_INDEX_DIR}" && -f "${HELPDESK_INDEX_DIR}/docstore.json" ]]; then
    echo "==> Index already exists at ${HELPDESK_INDEX_DIR} - skipping copy."
else
    SOURCE_INDEX="${HOME}/hpc-helpdesk/cosma_index"
    if [[ ! -d "${SOURCE_INDEX}" ]]; then
        echo "ERROR: Source index not found at ${SOURCE_INDEX}"
        echo "       Build it first with ingest.py before running setup."
        exit 1
    fi
    echo "==> Copying index from ${SOURCE_INDEX} to ${HELPDESK_INDEX_DIR}..."
    mkdir -p "${HELPDESK_INDEX_DIR}"
    cp -r "${SOURCE_INDEX}"/* "${HELPDESK_INDEX_DIR}/"
fi

# 3. Touch initial heartbeat (so worker_alive() doesn't immediately fail
#    if a user runs ask-cosma right after setup but before worker starts -
#    actually we want it to fail in that case, so DON'T touch it here).

# 4. Initial log entry
touch "${HELPDESK_LOG_FILE}"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | INFO | setup_complete by $(whoami) on $(hostname)" >> "${HELPDESK_LOG_FILE}"

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Make sure Ollama is running on ga008 with both models available."
echo "     (See start-ollama.sh or OPERATOR_RUNBOOK.md)"
echo "  2. Start the worker on ga008:"
echo "       bash ${REPO_ROOT}/worker/start-worker.sh"
echo "  3. From any node, install the ask-cosma command in your shell:"
echo "       bash ${SCRIPT_DIR}/install-user.sh"
echo ""
