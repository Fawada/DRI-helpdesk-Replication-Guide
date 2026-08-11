#!/usr/bin/env python3
"""
convert_docx.py — Convert a Word document to markdown for RAG ingestion.

Usage:
    python3 convert_docx.py --input your-docs.docx --output ./docs/

Converts heading styles to # / ## / ### markdown markers and preserves
body text. Output is one .md file per input .docx, saved to --output dir.

Part of the AI HPC Helpdesk replication framework.
https://github.com/Fawada/DRI-helpdesk-Replication-Guide
"""

import os
import sys
import argparse
from pathlib import Path


def convert_docx_to_md(input_path: Path, output_dir: Path) -> Path:
    """Convert a single .docx file to markdown. Returns the output path."""
    try:
        import docx
    except ImportError:
        sys.exit(
            "ERROR: python-docx is not installed.\n"
            "Run: pip install python-docx"
        )

    doc = docx.Document(str(input_path))
    lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue

        style = para.style.name
        if "Heading 1" in style:
            lines.append(f"# {text}")
        elif "Heading 2" in style:
            lines.append(f"## {text}")
        elif "Heading 3" in style:
            lines.append(f"### {text}")
        elif "Heading 4" in style:
            lines.append(f"#### {text}")
        else:
            lines.append(text)

    # Remove excessive blank lines (more than 2 consecutive)
    cleaned = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    output_path = output_dir / (input_path.stem + ".md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert Word documents to markdown for RAG ingestion."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input .docx file, or directory of .docx files."
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for .md files (will be created if needed)."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print details for each file converted."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect input files
    if input_path.is_dir():
        docx_files = sorted(input_path.glob("*.docx"))
        if not docx_files:
            sys.exit(f"ERROR: No .docx files found in {input_path}")
    elif input_path.is_file() and input_path.suffix == ".docx":
        docx_files = [input_path]
    else:
        sys.exit(f"ERROR: {input_path} is not a .docx file or directory.")

    print(f"Converting {len(docx_files)} file(s) to {output_dir}/")

    total_lines = 0
    for docx_path in docx_files:
        out = convert_docx_to_md(docx_path, output_dir)
        line_count = len(out.read_text().splitlines())
        total_lines += line_count
        if args.verbose:
            print(f"  {docx_path.name} -> {out.name} ({line_count} lines)")
        else:
            print(f"  {out.name} ({line_count} lines)")

    print(f"Done. {total_lines} total lines written to {output_dir}/")
    print(f"\nNext step — build the index:")
    print(f"  python3 ingest/ingest.py --docs-dir {output_dir} --index-dir ~/helpdesk-index/")


if __name__ == "__main__":
    main()
