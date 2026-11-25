import html
import random
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from . import api, db
from .fmt import rank, match_line, dur

router = Router()
e = html.escape


@router.message(Command("dota"))
async def menu(m: Message):
    await m.answer(
        "🎮 <b>Dota-бот</b>\n\n"
        "/link ID — привязать свой аккаунт (friend ID или Steam64)\n"
        "/profile [ID] — профиль и статистика\n"
        "/matches [ID] — последние 5 матчей\n"
        "/match ID — разбор матча\n"
        "/watch ID — следить за другом (уведомления о матчах)\n"
        "/unwatch ID — перестать следить\n"
        "/watchlist — за кем слежу\n"
        "/quiz — викторина «угадай героя»\n"
        "/top — рейтинг викторины\n\n"
        "В Dota включи «Публичная история матчей», иначе данных не будет.",
        parse_mode="HTML",
    )


async def _acc(m: Message, command: CommandObject):
    if command.args:
        return api.to_account_id(command.args.split()[0])
    return db.get_account(m.from_user.id)


@router.message(Command("link"))
async def link(m: Message, command: CommandObject):
    acc = api.to_account_id(command.args or "")
    if not acc:
        return await m.answer("Использование: /link 123456789")
    p = await api.get(f"/players/{acc}", ttl=0)
    if not p or not p.get("profile"):
        return await m.answer("Профиль не найден. Проверь ID.")
    name = p["profile"].get("personaname") or str(acc)
    rm = await api.get(f"/players/{acc}/recentMatches", ttl=0)
    db.set_account(m.from_user.id, acc)
    db.watch(m.from_user.id, acc, name, rm[0]["match_id"] if rm else 0)
    await m.answer(f"✅ Привязан: <b>{e(name)}</b>. Теперь /profile и уведомления о твоих матчах.", parse_mode="HTML")


@router.message(Command("profile"))
async def profile(m: Message, command: CommandObject):
    acc = await _acc(m, command)
    if not acc:
        return await m.answer("Сначала /link ID или /profile ID")
    p = await api.get(f"/players/{acc}")
    if not p or not p.get("profile"):
        return await m.answer("Профиль не найден или скрыт.")
    wl = await api.get(f"/players/{acc}/wl") or {}
    top = (await api.get(f"/players/{acc}/heroes") or [])[:3]
    names = await api.hero_names()
    w, l = wl.get("win", 0), wl.get("lose", 0)
    wr = f"{w / (w + l) * 100:.1f}%" if w + l else "—"
    lines = [
        f"👤 <b>{e(p['profile'].get('personaname') or str(acc))}</b>",
        f"🏅 Ранг: {rank(p.get('rank_tier'))}",
        f"📊 {w}W / {l}L · винрейт {wr}",
        "",
        "<b>Любимые герои:</b>",
    ]
    for h in top:
        g, win = h["games"], h["win"]
        lines.append(f"• {names.get(int(h['hero_id']), '?')} — {g} игр, {win / g * 100:.0f}% побед" if g else "")
    await m.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("matches"))
async def matches(m: Message, command: CommandObject):
    acc = await _acc(m, command)
    if not acc:
        return await m.answer("Сначала /link ID")
    rm = await api.get(f"/players/{acc}/recentMatches", ttl=0)
    if not rm:
        return await m.answer("Матчей не найдено (история может быть скрыта).")
    names = await api.hero_names()
    out = [f"{match_line(x, names)}\n/match {x['match_id']}" for x in rm[:5]]
    await m.answer("\n\n".join(out))


@router.message(Command("match"))
async def match(m: Message, command: CommandObject):
    if not command.args or not command.args.strip().isdigit():
        return await m.answer("Использование: /match 1234567890")
    d = await api.get(f"/matches/{command.args.strip()}", ttl=600)
    if not d or "players" not in d:
        return await m.answer("Матч не найден.")
    names = await api.hero_names()
    ps = d["players"]

    def kda(p):
        return (p["kills"] + p["assists"]) / max(p["deaths"], 1)

    winners = [p for p in ps if p.get("win")]
    losers = [p for p in ps if not p.get("win")]
    mvp = max(winners, key=kda) if winners else None
    grief = max(losers, key=lambda p: p["deaths"] - kda(p)) if losers else None

    def row(p):
        who = e(p.get("personaname") or "Аноним")
        return (f"{names.get(p['hero_id'], '?')} ({who}) {p['kills']}/{p['deaths']}/{p['assists']} "
                f"· {p['gold_per_min']} GPM · {p['hero_damage']} урона")

    win_side = "Radiant" if d.get("radiant_win") else "Dire"
    lines = [f"🏆 Победил <b>{win_side}</b> · {dur(d['duration'])} · "
             f"{d.get('radiant_score', 0)}:{d.get('dire_score', 0)}", ""]
    lines.append("<b>Radiant</b>")
    lines += [f"• {row(p)}" for p in ps if p["isRadiant"]]
    lines += ["", "<b>Dire</b>"]
    lines += [f"• {row(p)}" for p in ps if not p["isRadiant"]]
    if mvp:
        lines += ["", f"⭐ MVP: {names.get(mvp['hero_id'], '?')} ({e(mvp.get('personaname') or 'Аноним')})"]
    if grief:
        lines += [f"🤡 Главный вредитель: {names.get(grief['hero_id'], '?')} "
                  f"({e(grief.get('personaname') or 'Аноним')}), {grief['deaths']} смертей"]
    await m.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("watch"))
async def watch(m: Message, command: CommandObject):
    acc = api.to_account_id(command.args or "")
    if not acc:
        return await m.answer("Использование: /watch 123456789")
    p = await api.get(f"/players/{acc}", ttl=0)
    if not p or not p.get("profile"):
        return await m.answer("Профиль не найден.")
    name = p["profile"].get("personaname") or str(acc)
    rm = await api.get(f"/players/{acc}/recentMatches", ttl=0)
    db.watch(m.from_user.id, acc, name, rm[0]["match_id"] if rm else 0)
    await m.answer(f"👀 Слежу за <b>{e(name)}</b>. Напишу, когда он закончит катку.", parse_mode="HTML")


@router.message(Command("unwatch"))
async def unwatch(m: Message, command: CommandObject):
    acc = api.to_account_id(command.args or "")
    if not acc:
        return await m.answer("Использование: /unwatch 123456789")
    db.unwatch(m.from_user.id, acc)
    await m.answer("Готово.")


@router.message(Command("watchlist"))
async def watchlist(m: Message):
    rows = db.my_watch(m.from_user.id)
    if not rows:
        return await m.answer("Список пуст. /watch ID")
    await m.answer("\n".join(f"• {e(n)} — {a}" for a, n in rows), parse_mode="HTML")


# ---------- Викторина ----------
@router.message(Command("quiz"))
async def quiz(m: Message):
    stats = await api.hero_stats()
    if len(stats) < 4:
        return await m.answer("Не получилось загрузить героев, попробуй позже.")
    opts = random.sample(stats, 4)
    right = random.choice(opts)
    attr = {"str": "Сила", "agi": "Ловкость", "int": "Интеллект", "all": "Универсал"}.get(
        right.get("primary_attr"), "?")
    text = (f"🧩 <b>Угадай героя</b>\nАтрибут: {attr}\n"
            f"Атака: {right.get('attack_type')}\nРоли: {', '.join(right.get('roles', []))}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=o["localized_name"], callback_data=f"q:{right['id']}:{o['id']}")] for o in opts])
    await m.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("q:"))
async def quiz_answer(c: CallbackQuery):
    _, right, chosen = c.data.split(":")
    names = await api.hero_names()
    if right == chosen:
        db.add_point(c.from_user.id, c.from_user.full_name)
        res = f"✅ Верно! Это {names.get(int(right), '?')}. +1 очко"
    else:
        res = f"❌ Нет. Это был {names.get(int(right), '?')}"
    await c.message.edit_text(c.message.html_text + f"\n\n{res}\n/quiz — ещё", parse_mode="HTML")
    await c.answer()


@router.message(Command("top"))
async def top(m: Message):
    rows = db.top()
    if not rows:
        return await m.answer("Пока никто не играл. /quiz")
    medals = ["🥇", "🥈", "🥉"]
    await m.answer("🏆 <b>Топ викторины</b>\n" + "\n".join(
        f"{medals[i] if i < 3 else i + 1}. {e(n)} — {p}" for i, (n, p) in enumerate(rows)), parse_mode="HTML")
