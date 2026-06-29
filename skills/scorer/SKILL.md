---
name: skill-scorer
description: Score and weight skills so that higher-rated skills are preferred when the agent selects which skill to invoke. Use this skill to record feedback, view rankings, or adjust skill weights.
metadata:
  category: IDE & Skills
---

# Skill Scorer

Maintain a score/weight for every skill in the registry. When multiple skills
match a user request, the agent **SHOULD** prefer the skill with the higher
weight. This skill provides a CLI to record usage, collect user feedback, and
output a ranked skill list.

## How scoring works

Each skill entry in `scores.json` tracks:

| Field | Type | Description |
|-------|------|-------------|
| `usage_count` | int | How many times the skill has been invoked |
| `total_rating` | float | Sum of all user ratings (1-5 scale) |
| `rating_count` | int | Number of ratings received |
| `weight` | float | Computed weight used for ranking |

**Weight formula:**

```
avg_rating  = total_rating / rating_count   (default 3.0 if unrated)
usage_bonus = log2(1 + usage_count) * 0.5
weight      = avg_rating + usage_bonus
```

Skills with higher `weight` should be prioritized by the agent.

## Runtime requirements

- Python 3.9+

No external dependencies — uses only the standard library.

## Capabilities

All commands are run from the repository root (or use the full path to the
script). The scores database is stored at
`skills/skill-scorer/scores.json`.

### List ranked skills

```bash
python3 skills/skill-scorer/scripts/scorer.py list
```

Output is a table sorted by weight (descending). Use `--format json` to get
machine-readable output:

```bash
python3 skills/skill-scorer/scripts/scorer.py list --format json
```

### Record a skill invocation

Call this after successfully using a skill so its usage count increases:

```bash
python3 skills/skill-scorer/scripts/scorer.py record <skill-name>
```

### Rate a skill

Provide a rating from 1 (poor) to 5 (excellent):

```bash
python3 skills/skill-scorer/scripts/scorer.py rate <skill-name> <1-5>
```

### Show details for one skill

```bash
python3 skills/skill-scorer/scripts/scorer.py show <skill-name>
```

### Reset a skill's scores

```bash
python3 skills/skill-scorer/scripts/scorer.py reset <skill-name>
```

### Sync with registry

Scan the `skills/` directory and add any new skills that are missing from
`scores.json` (existing entries are preserved):

```bash
python3 skills/skill-scorer/scripts/scorer.py sync
```

## Weight update workflow

Weights are updated by two signals:

### Signal 1 — Usage (automatic)

Every time a skill is invoked, the agent runs `record` to bump its usage count.
More usage → higher `log2` bonus → higher weight.

```
invoke skill "my-skill"
  └─→ scorer.py record my-skill
       └─→ usage_count: 0 → 1, weight: 3.0 → 3.5
```

### Signal 2 — User rating (explicit)

After a skill completes, the agent asks the user to rate it (1-5). Good ratings
push the average up; bad ratings pull it down.

```
agent: "How useful was this skill? (1-5)"
user:  "5"
  └─→ scorer.py rate my-skill 5
       └─→ avg_rating: 5.0, weight: 5.5
```

### Weight progression example

| Event | usage_count | avg_rating | weight |
|-------|:-----------:|:----------:|:------:|
| Initial (no data) | 0 | 3.0 (default) | 3.0 |
| 1st use | 1 | 3.0 | 3.5 |
| User rates 5 | 1 | 5.0 | 5.5 |
| 2nd use | 2 | 5.0 | 5.79 |
| User rates 4 | 2 | 4.5 | 5.29 |
| 10th use | 10 | 4.5 | 6.23 |

## Agent integration

The protocol is defined in the repo-level `AGENTS.md`. In summary:

```
User request
  │
  ├─ 1+ candidate skills match?
  │     ├─ Only 1 → use it directly
  │     └─ Multiple → scorer.py list --format json → pick highest weight
  │
  ├─ Execute the skill
  │
  ├─ scorer.py record <skill-name>        ← always
  │
  └─ Ask user: "How useful? (1-5)"        ← always
        └─ scorer.py rate <skill-name> N  ← if user responds
```

This creates a **positive feedback loop**: good skills get used more → get rated
higher → get selected more often. Poor skills naturally sink in the ranking.
