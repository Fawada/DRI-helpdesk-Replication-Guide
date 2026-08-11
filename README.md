# AI HPC Helpdesk — RAG-based Question Answering for HPC Facilities

A lightweight, self-hosted AI helpdesk that answers questions about your HPC
facility using your own documentation. Built at DiRAC / Durham University and
successfully replicated at Keele University's GreenHPC cluster.

**No data leaves your site. No OpenAI API key needed. Runs entirely on your
existing GPU hardware.**

---

## What It Does

Users type questions in plain English from any login node:

```
$ ask-cosma "how do I submit a GPU job?"

To submit a GPU job on COSMA8, use the following SLURM script:

  #SBATCH --partition=gpu
  #SBATCH --gres=gpu:1
  #SBATCH --account=your_project

The COSMA8 GPU nodes each have 4x NVIDIA A100 GPUs. For more details see:
https://cosma.readthedocs.io/en/latest/gpu.html
```

The system retrieves relevant chunks from your documentation using hybrid
BM25 + dense vector search, then generates a grounded answer using a local
language model via Ollama. Answers stream token-by-token to the terminal.

---

## Architecture

```
User on any login node
        │  writes JSON to shared filesystem queue
        ▼
  Shared filesystem (NFS/Lustre/GPFS)
        │  worker polls and claims requests
        ▼
  worker.py on GPU node
        ├── LlamaIndex hybrid retriever (BM25 + dense, top-12 chunks)
        └── Ollama HTTP streaming (llama3.1:8b, local)
        │  tokens stream to user via shared filesystem
        ▼
  Answer appears in user's terminal
```

---

## Proven Deployments

| Facility | Institution | Corpus | Command |
|---|---|---|---|
| COSMA | Durham University | ~80 markdown pages | `ask-cosma` |
| COSMA Admin | Durham University | COSMA + OpenStack docs | `ask-cosma-admin` |
| GreenHPC | Keele University | 1 Word document | `ask-keel` |

**Replication time for Keele: ~2 hours from zero to working helpdesk.**

---

## Repository Contents

```
├── worker.py            # RAG pipeline + Ollama streaming worker
├── ask-helpdesk.py      # CLI client (rename per facility)
├── ingest.py            # Builds the vector index from your docs
├── setup.sh             # Creates shared dirs, copies index to shared FS
├── start-worker.sh      # Launches worker in tmux on GPU node
├── install-user.sh      # Adds shell alias for each user
├── config.sh.example    # THE only file you edit per deployment
├── .gitignore
├── REPLICATION.md       # Full step-by-step replication guide

```

---

## Quick Start

### Prerequisites
- GPU node (llama3.1:8b needs ~6 GB VRAM)
- Shared filesystem visible from all login nodes
- Python 3.10+, [Ollama](https://ollama.com)

### 1. Clone and install dependencies
```bash
git clone https://github.com/Fawada/DRI-helpdesk-Replication-Guide.git
cd DRI-helpdesk-Replication-Guide

python3 -m venv ~/hpc-helpdesk-env
source ~/hpc-helpdesk-env/bin/activate
pip install llama-index llama-index-llms-ollama \
            llama-index-embeddings-ollama \
            llama-index-retrievers-bm25 python-docx
```

### 2. Pull models (on GPU node)
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### 3. Prepare your docs and build the index
```bash
# If your docs are a Word file:
python3 ingest/convert_docx.py --input your-docs.docx --output ~/helpdesk-docs/

# Build the index
python3 ingest.py --docs-dir ~/helpdesk-docs/ --index-dir ~/helpdesk-index/
```

### 4. Configure
```bash
cp config.sh.example config.sh
nano config.sh   # edit 4 values: HELPDESK_ROOT, INDEX_DIR, PYTHON, emails
```

### 5. Deploy and test
```bash
bash setup.sh
bash start-worker.sh
bash install-user.sh && source ~/.bashrc
ask-helpdesk "how do I submit a job?"
```

**See [docs/REPLICATION.md](docs/REPLICATION.md) for the full step-by-step guide.**

---

## What Changes Between Deployments

Only four things need changing to replicate at a new facility:

| What | Where |
|---|---|
| Shared filesystem root path | `config.sh` |
| Index directory path | `config.sh` |
| Facility name + support email | `worker.py` prompt |
| Source documents | Your docs directory |

Everything else — the worker logic, retrieval pipeline, streaming, queue
architecture — is reused unchanged.

---

## Technical Stack

- **Retrieval:** LlamaIndex hybrid BM25 + dense vector search (FINAL_TOP_K=12)
- **Embeddings:** nomic-embed-text via Ollama
- **Generation:** llama3.1:8b via Ollama (direct HTTP streaming)
- **Index format:** LlamaIndex persistent vector store
- **Queue:** shared filesystem (no message broker required)
- **Temperature:** 0.1 (near-deterministic answers)

---

## Citation / Contact

Developed by **Dr Fawada Qaiser**
Lead Data & AI Engineer, DiRAC / Durham University
Honorary Lecturer in ML, AI and Data Science, University of Liverpool

Part of the DRI HPC federation AI helpdesk initiative.

For questions: dc-qais1@durham.ac.uk

---

## Licence

MIT — free to use and adapt for your HPC facility.
