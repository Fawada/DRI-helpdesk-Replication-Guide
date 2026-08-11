#!/bin/bash
# Start the helpdesk worker in a tmux session on the current node.
# Run this on ga008.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${REPO_ROOT}/install/config.sh"

# Sanity checks
if [[ ! -d "${HELPDESK_INDEX_DIR}" ]]; then
    echo "ERROR: Index dir not found: ${HELPDESK_INDEX_DIR}"
    echo "Run install/setup.sh first."
    exit 1
fi

if [[ ! -x "${HELPDESK_PYTHON}" ]]; then
    echo "ERROR: Python interpreter not found: ${HELPDESK_PYTHON}"
    echo "Edit install/config.sh -> HELPDESK_PYTHON"
    exit 1
fi

# Check Ollama is up
if ! curl -s --max-time 5 "${HELPDESK_OLLAMA_HOST}/api/tags" > /dev/null; then
    echo "ERROR: Ollama not responding at ${HELPDESK_OLLAMA_HOST}"
    echo ""
    echo "Start Ollama on this node first:"
    echo "  pkill -u \$USER ollama"
    echo "  sleep 2"
    echo "  OLLAMA_HOST=127.0.0.1:11436 \\"
    echo "  OLLAMA_MODELS=${OLLAMA_MODELS} \\"
    echo "  nohup ~/apps/ollama/bin/ollama serve > ~/ollama-\$(hostname).log 2>&1 &"
    exit 1
fi

# Confirm both models are present
MODELS=$(curl -s "${HELPDESK_OLLAMA_HOST}/api/tags")
if ! echo "$MODELS" | grep -q "${HELPDESK_LLM_MODEL}"; then
    echo "ERROR: ${HELPDESK_LLM_MODEL} not available in Ollama."
    echo "Pull it first (from a login node)."
    exit 1
fi
if ! echo "$MODELS" | grep -q "${HELPDESK_EMBED_MODEL}"; then
    echo "ERROR: ${HELPDESK_EMBED_MODEL} not available in Ollama."
    echo "Pull it first (from a login node)."
    exit 1
fi

# Check tmux
if ! command -v tmux > /dev/null; then
    echo "tmux not installed. Running worker directly (Ctrl-C to stop)..."
    exec "${HELPDESK_PYTHON}" "${REPO_ROOT}/worker/worker.py"
fi

# If session exists, attach instead of starting a new one
if tmux has-session -t helpdesk 2>/dev/null; then
    echo "Worker tmux session 'helpdesk' already running."
    echo "  Attach: tmux attach -t helpdesk"
    echo "  Stop:   tmux kill-session -t helpdesk"
    exit 0
fi

# Start in detached tmux
tmux new-session -d -s helpdesk \
    "source ${REPO_ROOT}/install/config.sh && \
     ${HELPDESK_PYTHON} ${REPO_ROOT}/worker/worker.py 2>&1 | \
     tee -a ${HELPDESK_ROOT}/worker.console.log"

echo "Worker started in tmux 'helpdesk' on $(hostname)."
echo ""
echo "Useful commands:"
echo "  tmux attach -t helpdesk         # see worker output"
echo "  tmux kill-session -t helpdesk   # stop the worker"
echo "  tail -f ${HELPDESK_LOG_FILE}    # live activity log"
