#!/usr/bin/env python3
"""Skill Scorer – score and weight skills in the the skills registry.

Usage:
    scorer.py list [--format json|table]
    scorer.py record <skill>
    scorer.py rate <skill> <rating>
    scorer.py show <skill>
    scorer.py reset <skill>
    scorer.py sync
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_SCORER_DIR = SCRIPT_DIR.parent
SCORES_FILE = SKILL_SCORER_DIR / "scores.json"
SKILLS_ROOT = SKILL_SCORER_DIR.parent  # skills/


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_scores() -> dict:
    """Return the scores dict, creating the file if missing."""
    if SCORES_FILE.exists():
        with open(SCORES_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_scores(data: dict) -> None:
    with open(SCORES_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _ensure_skill(data: dict, name: str) -> dict:
    """Return the entry for *name*, creating a blank one if needed."""
    if name not in data:
        data[name] = {
            "usage_count": 0,
            "total_rating": 0.0,
            "rating_count": 0,
        }
    return data[name]


def _compute_weight(entry: dict) -> float:
    """Compute the weight for a single skill entry."""
    rc = entry.get("rating_count", 0)
    avg = entry["total_rating"] / rc if rc > 0 else 3.0
    bonus = math.log2(1 + entry.get("usage_count", 0)) * 0.5
    return round(avg + bonus, 4)


def _discover_skills() -> list[str]:
    """Return sorted skill folder names that contain a SKILL.md."""
    names: list[str] = []
    if not SKILLS_ROOT.is_dir():
        return names
    for child in sorted(SKILLS_ROOT.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            names.append(child.name)
    return names


def _auto_sync() -> None:
    """Silently add new skills and remove stale entries from scores.json.

    Called on every command so the database stays in sync with the
    skills/ directory after git pull, branch switch, etc.
    """
    discovered = set(_discover_skills())
    if not discovered:
        return
    data = _load_scores()
    changed = False
    # Add newly discovered skills
    for name in discovered:
        if name not in data:
            _ensure_skill(data, name)
            changed = True
    # Remove entries whose skill folder no longer exists
    stale = [name for name in data if name not in discovered]
    for name in stale:
        del data[name]
        changed = True
    if changed:
        _save_scores(data)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> None:
    data = _load_scores()
    rows = []
    for name, entry in data.items():
        w = _compute_weight(entry)
        rc = entry.get("rating_count", 0)
        avg = entry["total_rating"] / rc if rc > 0 else None
        rows.append(
            {
                "skill": name,
                "weight": w,
                "usage_count": entry.get("usage_count", 0),
                "avg_rating": round(avg, 2) if avg is not None else None,
                "rating_count": rc,
            }
        )
    rows.sort(key=lambda r: r["weight"], reverse=True)

    fmt = getattr(args, "format", "table")
    if fmt == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        # simple table
        header = f"{'Skill':<30} {'Weight':>8} {'Uses':>6} {'AvgRate':>8} {'#Rates':>7}"
        print(header)
        print("-" * len(header))
        for r in rows:
            avg_str = f"{r['avg_rating']:.2f}" if r["avg_rating"] is not None else "  n/a"
            print(
                f"{r['skill']:<30} {r['weight']:>8.4f} {r['usage_count']:>6} {avg_str:>8} {r['rating_count']:>7}"
            )


def cmd_record(args: argparse.Namespace) -> None:
    data = _load_scores()
    entry = _ensure_skill(data, args.skill)
    entry["usage_count"] = entry.get("usage_count", 0) + 1
    _save_scores(data)
    w = _compute_weight(entry)
    print(f"Recorded usage for '{args.skill}'. usage_count={entry['usage_count']}, weight={w}")


def cmd_rate(args: argparse.Namespace) -> None:
    rating = float(args.rating)
    if not 1 <= rating <= 5:
        print("Error: rating must be between 1 and 5.", file=sys.stderr)
        sys.exit(1)
    data = _load_scores()
    entry = _ensure_skill(data, args.skill)
    entry["total_rating"] = entry.get("total_rating", 0.0) + rating
    entry["rating_count"] = entry.get("rating_count", 0) + 1
    _save_scores(data)
    avg = entry["total_rating"] / entry["rating_count"]
    w = _compute_weight(entry)
    print(
        f"Rated '{args.skill}' with {rating:.1f}. "
        f"avg_rating={avg:.2f}, weight={w}"
    )


def cmd_show(args: argparse.Namespace) -> None:
    data = _load_scores()
    if args.skill not in data:
        print(f"No scores recorded for '{args.skill}'.")
        return
    entry = data[args.skill]
    w = _compute_weight(entry)
    rc = entry.get("rating_count", 0)
    avg = entry["total_rating"] / rc if rc > 0 else None
    print(f"Skill:        {args.skill}")
    print(f"Usage count:  {entry.get('usage_count', 0)}")
    print(f"Avg rating:   {f'{avg:.2f}' if avg is not None else 'n/a'}")
    print(f"Rating count: {rc}")
    print(f"Weight:       {w}")


def cmd_reset(args: argparse.Namespace) -> None:
    data = _load_scores()
    if args.skill in data:
        del data[args.skill]
        _save_scores(data)
        print(f"Reset scores for '{args.skill}'.")
    else:
        print(f"No scores found for '{args.skill}'.")


def cmd_sync(_args: argparse.Namespace) -> None:
    data = _load_scores()
    discovered = _discover_skills()
    added = 0
    for name in discovered:
        if name not in data:
            _ensure_skill(data, name)
            added += 1
    _save_scores(data)
    print(f"Synced. {len(discovered)} skills in registry, {added} newly added.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill Scorer")
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List ranked skills")
    p_list.add_argument("--format", choices=["json", "table"], default="table")

    # record
    p_rec = sub.add_parser("record", help="Record a skill invocation")
    p_rec.add_argument("skill")

    # rate
    p_rate = sub.add_parser("rate", help="Rate a skill (1-5)")
    p_rate.add_argument("skill")
    p_rate.add_argument("rating")

    # show
    p_show = sub.add_parser("show", help="Show details for a skill")
    p_show.add_argument("skill")

    # reset
    p_reset = sub.add_parser("reset", help="Reset a skill's scores")
    p_reset.add_argument("skill")

    # sync
    sub.add_parser("sync", help="Sync with skills directory")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    _auto_sync()

    dispatch = {
        "list": cmd_list,
        "record": cmd_record,
        "rate": cmd_rate,
        "show": cmd_show,
        "reset": cmd_reset,
        "sync": cmd_sync,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
