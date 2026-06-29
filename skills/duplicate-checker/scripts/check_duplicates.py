#!/usr/bin/env python3
"""
check_duplicates.py - Scan all SKILL.md files in the the skills registry skills/
directory and report pairs that have suspiciously high similarity.

Similarity is measured with two complementary metrics:
  1. Description similarity  - difflib.SequenceMatcher on the frontmatter
                                `description` field (weight 40 %)
  2. Content similarity      - cosine similarity on word-frequency vectors
                                of the full body text (weight 60 %)

stdlib only; no external packages required.
"""

import argparse
import math
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
_FM_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)[ \t]*:[ \t]*(.*)")
_WORD_RE = re.compile(r"\b[a-z0-9_\-]{2,}\b")
_SUB_SKILLS_SECTION_RE = re.compile(r"##\s+Sub-skills\b(.*?)(?=\n##|\Z)", re.DOTALL | re.IGNORECASE)
_TABLE_SKILL_NAME_RE = re.compile(r"\|\s*`([^`]+)`")


def _parse_frontmatter(text: str) -> tuple:
    """Return (frontmatter_dict, body_text)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        km = _FM_KEY_RE.match(line)
        if km:
            fm[km.group(1)] = km.group(2).strip()
    return fm, text[m.end():]


def _extract_sub_skill_names(body: str) -> set:
    """Return the set of skill names declared in a '## Sub-skills' table."""
    m = _SUB_SKILLS_SECTION_RE.search(body)
    if not m:
        return set()
    names = set()
    for line in m.group(1).splitlines():
        for name in _TABLE_SKILL_NAME_RE.findall(line):
            name = name.strip()
            if "/" not in name:
                names.add(name)
    return names


def parse_skill_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(text)
    body = body.strip()
    return {
        "path": path,
        "name": fm.get("name", path.parent.name),
        "description": fm.get("description", ""),
        "body": body,
        "sub_skills": _extract_sub_skill_names(body),
    }


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _word_freq(text: str) -> Counter:
    return Counter(_WORD_RE.findall(text.lower()))


def cosine_similarity(text_a: str, text_b: str) -> float:
    fa, fb = _word_freq(text_a), _word_freq(text_b)
    common = set(fa) & set(fb)
    if not common:
        return 0.0
    dot = sum(fa[w] * fb[w] for w in common)
    mag_a = math.sqrt(sum(v * v for v in fa.values()))
    mag_b = math.sqrt(sum(v * v for v in fb.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def desc_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def combined_score(skill_a: dict, skill_b: dict) -> tuple:
    d = desc_similarity(skill_a["description"], skill_b["description"])
    c = cosine_similarity(skill_a["body"], skill_b["body"])
    score = 0.4 * d + 0.6 * c
    return score, d, c


# ---------------------------------------------------------------------------
# Sub-skill relationship helpers
# ---------------------------------------------------------------------------

def build_excluded_pairs(skills: list) -> set:
    """Return a set of frozensets({name_a, name_b}) that should be skipped
    because one skill is a declared sub-skill of the other."""
    excluded = set()
    for skill in skills:
        for child_name in skill["sub_skills"]:
            excluded.add(frozenset({skill["name"], child_name}))
    return excluded


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_skills_root(start: Path):
    """Walk upward from *start* to find the 'skills/' directory."""
    for candidate in [start, *start.parents]:
        skills = candidate / "skills"
        if skills.is_dir():
            return skills
    return None


def load_all_skills(skills_root: Path) -> list:
    skills = []
    for md in sorted(skills_root.glob("*/SKILL.md")):
        try:
            skills.append(parse_skill_file(md))
        except Exception as exc:
            print(f"  WARN: could not parse {md}: {exc}", file=sys.stderr)
    return skills


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def report(pairs: list, label: str, skills_root: Path, sep: str = "=") -> None:
    if not pairs:
        return
    print()
    print(sep * 60)
    print(label)
    print(sep * 60)
    for p in pairs:
        print(
            f"\n  {_bar(p['combined'])}  {p['combined']:.1%}"
            f"  |  {p['name_a']}  <->  {p['name_b']}"
        )
        print(f"    Description similarity : {p['desc']:.1%}")
        print(f"    Content similarity     : {p['content']:.1%}")
        rel_a = p["path_a"].relative_to(skills_root).as_posix()
        rel_b = p["path_b"].relative_to(skills_root).as_posix()
        print(f"    Skill A : skills/{rel_a}")
        print(f"    Skill B : skills/{rel_b}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report duplicate/overlapping skills in the the skills registry repo."
    )
    parser.add_argument(
        "--skills-dir",
        metavar="PATH",
        help="Path to the skills/ directory (auto-detected if omitted).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.40,
        metavar="0.0-1.0",
        help="Minimum combined score to report (default: 0.30).",
    )
    parser.add_argument(
        "--high",
        type=float,
        default=0.70,
        metavar="0.0-1.0",
        help="Score at or above which a pair is HIGH duplication (default: 0.60).",
    )
    args = parser.parse_args()

    if args.skills_dir:
        skills_root = Path(args.skills_dir).resolve()
        if not skills_root.is_dir():
            print(f"ERROR: {skills_root} is not a directory.", file=sys.stderr)
            sys.exit(1)
    else:
        skills_root = find_skills_root(Path(__file__).resolve().parent)
        if skills_root is None:
            print(
                "ERROR: Could not auto-detect skills/ directory. "
                "Use --skills-dir to specify it.",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Skills root : {skills_root}")

    skills = load_all_skills(skills_root)
    n = len(skills)
    if n < 2:
        print(f"Only {n} skill(s) found - need at least 2 to compare.")
        return

    print(f"Loaded {n} skills.")
    excluded_pairs = build_excluded_pairs(skills)
    if excluded_pairs:
        excluded_names = [
            " <-> ".join(sorted(p)) for p in sorted(excluded_pairs, key=sorted)
        ]
        print(f"Skipping {len(excluded_pairs)} parent<->sub-skill pair(s):")
        for name in excluded_names:
            print(f"  - {name}")
    total_pairs = n * (n - 1) // 2
    effective_pairs = total_pairs - len(excluded_pairs)
    print(f"\nAnalyzing {effective_pairs} pairs (skipped {len(excluded_pairs)} sub-skill pairs)...\n")

    high_pairs = []
    moderate_pairs = []

    for i in range(n):
        for j in range(i + 1, n):
            sa, sb = skills[i], skills[j]
            if frozenset({sa["name"], sb["name"]}) in excluded_pairs:
                continue
            score, d, c = combined_score(sa, sb)
            if score < args.threshold:
                continue
            entry = {
                "combined": score,
                "desc": d,
                "content": c,
                "name_a": sa["name"],
                "name_b": sb["name"],
                "path_a": sa["path"],
                "path_b": sb["path"],
            }
            if score >= args.high:
                high_pairs.append(entry)
            else:
                moderate_pairs.append(entry)

    high_pairs.sort(key=lambda x: x["combined"], reverse=True)
    moderate_pairs.sort(key=lambda x: x["combined"], reverse=True)

    if not high_pairs and not moderate_pairs:
        print(f"No duplicate pairs found above threshold {args.threshold:.0%}.")
        return

    report(
        high_pairs,
        f"HIGH DUPLICATION  (combined score >= {args.high:.0%})",
        skills_root,
    )
    report(
        moderate_pairs,
        f"MODERATE DUPLICATION  ({args.threshold:.0%} <= combined score < {args.high:.0%})",
        skills_root,
        sep="-",
    )

    print(
        f"\nSummary: {len(high_pairs)} high, {len(moderate_pairs)} moderate "
        f"duplicate pair(s) found out of {effective_pairs} compared pairs "
        f"({len(excluded_pairs)} sub-skill pairs excluded)."
    )


if __name__ == "__main__":
    main()
