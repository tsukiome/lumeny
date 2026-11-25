MEDALS = ["Без ранга", "Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"]


def rank(tier):
    if not tier:
        return "Без ранга"
    return f"{MEDALS[tier // 10]} {tier % 10 or ''}".strip()


def is_win(m):
    return (m["player_slot"] < 128) == m["radiant_win"]


def dur(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def match_line(m, heroes):
    mark = "✅ Победа" if is_win(m) else "❌ Поражение"
    hero = heroes.get(m["hero_id"], "?")
    return f"{mark} · {hero} · {m['kills']}/{m['deaths']}/{m['assists']} · {dur(m['duration'])}"
