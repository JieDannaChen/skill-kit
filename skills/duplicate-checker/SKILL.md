---
name: skill-duplicate-checker
description: Scan all skills in the the skills repository and report pairs with overlapping descriptions or content, to help identify redundant skills.
metadata:
  category: IDE & Skills
---

# Skill Duplicate Checker

Detects redundant or overlapping skills by comparing every pair of `SKILL.md` files
found under the `skills/` directory. Two similarity metrics are computed per pair:

| Metric | Method | Weight |
|--------|--------|--------|
| Description similarity | `difflib.SequenceMatcher` ratio on frontmatter `description` strings | 40 % |
| Content similarity | Cosine similarity on word-frequency vectors of the full body text | 60 % |

Results are grouped into **HIGH** (>= 60 %) and **MODERATE** (30 - 59 %) duplication
bands and printed to stdout, ranked by combined score descending.

## When to Use

- Before adding a new skill — confirm no equivalent already exists.
- During periodic skill-library audits to identify merge or removal candidates.

## Runtime Requirements

- Python 3.9+ (stdlib only — no extra packages required)

## Usage

Run from anywhere inside the repo:

```bash
python3 skills/skill-duplicate-checker/scripts/check_duplicates.py
```

Optional flags:

```bash
# Adjust the lower threshold (default 0.30)
python3 skills/skill-duplicate-checker/scripts/check_duplicates.py --threshold 0.4

# Point at a different skills root
python3 skills/skill-duplicate-checker/scripts/check_duplicates.py --skills-dir /path/to/skills
```

## Output Format

```
Skills root : /repo/skills
Loaded 12 skills.

Analyzing 66 pairs...

============================================================
HIGH DUPLICATION  (combined score >= 60%)
============================================================

  [############........]  73.4%  |  network-monitor  <->  storage-health-check
    Description similarity : 48.6%
    Content similarity     : 88.2%
    Skill A : skills/network-monitor/SKILL.md
    Skill B : skills/storage-health-check/SKILL.md

------------------------------------------------------------
MODERATE DUPLICATION  (30% <= combined score < 60%)
------------------------------------------------------------

  [########............]  42.1%  |  task-tracker  <->  build-failure-analyzer
    Description similarity : 21.1%
    Content similarity     : 55.1%
    Skill A : skills/task-tracker/SKILL.md
    Skill B : skills/build-failure-analyzer/SKILL.md

Summary: 1 high, 1 moderate duplicate pair(s) found out of 66 total.
```

## Interpreting Results

- **HIGH (>= 60%)**: Strong overlap — skills likely duplicate each other. Consider
  merging them into a single skill or clearly differentiating their scope.
- **MODERATE (30-59%)**: Partial overlap — worth reviewing to see if shared sections
  can be extracted or if one skill should reference the other.
- **Score < threshold**: Not reported — normal level of shared vocabulary for a
  domain-specific registry.

## Implementation

- **Script**: `skills/skill-duplicate-checker/scripts/check_duplicates.py`
- All similarity logic uses Python stdlib (`difflib`, `collections`, `math`, `re`).
- The script auto-discovers the `skills/` directory by walking up from its own location.
