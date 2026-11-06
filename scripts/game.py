"""Incident Commander: rules for the profile README game. Standard library only."""
import copy
import random
import re
from datetime import date

MOVES = ("rollback", "restart-it", "blame-dns", "add-yaml", "deploy-friday")

INCIDENTS = [
    ("Certificate expired at 3am", 80),
    ("The intern ran `rm -rf`", 100),
    ("DNS is down (it's always DNS)", 90),
    ("Disk full of logs nobody reads", 70),
    ("Kubernetes pods in CrashLoopBackOff", 110),
    ("Terraform wants to destroy everything", 120),
]

# Each rule: (rng, state) -> damage; negative means the outage heals.
DAMAGE = {
    "rollback": lambda r, s: 18,
    "restart-it": lambda r, s: s["incident"]["hp"] if r.random() < 0.08 else r.randint(5, 10),
    "blame-dns": lambda r, s: 0,
    "add-yaml": lambda r, s: min(4 + 4 * s["yaml_stack"], 30),
    "deploy-friday": lambda r, s: 35 if r.random() < 0.5 else -20,
}

JOKES = {
    "rollback": ["Ctrl+Z, but for production.", "We were never here.", "git revert, and breathe."],
    "restart-it": ["Have you tried turning it off and on again?", "Percussive maintenance, but digital.", "Reboot: the duct tape of ops."],
    "blame-dns": ["It was DNS. It's always DNS. Zero fixed, full confidence.", "Blame assigned, nothing fixed.", "DNS has been notified (it did not care)."],
    "add-yaml": ["More YAML. Indentation is a lifestyle.", "Two spaces or four? The outage waits.", "The YAML grows. The outage flinches."],
    "deploy-friday": ["Deploying on a Friday. Bold. Reckless. Legendary.", "Friday 5pm deploy: what could go wrong?", "The on-call engineer felt a disturbance."],
}
WIN_LINE = "🎉 Incident resolved! A new one is already paging."

REJECT_USER = "That doesn't look like a valid GitHub username, so the bot is ignoring you."
REJECT_TITLE = "I only understand `play: <move>` with one of: " + ", ".join(MOVES) + "."
REJECT_REPEAT = "You made the last move. Let someone else take the pager."


def new_incident(rng, exclude=None):
    name, hp = rng.choice([i for i in INCIDENTS if i[0] != exclude])
    return {"name": name, "hp": hp, "max_hp": hp}


def initial_state(today: date) -> dict:
    name, hp = INCIDENTS[0]
    return {
        "incident": {"name": name, "hp": hp, "max_hp": hp},
        "yaml_stack": 0,
        "log": [],
        "hall_of_fame": [],
        "last_resolved": today.isoformat(),
    }


def parse_title(title: str):
    m = re.fullmatch(r"\s*play:\s*([a-z-]+)\s*", title, re.I)
    move = m.group(1).lower() if m else None
    return move if move in MOVES else None


def valid_user(login: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", login) is not None


def validate(state: dict, title: str, user: str):
    if not valid_user(user):
        return None, REJECT_USER
    move = parse_title(title)
    if move is None:
        return None, REJECT_TITLE
    if state["log"] and state["log"][0]["user"].lower() == user.lower():
        return None, REJECT_REPEAT
    return move, None


def apply_move(state: dict, move: str, user: str, seed: int, today: date):
    s = copy.deepcopy(state)
    rng = random.Random(seed)
    inc = s["incident"]
    dmg = DAMAGE[move](rng, s)
    if move == "add-yaml":
        s["yaml_stack"] += 1
    before = inc["hp"]
    inc["hp"] = max(0, min(inc["max_hp"], before - dmg))
    delta = before - inc["hp"]
    effect = f"-{delta} HP" if delta > 0 else f"+{-delta} HP (it got worse)" if delta < 0 else "no effect"
    text = f"{effect}. {rng.choice(JOKES[move])}"

    if inc["hp"] == 0:
        entry = {"user": user, "incident": inc["name"], "date": today.isoformat()}
        s["hall_of_fame"] = ([entry] + s["hall_of_fame"])[:10]
        s["last_resolved"] = today.isoformat()
        s["yaml_stack"] = 0
        s["incident"] = new_incident(rng, exclude=inc["name"])
        text += " " + WIN_LINE

    s["log"] = ([{"user": user, "move": move, "text": text}] + s["log"])[:5]
    return s, f"@{user} used `{move}`: {text}"


BAR_CELLS = 20
MARKERS = ("<!--START_SECTION:game-->", "<!--END_SECTION:game-->")


def render(state: dict, today: date) -> str:
    inc = state["incident"]
    filled = round(BAR_CELLS * inc["hp"] / inc["max_hp"])
    if inc["hp"] > 0:
        filled = max(1, filled)
    bar = "🟥" * filled + "⬜" * (BAR_CELLS - filled)
    days = max(0, (today - date.fromisoformat(state["last_resolved"])).days)
    unit = "day" if days == 1 else "days"
    moves = "\n".join(f"- @{e['user']} — {e['move']} — {e['text']}" for e in state["log"]) or "_no moves yet_"
    hall = "\n".join(f"- @{e['user']} — {e['incident']} — {e['date']}" for e in state["hall_of_fame"]) or "_no winners yet_"
    return (
        f"**🔥 Incident:** {inc['name']}\n\n"
        f"{bar} `{inc['hp']}/{inc['max_hp']}`\n\n"
        f"🗓️ **{days} {unit} since last incident was resolved**\n\n"
        f"**Last moves**\n{moves}\n\n"
        f"**Hall of fame**\n{hall}"
    )


def update_readme(text: str, board: str) -> str:
    start, end = MARKERS
    new, n = re.subn(
        f"({re.escape(start)}).*?({re.escape(end)})",
        lambda m: f"{m.group(1)}\n{board}\n{m.group(2)}",
        text,
        flags=re.S,
    )
    if n == 0:
        raise ValueError("README is missing the game section markers")
    return new
