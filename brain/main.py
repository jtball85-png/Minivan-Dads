"""CLI entrypoint for the brain. Subcommands are filled in incrementally
(status, ask, ingest, meeting, directive) — see project-context.md for
build order."""

import argparse


def cli() -> None:
    parser = argparse.ArgumentParser(prog="brain", description="Minivan Dads COO")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show the company dashboard")

    args = parser.parse_args()

    if args.command == "status":
        print("brain status: not yet implemented")
