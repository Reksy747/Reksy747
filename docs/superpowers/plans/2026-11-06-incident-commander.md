# Incident Commander Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the profile README with a DevOps-engineer page containing a turn-based incident game driven by GitHub issues and Actions.

**Architecture:** One pure-logic Python module (`scripts/game.py`) holds rules, rendering and README patching; a thin `main()` reads env vars and writes files. A workflow triggered by new issues runs it, commits, then comments and closes the issue.

**Tech Stack:** Python 3 standard library (`unittest`, `random`, `re`, `json`, `datetime`), GitHub Actions, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-11-06-incident-commander-design.md`

## Global Constraints

- Python 3 standard library only; no pip installs.
- Run Python locally with `PY="/c/Users/Reksy/AppData/Local/hermes/tools/python-3.14.9+20261021-win32-x64/python.exe"` (the Store shims on PATH do not work). Tests: `"$PY" -m unittest discover -s tests -v` from the repo root; tests import with `sys.path` insert of `scripts/`.
- Moves, exactly: `rollback`, `restart-it`, `blame-dns`, `add-yaml`, `deploy-friday`.
- Randomness only via `random.Random(seed)` where seed = issue number.
- The issue body is never read; the title only reaches Python through an environment variable, never interpolated into shell.
- Login regex: `^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$`.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Repo `Reksy747/Reksy747`, default branch `master`. Keep website, Twitter, LinkedIn and email links.

## Review Focus

1. Title variants: `"  Play:   Rollback "` is accepted; `"play: rollback; rm -rf /"`, an empty title and a 500-character title are rejected without raising. (Task 1)
2. Same-user rule compares logins case-insensitively (GitHub logins are case-insensitive). (Task 1)
3. Damage past 0 HP never shows negative HP; `deploy-friday` heal never exceeds `max_hp`. (Task 1)
4. A fresh state with an empty log and empty hall of fame renders without error. (Task 2)
5. `update_readme` on text missing the markers raises `ValueError` instead of silently doing nothing, so the workflow fails loudly rather than committing no change. (Task 2)

---

### Task 1: Game rules

**Files:**
- Create: `scripts/game.py` (rules part), `tests/test_game.py`

**Interfaces:**
- Produces:
  - `MOVES: tuple[str, ...]` (the five moves, order as in Global Constraints)
  - `INCIDENTS: list[tuple[str, int]]` (name, max_hp): the six from the spec
  - `initial_state(today: date) -> dict` (spec state shape; first incident "Certificate expired at 3am", hp = max_hp, `last_resolved = today.isoformat()`)
  - `parse_title(title: str) -> str | None` (returns the move or None)
  - `valid_user(login: str) -> bool`
  - `validate(state: dict, title: str, user: str) -> tuple[str | None, str | None]` returning `(move, None)` or `(None, rejection_message)`; rejects bad title, bad login, or `user` equal (case-insensitive) to `state["log"][0]["user"]`
  - `apply_move(state: dict, move: str, user: str, seed: int, today: date) -> tuple[dict, str]` (returns a new state, never mutates the input; second value is the reply text)

- [ ] **Step 1: Write failing tests** in `tests/test_game.py` (`unittest.TestCase`, helper `state()` = `initial_state(date(2026,11,6))` with hp set per test):
  - `test_parse_title_accepts_case_and_spaces`: `parse_title("  Play:   Rollback ") == "rollback"`
  - `test_parse_title_rejects_junk`: `None` for `""`, `"play: rollback; rm -rf /"`, `"play: nope"`, `"x"*500`
  - `test_valid_user`: `"Reksy747"` and `"a-b"` valid; `""`, `"-a"`, `"a_b"`, `"a"*40` invalid
  - `test_rollback_damage_18`: hp 100 → 82; log[0] has user, move, non-empty text
  - `test_add_yaml_scales_and_caps`: first call damage 4, second 8, with `yaml_stack` 7 damage is 30 (cap)
  - `test_blame_dns_zero_damage`: hp unchanged
  - `test_restart_it_damage_range_and_fix`: over seeds 0–200, non-fix damage is in 5..10, and at least one seed fixes the incident (hp 0 → win)
  - `test_deploy_friday_both_outcomes`: over seeds 0–200 outcomes include hp−35 and a heal of +20 (hp 50 → 70); heal at hp `max_hp-5` stops at `max_hp`
  - `test_win_resets_and_records`: hp 10 + rollback → hall_of_fame[0] == `{"user","incident","date"}` of the solved incident, `last_resolved` = today, `yaml_stack` 0, new incident name differs and hp == its max_hp; hp never negative
  - `test_log_keeps_newest_five_first`: after 6 alternating-user moves `len(log)==5`, newest first; hall of fame trimmed to 10
  - `test_same_seed_same_result`: two calls with seed 7 give equal states and replies
  - `test_apply_move_does_not_mutate_input`
  - `test_validate_rejects_same_user_case_insensitive`: log[0].user `"Reksy747"`, `validate(s, "play: rollback", "reksy747")` returns `(None, msg)`
  - `test_validate_accepts_other_user`: returns `("rollback", None)`

- [ ] **Step 2: Run tests, expect failure** — `"$PY" -m unittest discover -s tests -v` → ImportError/`ModuleNotFoundError: game`.

- [ ] **Step 3: Implement the above in `scripts/game.py`.** Damage and effects exactly per the spec table; win handling per the spec ("Win (hp ≤ 0)"); 3 jokes per move in a `JOKES: dict[str, list[str]]`, plus 3 rejection messages and one win line. Keep damage logic in a small per-move dict of functions `(rng, state) -> int` (negative = heal) so each rule is one line.

- [ ] **Step 4: Run tests, expect all pass.**

- [ ] **Step 5: Commit** — `git add scripts/game.py tests/test_game.py && git commit -m "feat: add incident game rules"`

---

### Task 2: Rendering and README patching

**Files:**
- Modify: `scripts/game.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: state shape from Task 1.
- Produces:
  - `render(state: dict, today: date) -> str` — markdown board: incident name, emoji HP bar (20 cells, `🟥` filled / `⬜` empty, plus `hp/max_hp`), `"N days since last incident was resolved"`, last-5 log lines `- @user — move — text`, hall of fame lines `- @user — incident — date`; empty log/hall show `_no moves yet_` / `_no winners yet_`
  - `update_readme(text: str, board: str) -> str` — replaces content between `<!--START_SECTION:game-->` and `<!--END_SECTION:game-->` (markers kept); raises `ValueError` if either marker is missing

- [ ] **Step 1: Write failing tests:**
  - `test_render_fresh_state`: contains "Certificate expired at 3am", `80/80`, "0 days since last incident", `_no moves yet_`, `_no winners yet_`
  - `test_render_hp_bar_proportional`: hp 40/80 → 10 `🟥` and 10 `⬜`
  - `test_render_days_since`: `last_resolved` 3 days before `today` → "3 days"
  - `test_render_lists_log_and_hall`
  - `test_update_readme_replaces_between_markers_only`: text before/after unchanged
  - `test_update_readme_idempotent`: applying twice equals applying once
  - `test_update_readme_missing_markers_raises`: `ValueError`

- [ ] **Step 2: Run tests, expect the new ones to fail.**
- [ ] **Step 3: Implement `render` and `update_readme`** (regex with `re.S`; use a lambda replacement so board text is never treated as a regex template).
- [ ] **Step 4: Run tests, expect all pass.**
- [ ] **Step 5: Commit** — `git add scripts/game.py tests/test_game.py && git commit -m "feat: render game board into README"`

---

### Task 3: Entrypoint

**Files:**
- Modify: `scripts/game.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: `validate`, `apply_move`, `render`, `update_readme`, `initial_state`.
- Produces: `main(root: Path = ROOT, env: Mapping[str, str] = os.environ) -> bool`. Reads `TITLE`, `USER`, `NUMBER` from `env`; loads `root/state/game.json` (creates via `initial_state` if absent); on accept writes `state/game.json` (indent 2, trailing newline) and `README.md`; always writes `root/reply.md` with the reply or rejection message; returns True when a move was applied. `if __name__ == "__main__":` calls `main()` and appends `applied=true|false` to the file named by `$GITHUB_OUTPUT` when set.

- [ ] **Step 1: Write failing tests** using `tempfile.TemporaryDirectory` with a minimal README containing the markers:
  - `test_main_applies_move`: returns True, state file and README updated, `reply.md` non-empty
  - `test_main_rejects_bad_title`: returns False, state file and README unchanged byte-for-byte, `reply.md` non-empty
  - `test_main_rejects_same_user_twice`: second identical call returns False
  - `test_main_bad_number_rejected`: `NUMBER="abc"` returns False without raising
- [ ] **Step 2: Run tests, expect the new ones to fail.**
- [ ] **Step 3: Implement `main`** (no new rules; delegate to existing functions; non-integer `NUMBER` is a rejection).
- [ ] **Step 4: Run tests, expect all pass.**
- [ ] **Step 5: Commit** — `git add scripts/game.py tests/test_game.py && git commit -m "feat: add game entrypoint"`

---

### Task 4: README, state, workflow, cleanup

**Files:**
- Create: `state/game.json`, `.github/workflows/play.yml`
- Modify: `README.md` (full rewrite)
- Delete: `.github/workflows/update-readme.yml`, `scripts/build_pipeline.py`, `assets/pipeline.svg`

**Interfaces:**
- Consumes: `main()` and the README markers from Task 2.

- [ ] **Step 1: Generate `state/game.json`** by running `initial_state(date.today())` through `json.dump` (indent 2) via a one-off `"$PY" -c` call.
- [ ] **Step 2: Rewrite `README.md`** per the spec layout: terminal banner `reksy@prod:~$ whoami` → `DevOps Engineer`; the game markers wrapping a placeholder line; five move badge links (`https://img.shields.io/badge/…` style, URL per spec); about, links, stack. Charming and funny copy, first person, short.
- [ ] **Step 3: Write `.github/workflows/play.yml`:** `on: issues: types: [opened]`; `permissions: contents: write, issues: write`; `concurrency: {group: game, cancel-in-progress: false}`; steps: `actions/checkout@v4`, run `python3 scripts/game.py` with `env: TITLE: ${{ github.event.issue.title }}`, `USER: ${{ github.event.issue.user.login }}`, `NUMBER: ${{ github.event.issue.number }}` (step has `id: play`); if `steps.play.outputs.applied == 'true'`, commit `state README.md` as `github-actions[bot]` and `git push`; final step `gh issue comment` with `--body-file reply.md` then `gh issue close`, using `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` and the issue number from the event.
- [ ] **Step 4: Delete the three obsolete files** with `git rm` (and `rm -rf assets` if empty).
- [ ] **Step 5: Verify locally:** all tests pass; then run once `TITLE="play: rollback" USER=tester NUMBER=1 "$PY" scripts/game.py` — expected `state/game.json` hp 62/80, README board shows `@tester`, `reply.md` exists. Check YAML parses: `"$PY" -c "import yaml"` is unavailable, so instead eyeball indentation and confirm with `git diff --stat`.
- [ ] **Step 6: Commit the pre-run files, not the test run.** Order: do Steps 1–4, run tests, commit (`git add -A` excluding `reply.md`; add `reply.md` to `.gitignore`), *then* run the Step 5 game run, view the result, and `git checkout -- state/game.json README.md` plus delete `reply.md` to restore the fresh state. Commit message: `feat: playable DevOps README game`.
- [ ] **Step 7 (after merge to `master`, by the user):** open an issue titled `play: rollback`; expected: Action comments, closes the issue, and the README board shows the move. Issue workflows only run from the default branch, so this cannot be checked before merge.

---

## Self-review notes

- Spec coverage: layout (Task 4), rules and state (Task 1), rendering (Task 2), safety, validation, concurrency (Tasks 1, 3, 4), testing (all), deletions (Task 4), known limits (README copy only).
- Interfaces are consistent: `validate` returns `(move, message)`, `apply_move` returns `(state, reply)`, `main` returns bool.
- Review Focus items are pinned by Task 1 (1–3), Task 2 (4–5).
