# HPC AI Helpdesk — Replication Guide

**How to deploy the RAG-based AI helpdesk at any HPC facility**

Developed at DiRAC / Durham University as part of the DRI federation roadmap.
Demonstrated on COSMA (Durham) and GreenHPC (Keele University).

---

## What This Is

A lightweight, self-hosted AI helpdesk that answers questions about your HPC
facility by retrieving relevant chunks from your own documentation and passing
them to a local language model. No data leaves your site. No OpenAI API key
needed. Runs entirely on your existing GPU hardware via Ollama.

The system was built and deployed at COSMA (Durham University) and successfully
replicated at Keele University's GreenHPC cluster from a single Word document
in under two hours. This guide documents exactly how to do that.

---

## Architecture Overview

```
User on any login node
        │
        │  writes JSON request to shared filesystem queue
        ▼
  $HELPDESK_ROOT/queue/requests/
        │
        │  worker polls and atomically claims requests
        ▼
  worker.py on GPU node (ga008 at COSMA)
        │
        ├── LlamaIndex hybrid retriever (BM25 + dense vector)
        │         pulls top-12 chunks from your indexed docs
        │
        └── Ollama HTTP API (llama3.1:8b, local, streaming)
                  streams tokens to streams/<id>.stream
                  writes final response to responses/<id>.json
        │
        ▼
  User sees streamed answer in terminal
```

**Key design decisions:**

- Shared filesystem queue (NFS) — no message broker needed
- Direct Ollama HTTP streaming — bypasses LlamaIndex query engine for speed
- Hybrid BM25 + dense retrieval — better than either alone for HPC docs
- Single config file — the only file that changes between deployments

---

## Prerequisites

### Hardware
- A GPU node with enough VRAM for your chosen model
  - llama3.1:8b requires ~6 GB VRAM (runs well on AMD MI300X, NVIDIA A100, etc.)
  - All login nodes need shared filesystem access to the queue directory
- Shared filesystem visible from ALL nodes (NFS, Lustre, GPFS, etc.)

### Software
- Python 3.10+ with pip
- [Ollama](https://ollama.com) installed on the GPU node
- Git

### Models (pulled via Ollama on the GPU node)
```bash
ollama pull llama3.1:8b        # generation
ollama pull nomic-embed-text   # embeddings
ollama pull llama3.2:3b        # index build only (lighter model)
```

---

## Repository Structure

```
ai-hpc-helpdesk/
├── install/
│   ├── config.sh          # THE ONLY FILE YOU EDIT PER DEPLOYMENT
│   ├── setup.sh           # creates shared dirs, copies index
│   └── install-user.sh    # adds shell alias for each user
├── worker/
│   ├── worker.py          # RAG pipeline + Ollama streaming
│   └── start-worker.sh    # launches worker in tmux on GPU node
├── client/
│   └── ask-helpdesk.py    # CLI client (rename per facility)
├── ingest/
│   ├── ingest.py          # builds the vector index from docs
│   └── convert_docx.py    # converts Word docs to markdown
└── docs/
    └── REPLICATION.md     # this guide
```

---

## Step-by-Step Replication

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_ORG/ai-hpc-helpdesk.git
cd ai-hpc-helpdesk
```

### Step 2 — Set up the Python environment

On your GPU node:

```bash
python3 -m venv ~/hpc-helpdesk-env
source ~/hpc-helpdesk-env/bin/activate
pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-retrievers-bm25 python-docx
```

### Step 3 — Start Ollama on the GPU node

```bash
OLLAMA_HOST=127.0.0.1:11436 \
OLLAMA_MODELS=/path/to/shared/ollama-models \
nohup ollama serve > ~/ollama.log 2>&1 &

# Pull required models
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### Step 4 — Prepare your documentation

Your docs can be in any of these formats:

**Option A — Markdown files (ideal)**

Already in `.md` format? Put them in a directory and skip to Step 5.

**Option B — Word document (.docx)**

```bash
python3 ingest/convert_docx.py \
    --input /path/to/your-docs.docx \
    --output ~/helpdesk-docs/
```

This converts headings to `#`/`##`/`###` markdown and preserves code blocks.
Check the output:

```bash
head -60 ~/helpdesk-docs/your-docs.md
```

**Option C — Existing web documentation**

If your docs are on ReadTheDocs or a similar platform, clone the source
repository and point the ingest script at the `.md`/`.rst` source files.

### Step 5 — Build the index

```bash
source ~/hpc-helpdesk-env/bin/activate

python3 ingest/ingest.py \
    --docs-dir ~/helpdesk-docs/ \
    --index-dir ~/helpdesk-index/ \
    --ollama-host http://127.0.0.1:11436
```

This will take 5–20 minutes depending on corpus size and hardware.
You should see output like:

```
Loaded 45 documents
Markdown parser produced 312 nodes
Building index... 100%|████████████| 312/312
Index saved to ~/helpdesk-index/
```

Verify the index covers your key documents:

```bash
python3 ingest/inspect_index.py --index-dir ~/helpdesk-index/
```

### Step 6 — Edit config.sh

This is the only file that changes between deployments:

```bash
cp install/config.sh install/config.sh.example
nano install/config.sh
```

Edit these values:

```bash
# Root directory on shared filesystem — must be visible from ALL nodes
export HELPDESK_ROOT="/shared/fs/path/to/your-helpdesk"

# Path to the index you built in Step 5
export HELPDESK_INDEX_DIR="/shared/fs/path/to/your-helpdesk/index"

# Python interpreter with dependencies installed
export HELPDESK_PYTHON="/home/YOU/hpc-helpdesk-env/bin/python"

# Ollama on your GPU node
export HELPDESK_OLLAMA_HOST="http://127.0.0.1:11436"

# Models
export HELPDESK_LLM_MODEL="llama3.1:8b"
export HELPDESK_EMBED_MODEL="nomic-embed-text"

# Contact shown to users when worker is offline
export HELPDESK_ADMIN_EMAIL="you@your-institution.ac.uk"
export HELPDESK_SUPPORT_EMAIL="hpc-support@your-institution.ac.uk"
```

Everything else (queue dirs, poll intervals, timeouts) can stay as defaults.

### Step 7 — Update the prompt for your facility

In `worker/worker.py`, find `QA_PROMPT_TEMPLATE` and update the
facility name and support email:

```python
QA_PROMPT_TEMPLATE = (
    "You are the YOUR-FACILITY-NAME helpdesk assistant at YOUR UNIVERSITY. "
    ...
    "contacting hpc-support@your-institution.ac.uk instead.\n"
    ...
)
```

The two placeholders to change are:
- The facility name in the first line
- The support email in the SECURITY rule

Everything else in the prompt should stay as-is — it has been tuned for
llama3.1:8b at this scale.

### Step 8 — Run setup and start the worker

```bash
# On your GPU node:
source install/config.sh

# Copy index to shared filesystem and create queue directories
bash install/setup.sh

# Start the worker in a tmux session
bash worker/start-worker.sh

# Verify it's running
tmux ls
tmux attach -t helpdesk   # watch startup output, Ctrl-B D to detach
```

### Step 9 — Install the client for users

Each user runs this once:

```bash
bash install/install-user.sh
source ~/.bashrc
```

This adds a shell alias so they can type `ask-helpdesk "question"` from
any login node.

### Step 10 — Test

```bash
ask-helpdesk "how do I log in?"
ask-helpdesk "how do I submit a job?"
ask-helpdesk "how do I debug an MPI deadlock?"
```

---

## Renaming the Command

The client command defaults to `ask-helpdesk`. To rename it to match your
facility (e.g. `ask-archer`, `ask-baskerville`):

```bash
# Rename the client script
mv client/ask-helpdesk.py client/ask-archer.py

# Update install-user.sh
sed -i 's/ask-helpdesk/ask-archer/g' install/install-user.sh

# Re-run install for each user
bash install/install-user.sh
```

---

## Adding URL Citations

If your documentation is hosted publicly (e.g. ReadTheDocs), you can make
the helpdesk cite source URLs in its answers. In `worker/worker.py`,
find `fname_to_url()` and update it:

```python
def fname_to_url(fname):
    base = fname.replace(".md", ".html").replace(".rst", ".html")
    return f"https://YOUR-FACILITY.readthedocs.io/en/latest/{base}"
```

This maps each retrieved chunk's filename to a public URL, which gets
injected into the context so the model can cite it.

---

## Corpus Size Guidelines

| Corpus size | Chunks | Index build time | Answer quality |
|---|---|---|---|
| 1 Word doc (~200 lines) | 15–25 | 2–5 min | Good for focused questions |
| Small doc site (~20 pages) | 100–200 | 10–20 min | Good |
| Full doc site (~80 pages) | 400–600 | 30–60 min | Best |

For very small corpora (single document), consider increasing `FINAL_TOP_K`
in `worker.py` from 12 to 6 so the full document fits in context.

---

## Troubleshooting

**Worker shows offline from login nodes but works on GPU node**

Ollama only runs on the GPU node. The worker must be started there, not
on login nodes. The client (ask-helpdesk) can run from any node.

**Wrong answers for facility-specific questions**

Check whether the relevant doc chunk is being retrieved:

```bash
python3 ingest/inspect_index.py \
    --index-dir ~/helpdesk-index/ \
    --query "your question here"
```

If the right file doesn't appear in the top 12, either add an explicit
Q&A entry to your source document and reindex, or increase `FINAL_TOP_K`.

**Model invents facility-specific facts**

The prompt instructs the model to use only the Context for facility-specific
facts. If hallucination persists for a specific question, add an explicit
answer to your source documentation and reindex — retrieval is the most
reliable fix.

**Syntax error after editing worker.py**

Always verify before restarting:

```bash
python3 -c "import ast; ast.parse(open('worker/worker.py').read()); print('OK')"
```

---

## What Changes Between Deployments

To replicate at a new facility, you change exactly four things:

| What | Where | Example |
|---|---|---|
| Shared filesystem root | `install/config.sh` | `/shared/your-helpdesk` |
| Index directory | `install/config.sh` | `/shared/your-helpdesk/index` |
| Facility name + support email | `worker/worker.py` prompt | `"GreenHPC helpdesk at Keele"` |
| Source documents | Your docs dir | `~/helpdesk-docs/*.md` |

Everything else — the worker logic, retrieval pipeline, streaming, queue
architecture, client — is reused unchanged.

---

## Proven Deployments

| Facility | Institution | Corpus | Command |
|---|---|---|---|
| COSMA | Durham University | ~80 markdown pages (cosmadoc) | `ask-cosma` |
| COSMA Admin | Durham University | COSMA + OpenStack docs | `ask-cosma-admin` |
| GreenHPC | Keele University | 1 Word document | `ask-keel` |

---

## Repository Contents for GitHub

Push the following to your public repo. Do NOT commit:
- `install/config.sh` (contains your paths — commit `config.sh.example` instead)
- Any index files (`cosma_index/`, `keel_index/` etc.)
- Log files or queue contents
- Model weights

Recommended `.gitignore`:

```
install/config.sh
*_index/
*.log
queue/
streams/
responses/
__pycache__/
*.pyc
hpc-helpdesk-env/
```

---

*Developed by Dr Fawada Qaiser, DiRAC / Durham University, 2026.
Part of the DRI HPC federation AI helpdesk initiative.*
