"""
COSMA HPC Helpdesk - Document ingestion (v2).

Key change from v1: use MarkdownNodeParser instead of SentenceSplitter.
COSMA docs are heavily structured with ## headings (## COSMA7, ## COSMA8,
## DINE, etc.). MarkdownNodeParser respects these boundaries, so each
chunk corresponds to a coherent section instead of being chopped at
arbitrary sentence boundaries.

This typically:
  - Produces more chunks (one per heading section)
  - Each chunk is more topically coherent
  - Greatly improves retrieval for "what is X" / "tell me about X" queries
"""

import os
import shutil
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

OLLAMA_HOST = "http://127.0.0.1:11436"
INDEX_DIR   = os.path.expanduser("~/hpc-helpdesk/cosma_index")
DOCS_DIR    = os.path.expanduser("~/cosmadoc/docs/source")

Settings.llm = Ollama(model="llama3.2:3b", base_url=OLLAMA_HOST, request_timeout=180.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text", base_url=OLLAMA_HOST)

# Two-stage parsing:
# 1. MarkdownNodeParser splits at heading boundaries (## sections)
# 2. SentenceSplitter is used as a fallback to break up any section that's
#    too long for the embedding model (nomic-embed-text has ~8k context but
#    cleaner chunks improve retrieval).
md_parser = MarkdownNodeParser()
sentence_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)

print(f"Loading COSMA docs from {DOCS_DIR}...")
documents = SimpleDirectoryReader(
    input_dir=DOCS_DIR,
    required_exts=[".md", ".rst"],
    recursive=False,
).load_data()
print(f"Loaded {len(documents)} documents")

# Tag priority files (fixed: plain filenames, no markdown-link syntax)
priority_files = {"cosma.md", "faq.md", "cosma8.md", "facilities.md",
                  "slurm.md", "storage.md", "lhdctour.md"}
for doc in documents:
    fname = doc.metadata.get("file_name", "")
    is_priority = fname in priority_files
    doc.metadata["priority"] = "high" if is_priority else "normal"
    print(f"  {'[HIGH]' if is_priority else '      '} {fname}")

print("\nParsing with MarkdownNodeParser (heading-aware)...")
md_nodes = md_parser.get_nodes_from_documents(documents)
print(f"Markdown parser produced {len(md_nodes)} nodes")

# Second pass: any markdown section longer than the chunk_size gets split
# further. Short sections pass through unchanged.
print("Second pass: splitting any oversized sections...")
final_nodes = []
for node in md_nodes:
    if len(node.text) > 2000:   # roughly > chunk_size in chars
        sub_nodes = sentence_splitter.get_nodes_from_documents(
            [node]  # node is also a document for splitter purposes
        )
        # Preserve the heading metadata from the markdown parser
        for sn in sub_nodes:
            sn.metadata.update(node.metadata)
        final_nodes.extend(sub_nodes)
    else:
        final_nodes.append(node)

print(f"Final node count: {len(final_nodes)}")

print("\nBuilding vector index (embedding all nodes)...")
index = VectorStoreIndex(final_nodes, show_progress=True)

if os.path.exists(INDEX_DIR):
    shutil.rmtree(INDEX_DIR)
os.makedirs(INDEX_DIR)
index.storage_context.persist(persist_dir=INDEX_DIR)
print("Index rebuilt and saved successfully")