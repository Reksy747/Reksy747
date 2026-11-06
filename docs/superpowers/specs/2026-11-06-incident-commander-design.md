# Incident Commander — playable DevOps profile README

Date: 2026-11-06 · Repo: `Reksy747/Reksy747` (default branch `master`)

## Intent

Make the GitHub profile README say plainly that Reksy is a **DevOps engineer**, and make it **playable, funny and charming**. Visitors play a turn-based game inside the README. The game itself is a GitHub Actions pipeline, so playing it demonstrates the skill.

Success: a visitor can click a move, press Submit once, and about 30 seconds later see the board change with a joke reply and their username in the log. The README reads as a DevOps engineer's profile at a glance.

Constraints: no paid services, no hosting, GitHub Actions + Python 3 standard library only. Existing links (website, Twitter, LinkedIn, email) are kept.

Out of scope: real-time or arcade play, GitHub Pages, leaderboards beyond the hall of fame, the old pipeline SVG, the Spotify block, the web-dev icon wall.

## README layout (top to bottom)

1. Terminal banner: `reksy@prod:~$ whoami` → `DevOps Engineer`.
2. Game board (between `<!--START_SECTION:game-->` and `<!--END_SECTION:game-->`): incident name, emoji HP bar with numbers, "N days since last incident was resolved", last 5 moves (`@user — move — outcome — joke`), hall of fame (last 10 winners).
3. Move buttons (static, outside the markers): one badge link per move.
4. About, links (website, Twitter, LinkedIn, email), one-line stack: Git, Docker, Kubernetes, Terraform, Jenkins, GitHub Actions, AWS, GCP, plus "also: Java, Laravel, MySQL, MongoDB".

Button URL: `https://github.com/Reksy747/Reksy747/issues/new?title=play%3A+<move>&body=Just+press+Submit+new+issue.`

## Game rules

State file `state/game.json`:

```
{ "incident": {"name": str, "hp": int, "max_hp": int},
  "yaml_stack": int,
  "log": [ {"user","move","text"} ... ],   // newest first, max 5
  "hall_of_fame": [ {"user","incident","date"} ... ],  // newest first, max 10
  "last_resolved": "YYYY-MM-DD" }
```

Randomness: `random.Random(issue_number)`, so any move is reproducible.

| Move | Effect |
|---|---|
| `rollback` | 18 damage |
| `restart-it` | 5–10 damage; 8% chance it fixes everything (damage = remaining HP) |
| `blame-dns` | 0 damage, joke only |
| `add-yaml` | `min(4 + 4 * yaml_stack, 30)` damage, then `yaml_stack += 1` |
| `deploy-friday` | 50%: 35 damage; 50%: outage heals 20 (capped at `max_hp`) |

Each move has 3 joke replies; one is picked with the seeded RNG.

Win (hp ≤ 0): prepend `{user, incident, today}` to the hall of fame, set `last_resolved` to today, reset `yaml_stack` to 0, and start a new incident chosen from the pool (never the same as the one just solved). Incident pool (name, max HP): "Certificate expired at 3am" 80, "The intern ran `rm -rf`" 100, "DNS is down (it's always DNS)" 90, "Disk full of logs nobody reads" 70, "Kubernetes pods in CrashLoopBackOff" 110, "Terraform wants to destroy everything" 120.

Days since last incident = today − `last_resolved`, in whole days.

## Move processing and safety

Trigger: workflow `.github/workflows/play.yml` on `issues: [opened]`.

1. Read the issue **title** (and number, author login) through environment variables, never interpolated into shell. The body is ignored.
2. Validate: title must match `play: <move>` (trimmed, case-insensitive) where `<move>` is one of the five moves; author login must match `^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$`.
3. Reject (comment with a polite joke, close the issue, no state change, no commit) when the title or move is invalid, or when the author made the most recent logged move.
4. Otherwise apply the move, rewrite `state/game.json` and the README game section, commit as `github-actions[bot]`, push, then comment the reply and close the issue.

Concurrency: `concurrency: group: game, cancel-in-progress: false` so moves are processed one at a time. Permissions: `contents: write`, `issues: write`. Python's script writes the reply to a file; `gh issue comment/close` posts it with `GITHUB_TOKEN`.

## Code layout

- `scripts/game.py`: pure `apply_move(state, move, user, seed, today) -> (state, reply)`, `render(state) -> str`, `update_readme(text, board) -> str`, and a small `main()` that reads env vars, calls the above, and writes files.
- `state/game.json`: initial state with the first incident and `last_resolved` set to the commit date.
- `tests/test_game.py`: `unittest`.
- `.github/workflows/play.yml`: the workflow above.
- Deleted: `.github/workflows/update-readme.yml` (replaced), plus `scripts/build_pipeline.py` and `assets/pipeline.svg` from the earlier abandoned design.
- `README.md`: rewritten per the layout.

## Testing

Unit tests, run locally with the bundled Python: each move's damage and bounds, the heal cap, `yaml_stack` growth, win and reset (hall of fame, new incident differs, `last_resolved`), same-user rejection, invalid-title rejection, login validation, seeded reproducibility, and README marker replacement (idempotent, other text untouched).

The workflow only runs on GitHub, so it cannot be tested locally. After merge to `master` (issue-triggered workflows run only from the default branch), open one real `play: rollback` issue and confirm the board updates.

## Known limits

- A visitor must be logged in to GitHub and press Submit once; updates take about 30 seconds.
- Anyone can play, so the same-user rule is the only spam control. Revisit with a per-user cooldown if the repo is abused.
