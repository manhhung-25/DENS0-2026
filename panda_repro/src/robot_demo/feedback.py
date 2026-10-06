"""Command-line technician feedback tool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .event_store import EventStore
from .faults import FAULTS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("artifacts/events.db"))
    parser.add_argument("--event-id", type=int)
    parser.add_argument("--label", choices=FAULTS)
    parser.add_argument("--joint", type=int, help="1-based joint number")
    parser.add_argument("--action", default="Inspected by technician")
    parser.add_argument("--status", choices=["confirmed", "rejected", "uncertain"], default="confirmed")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--confirmed-only", action="store_true")
    args = parser.parse_args()
    store = EventStore(args.db)
    if args.list:
        print(json.dumps(store.list_events(args.confirmed_only), indent=2))
        return
    if args.event_id is None or args.label is None or args.joint is None:
        parser.error("--event-id, --label and --joint are required unless --list is used")
    store.add_feedback(args.event_id, args.label, args.joint - 1, args.action, args.status)
    print(json.dumps(store.get_event(args.event_id), indent=2))


if __name__ == "__main__":
    main()

