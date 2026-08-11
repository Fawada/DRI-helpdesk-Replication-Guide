#!/usr/bin/env python3
"""
ask-cosma: AI helpdesk client for COSMA.

Submits a question to the helpdesk worker via shared filesystem, waits
for the answer, prints it, and asks for feedback.

Works from ANY node (login or compute) that can see the shared queue.

Usage:
  ask-cosma "How do I check my disk quota?"
  ask-cosma                           # interactive mode
"""

import os
import sys
import json
import time
import uuid
import socket
import getpass
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------
QUEUE_DIR     = os.environ.get("HELPDESK_QUEUE_DIR")
LOG_FILE      = os.environ.get("HELPDESK_LOG_FILE")
HEARTBEAT     = os.environ.get("HELPDESK_HEARTBEAT_FILE")
ADMIN_EMAIL   = os.environ.get("HELPDESK_ADMIN_EMAIL", "the helpdesk admin")
SUPPORT_EMAIL = os.environ.get("HELPDESK_SUPPORT_EMAIL", "cosma-support@durham.ac.uk")
MAX_LEN       = int(os.environ.get("HELPDESK_MAX_QUERY_LEN", "1000"))
POLL          = float(os.environ.get("HELPDESK_CLIENT_POLL_INTERVAL", "0.5"))
TIMEOUT_S     = float(os.environ.get("HELPDESK_CLIENT_TIMEOUT_S", "120"))
HEARTBEAT_FRESH_S = 60

if not all([QUEUE_DIR, LOG_FILE, HEARTBEAT]):
    print("ERROR: ask-cosma is not configured.", file=sys.stderr)
    print("Make sure config.sh has been sourced.", file=sys.stderr)
    sys.exit(3)

QUEUE_DIR     = Path(QUEUE_DIR)
HEARTBEAT     = Path(HEARTBEAT)
REQUESTS_DIR  = QUEUE_DIR / "requests"
RESPONSES_DIR = QUEUE_DIR / "responses"

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def banner():
    print()
    print("─" * 70)
    print("  COSMA AI Helpdesk (experimental)")
    print("  Answers may be incorrect. Always verify before running commands.")
    print(f"  Report issues: {ADMIN_EMAIL}")
    print("─" * 70)


def worker_alive():
    try:
        return time.time() - HEARTBEAT.stat().st_mtime < HEARTBEAT_FRESH_S
    except FileNotFoundError:
        return False


def offline_message():
    print()
    print("⚠  The COSMA Helpdesk worker appears to be offline.")
    print()
    print(f"   Please email {ADMIN_EMAIL} and ask them to restart it.")
    print(f"   For HPC help, contact {SUPPORT_EMAIL}.")
    print()


def get_query():
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    banner()
    print()
    print("Type your COSMA question (empty line to cancel):")
    try:
        return input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def submit(query):
    rid = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
           + "_" + uuid.uuid4().hex[:8])
    req = {
        "id": rid,
        "user": getpass.getuser(),
        "node": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
    }
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REQUESTS_DIR / f"{rid}.json.tmp"
    final = REQUESTS_DIR / f"{rid}.json"
    with tmp.open("w") as f:
        json.dump(req, f)
    tmp.rename(final)
    return rid, RESPONSES_DIR / f"{rid}.json"


def wait_for_response(response_path, timeout_s):
    start = time.time()
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    response_name = response_path.name
    response_dir = response_path.parent
    while time.time() - start < timeout_s:
        # Force NFS attribute cache refresh by listing the directory.
        # response_path.exists() alone hits the cache and may return stale
        # "doesn't exist" for many seconds even after the worker has written
        # the file. listdir() forces a server round-trip.
        try:
            files_in_dir = os.listdir(response_dir)
        except OSError:
            files_in_dir = []
        if response_name in files_in_dir:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            with response_path.open() as f:
                return json.load(f)

def feedback(rid, query):
    print()
    try:
        choice = input("Was this helpful? [g]ood / [b]ad / [s]kip: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice not in ("g", "b", "good", "bad"):
        return
    flag = "GOOD" if choice.startswith("g") else "BAD"
    detail = ""
    if flag == "BAD":
        try:
            detail = input("(optional) what was wrong? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} | "
                    f"FEEDBACK | id={rid} | flag={flag} | "
                    f"user={getpass.getuser()} | "
                    f"query={query!r} | detail={detail!r}\n")
        print("Thanks - feedback recorded.")
    except Exception as e:
        print(f"(could not write feedback: {e})")


def cleanup(p):
    try:
        p.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    query = get_query()
    if not query:
        print("No question entered.")
        sys.exit(2)
    if len(query) > MAX_LEN:
        print(f"Query too long ({len(query)} chars, max {MAX_LEN}).")
        sys.exit(2)

    if not worker_alive():
        offline_message()
        sys.exit(1)

    if len(sys.argv) > 1:
        banner()
        print(f"\nQ: {query}")

    rid, response_path = submit(query)
    response = wait_for_response(response_path, TIMEOUT_S)

    if response is None:
        print(f"⚠  No response after {int(TIMEOUT_S)}s.")
        if worker_alive():
            print("   Worker is alive but slow. Try again or shorten your "
                  "question.")
        else:
            offline_message()
        sys.exit(1)

    if not response.get("ok"):
        print(f"⚠  {response.get('error', 'Unknown error')}")
        cleanup(response_path)
        sys.exit(1)

    print()
    print("Answer:")
    print("─" * 70)
    print(response["answer"])
    print("─" * 70)
    if response.get("sources"):
        files = sorted({s["file"] for s in response["sources"]})
        print(f"Sources: {', '.join(files)}")
    elapsed = response.get("elapsed_s", 0)
    print(f"({elapsed:.1f}s, model: {response.get('model', '?')})")

    feedback(rid, query)
    cleanup(response_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
