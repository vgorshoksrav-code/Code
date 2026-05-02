import json, random, uuid
from datetime import datetime, timedelta
from database import get_db_connection, get_user, update_user_field, add_skin_to_user

# ── Promo codes ──────────────────────────────────────────────────────────

def create_promo(code, reward_type, reward_value, max_uses=1, days_valid=30, created_by=0):
    """
    reward_type: 'shards' | 'tickets' | 'skin' | 'temp_skin' | 'stars_spent'
    reward_value: dict, e.g. {"amount":500} or {"skin_id":7} or {"skin_id":7,"hours":72}
    """
    conn = get_db_connection()
    expires = (datetime.utcnow() + timedelta(days=days_valid)).strftime('%Y-%m-%d %H:%M:%S') if days_valid else None
    try:
        conn.execute('''INSERT INTO promo_codes (code,reward_type,reward_value,max_uses,expires_at,created_by)
                        VALUES (?,?,?,?,?,?)''',
                     (code.upper(), reward_type, json.dumps(reward_value), max_uses, expires, created_by))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}

def list_promos(active_only=True):
    conn = get_db_connection()
    q = "SELECT * FROM promo_codes" + (" WHERE active=1" if active_only else "")
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def deactivate_promo(code):
    conn = get_db_connection()
    conn.execute("UPDATE promo_codes SET active=0 WHERE code=?", (code.upper(),))
    conn.commit(); conn.close()
    return {"success": True}

def redeem_promo(user_id, code_raw):
    code = code_raw.strip().upper()
    conn = get_db_connection()
    promo = conn.execute("SELECT * FROM promo_codes WHERE code=?", (code,)).fetchone()
    if not promo:
        conn.close(); return {"success": False, "error": "Промокод не найден"}
    if not promo['active']:
        conn.close(); return {"success": False, "error": "Промокод неактивен"}
    if promo['expires_at']:
        if datetime.utcnow() > datetime.strptime(promo['expires_at'], '%Y-%m-%d %H:%M:%S'):
            conn.close(); return {"success": False, "error": "Срок действия истёк"}
    if promo['used_count'] >= promo['max_uses']:
        conn.close(); return {"success": False, "error": "Лимит использований исчерпан"}
    already = conn.execute("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", (code, user_id)).fetchone()
    if already:
        conn.close(); return {"success": False, "error": "Вы уже использовали этот промокод"}

    val = json.loads(promo['reward_value'])
    user = get_user(user_id)
    if not user:
        conn.close(); return {"success": False, "error": "Пользователь не найден"}

    msg = ""
    rtype = promo['reward_type']

    if rtype == 'shards':
        amt = val.get('amount', 100)
        update_user_field(user_id, 'shards', user['shards'] + amt)
        msg = f"+{amt} 💎 осколков"

    elif rtype == 'tickets':
        amt = val.get('amount', 3)
        update_user_field(user_id, 'daily_tickets', user['daily_tickets'] + amt)
        msg = f"+{amt} 🎟️ билетов"

    elif rtype == 'skin':
        sid = val.get('skin_id')
        if sid:
            add_skin_to_user(user_id, sid)
            skin = conn.execute("SELECT name FROM skins WHERE id=?", (sid,)).fetchone()
            msg = f"🎁 Скин: {skin['name'] if skin else sid}"

    elif rtype == 'temp_skin':
        sid = val.get('skin_id')
        hours = val.get('hours', 72)
        if sid:
            expires = (datetime.utcnow() + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            update_user_field(user_id, 'temp_skin_id', sid)
            update_user_field(user_id, 'temp_skin_expires', expires)
            skin = conn.execute("SELECT name FROM skins WHERE id=?", (sid,)).fetchone()
            msg = f"⏳ Временный скин на {hours}ч: {skin['name'] if skin else sid}"

    elif rtype == 'stars_spent':
        amt = val.get('amount', 100)
        new_stars = user['stars_spent'] + amt
        update_user_field(user_id, 'stars_spent', new_stars)
        if new_stars >= 5000 and not user['is_vip']:
            update_user_field(user_id, 'is_vip', 1)
            add_skin_to_user(user_id, 3)
        msg = f"+{amt} ⭐ Stars"

    conn.execute("INSERT INTO promo_uses VALUES (?,?,CURRENT_TIMESTAMP)", (code, user_id))
    conn.execute("UPDATE promo_codes SET used_count=used_count+1 WHERE code=?", (code,))
    conn.commit(); conn.close()
    return {"success": True, "message": msg, "reward_type": rtype}


# ── Temporary events ─────────────────────────────────────────────────────

def get_active_events():
    conn = get_db_connection()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    rows = conn.execute(
        "SELECT * FROM events WHERE active=1 AND starts_at<=? AND ends_at>=?",
        (now, now)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_event(name, description, event_type, multiplier, hours, icon='🎉', created_by=0):
    conn = get_db_connection()
    now = datetime.utcnow()
    starts = now.strftime('%Y-%m-%d %H:%M:%S')
    ends = (now + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''INSERT INTO events (name,description,icon,event_type,multiplier,starts_at,ends_at,created_by)
                    VALUES (?,?,?,?,?,?,?,?)''',
                 (name, description, icon, event_type, multiplier, starts, ends, created_by))
    conn.commit(); conn.close()
    return {"success": True}

def list_events():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_event_multiplier(event_type):
    """Returns best multiplier for given type from active events."""
    events = get_active_events()
    best = 1.0
    for e in events:
        if e['event_type'] == event_type and e['multiplier'] > best:
            best = e['multiplier']
    return best


# ── Guild quests ──────────────────────────────────────────────────────────

QUEST_TEMPLATES = [
    {"type": "win_battles",    "target": 10,  "reward": {"shards": 200, "exp": 100}},
    {"type": "win_battles",    "target": 25,  "reward": {"shards": 500, "exp": 250}},
    {"type": "defeat_bosses",  "target": 5,   "reward": {"shards": 300, "exp": 150}},
    {"type": "spend_shards",   "target": 1000,"reward": {"shards": 150, "exp": 80}},
    {"type": "guild_members",  "target": 5,   "reward": {"shards": 100, "exp": 50}},
    {"type": "raid_damage",    "target": 5000,"reward": {"shards": 400, "exp": 200}},
]

def generate_guild_quests(guild_id):
    """Generate fresh quests for a guild (called weekly)."""
    conn = get_db_connection()
    # Remove old completed quests
    conn.execute("DELETE FROM guild_quests WHERE guild_id=? AND completed=1", (guild_id,))
    # Check how many active quests
    count = conn.execute("SELECT COUNT(*) FROM guild_quests WHERE guild_id=? AND completed=0", (guild_id,)).fetchone()[0]
    added = 0
    if count < 3:
        import random
        templates = random.sample(QUEST_TEMPLATES, min(3 - count, len(QUEST_TEMPLATES)))
        expires = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        for t in templates:
            conn.execute('''INSERT INTO guild_quests (guild_id,quest_type,target,reward,expires_at)
                            VALUES (?,?,?,?,?)''',
                         (guild_id, t['type'], t['target'], json.dumps(t['reward']), expires))
            added += 1
    conn.commit(); conn.close()
    return added

def get_guild_quests(guild_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM guild_quests WHERE guild_id=? ORDER BY completed, id", (guild_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_guild_quest_progress(guild_id, quest_type, amount=1):
    """Called after guild actions to update quest progress."""
    conn = get_db_connection()
    quests = conn.execute(
        "SELECT * FROM guild_quests WHERE guild_id=? AND quest_type=? AND completed=0",
        (guild_id, quest_type)
    ).fetchall()
    for q in quests:
        new_prog = q['progress'] + amount
        if new_prog >= q['target']:
            conn.execute("UPDATE guild_quests SET progress=?, completed=1 WHERE id=?", (q['target'], q['id']))
        else:
            conn.execute("UPDATE guild_quests SET progress=? WHERE id=?", (new_prog, q['id']))
    conn.commit(); conn.close()

def claim_guild_quest(guild_id, quest_id, user_id):
    """Claim reward for completed guild quest — distributes to all members."""
    conn = get_db_connection()
    q = conn.execute("SELECT * FROM guild_quests WHERE id=? AND guild_id=? AND completed=1", (quest_id, guild_id)).fetchone()
    if not q:
        conn.close(); return {"success": False, "error": "Квест не найден или не завершён"}
    reward = json.loads(q['reward'])
    members = conn.execute("SELECT user_id FROM guild_members WHERE guild_id=?", (guild_id,)).fetchall()
    for m in members:
        uid = m['user_id']
        u = get_user(uid)
        if u:
            update_user_field(uid, 'shards', u['shards'] + reward.get('shards', 0))
    # Remove quest
    conn.execute("DELETE FROM guild_quests WHERE id=?", (quest_id,))
    conn.commit(); conn.close()
    return {"success": True, "reward": reward}
