"""CLI: python -m agent.cli <task> [--auto-approve]

Without --auto-approve the CLI shows the diff and asks you to approve the file write.
"""

import argparse
import json

from agent import runner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--auto-approve", action="store_true")
    args = ap.parse_args()

    out = runner.start(args.task)
    while out["status"] == "awaiting_approval":
        a = out["approval"]
        print(f"\n=== Approval needed: {a['action']}\n{a['diff']}\nCoder: {a['explanation']}\nReviewer: {a['reviewer']}")
        ok = True if args.auto_approve else input("Approve? [y/N] ").strip().lower() == "y"
        out = runner.resume(out["run_id"], ok, by="cli-auto" if args.auto_approve else "cli-human")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
