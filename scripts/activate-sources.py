#!/usr/bin/env python3
"""Set sources in catalog/sources.json to "active" (or back to "pending_review").

    scripts/activate-sources.py srf-news bbc-world     activate these ids
    scripts/activate-sources.py --all                  activate every candidate
    scripts/activate-sources.py --reset                everything back to pending_review

Activating a source is an editorial decision: read catalog/README.md first.
"""
import json
import sys
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "catalog" / "sources.json"
sources = json.loads(path.read_text(encoding="utf-8"))
args = sys.argv[1:]
known = {s["id"] for s in sources}
unknown = [a for a in args if not a.startswith("--") and a not in known]
if not args or unknown:
    sys.exit(f"usage: {Path(__file__).name} [--all | --reset | <id>...]; known ids: {', '.join(sorted(known))}")
for source in sources:
    if source["status"] == "blocked":
        continue
    if "--reset" in args:
        source["status"] = "pending_review"
    elif "--all" in args or source["id"] in args:
        source["status"] = "active"
path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for source in sources:
    print(f"{source['status']:15} {source['id']}")
