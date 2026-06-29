# Skill Kit

Management tools for AI skill registries. Score, rank, and deduplicate skills so the best ones get used first.

## Skills

### 1. Scorer (`skills/scorer/`)

Maintains a scoring and ranking system for skills. When multiple skills could satisfy a request, the agent picks the one with the highest weight.

**Weight formula:**
```
weight = avg_rating + log2(1 + usage_count) * 0.5
```

Skills that get used more and rated higher naturally rise to the top.

```bash
# List all skills ranked by weight
uv run skills/scorer/scripts/scorer.py list

# Record that a skill was used
uv run skills/scorer/scripts/scorer.py record my-skill

# Rate a skill (1-5)
uv run skills/scorer/scripts/scorer.py rate my-skill 5

# Show details for one skill
uv run skills/scorer/scripts/scorer.py show my-skill

# Sync: discover new skills, remove stale entries
uv run skills/scorer/scripts/scorer.py sync
```

**Auto-sync:** Every command automatically scans the `skills/` directory to add new skills and remove deleted ones.

**Output formats:**
```bash
# Table (default)
uv run skills/scorer/scripts/scorer.py list
#  Rank  Skill              Weight  Avg Rating  Uses  Ratings
#  1     my-best-skill       4.50    4.50         12       4
#  2     another-skill       3.82    3.50          5       2

# JSON (for programmatic use)
uv run skills/scorer/scripts/scorer.py list --format json
```

### 2. Duplicate Checker (`skills/duplicate-checker/`)

Detects overlapping or redundant skills by comparing every pair of `SKILL.md` files.

**How it works:**
- **Description similarity** (40% weight) — `difflib.SequenceMatcher` on frontmatter descriptions
- **Content similarity** (60% weight) — Cosine similarity on word-frequency vectors of the full Markdown body

```bash
# Scan for duplicates (default threshold: 40%)
uv run skills/duplicate-checker/scripts/check_duplicates.py

# Custom thresholds
uv run skills/duplicate-checker/scripts/check_duplicates.py \
  --threshold 0.30 \
  --high 0.60

# Point at a specific skills directory
uv run skills/duplicate-checker/scripts/check_duplicates.py \
  --skills-dir /path/to/your/skills/
```

**Smart exclusions:** Parent skills with a `## Sub-skills` section automatically have their children excluded from duplicate detection (parent-child overlap is expected).

**Output example:**
```
=== Skill Overlap Report ===
Scanned 25 skills, found 2 overlapping pairs

HIGH (likely duplicates):
  network-monitor <-> storage-health-check
    Combined: 0.72 (desc: 0.65, content: 0.77)

MODERATE (worth reviewing):
  task-tracker <-> build-failure-analyzer
    Combined: 0.45 (desc: 0.38, content: 0.50)
```

## Quick Start

```bash
git clone https://github.com/JieDannaChen/skill-kit.git

# See your skill rankings
uv run skills/scorer/scripts/scorer.py list

# Check for duplicate skills
uv run skills/duplicate-checker/scripts/check_duplicates.py

# Or install as skills (openskills)
npx openskills install https://github.com/JieDannaChen/skill-kit.git
```

## Project Structure

```
skill-kit/
├── README.md
├── LICENSE
├── skills/
│   ├── scorer/                    # Skill scoring and ranking
│   │   ├── SKILL.md               # Skill definition
│   │   ├── scores.json            # Score database (auto-populated)
│   │   └── scripts/
│   │       └── scorer.py          # CLI: list, record, rate, show, sync
│   └── duplicate-checker/         # Skill overlap detection
│       ├── SKILL.md               # Skill definition
│       └── scripts/
│           └── check_duplicates.py  # CLI: scan and report
```

## Integration with Agent Workflows

Add to your project's `AGENTS.md` or skill selection protocol:

```markdown
### Skill Selection Protocol

When multiple skills could satisfy a user request:
1. Query rankings: `uv run skills/scorer/scripts/scorer.py list --format json`
2. Prefer higher weight among matching candidates
3. After invocation: `uv run skills/scorer/scripts/scorer.py record <skill-name>`
4. After user feedback: `uv run skills/scorer/scripts/scorer.py rate <skill-name> <1-5>`
```

## Zero Dependencies

Both tools use **Python standard library only** — no pip install needed. Just run with `python3` or `uv run`.

## Contributing

Contributions welcome! Please fork, branch, and submit a PR.

## License

MIT — see [LICENSE](LICENSE) for details.
