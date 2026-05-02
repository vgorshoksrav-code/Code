

Напишите полный код в файле api.py.
баш

cat > /home/claude/echaris/api.py << 'PYEOF'
import json, uuid
from datetime import date, datetime, timedelta
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import (get_user, update_user_field, get_db_connection,
                      create_or_update_user, add_skin_to_user)
from game_logic import find_match, check_match_ready, active_matches, update_elo, claim_chain_reward, get_skin_name
from admin_utils import get_all_skins

app = FastAPI(title="Echaris API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── helpers ──────────────────────────────────────────────────────────────
def _profile_skins(user_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT skin_id,equipped FROM user_skins WHERE user_id=?", (user_id,)).fetchall()
    owned, equipped = [], None
    for r in rows:
        sk = conn.execute("SELECT id,name,rarity,stat_bonus,emoji,description FROM skins WHERE id=?",
                          (r['skin_id'],)).fetchone()
        if sk:
            d = dict(sk); d['equipped'] = bool(r['equipped'])
            owned.append(d)
            if r['equipped']:
                equipped = {"id": sk['id'], "name": sk['name'],
                            "emoji": sk['emoji'] or '🧙',
                            "stat_bonus": json.loads(sk['stat_bonus'] or '{}')}
    conn.close()
    if not equipped:
        equipped = {"id":4,"name":"Страж пустоты","emoji":"🧙","stat_bonus":{"defense_pct":1}}
    return owned, equipped

def _check_temp_skin(user):
    """If temp skin expired, clear it."""
    if user and user['temp_skin_id'] and user['temp_skin_expires']:
        try:
            if datetime.utcnow() > datetime.strptime(user['temp_skin_expires'], '%Y-%m-%d %H:%M:%S'):
                update_user_field(user['user_id'], 'temp_skin_id', 0)
                update_user_field(user['user_id'], 'temp_skin_expires', None)
        except: pass

# ── health ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health(): return {"status":"ok"}

# ── register ──────────────────────────────────────────────────────────────
@app.post("/api/register")
async def register(data: dict):
    uid  = data.get('user_id')
    uname= data.get('username', f'user_{uid}')
    if not uid: raise HTTPException(400,"Missing user_id")
    is_new = create_or_update_user(uid, uname)
    user   = get_user(uid)
    # Welcome bonus: random epic/legendary temp skin for 72h
    welcome_msg = None
    if is_new or (user and not user['welcome_bonus_claimed']):
        if user and not user['welcome_bonus_claimed']:
            welcome_skins = [7,8,10,11,13]  # epic/legendary
            chosen = random.choice(welcome_skins)
            expires = (datetime.utcnow() + timedelta(hours=72)).strftime('%Y-%m-%d %H:%M:%S')
            update_user_field(uid, 'temp_skin_id', chosen)
            update_user_field(uid, 'temp_skin_expires', expires)
            update_user_field(uid, 'welcome_bonus_claimed', 1)
            conn = get_db_connection()
            sk = conn.execute("SELECT name,emoji FROM skins WHERE id=?", (chosen,)).fetchone()
            conn.close()
            welcome_msg = {"skin_id": chosen, "skin_name": sk['name'] if sk else "?",
                           "skin_emoji": sk['emoji'] if sk else "🎁", "hours": 72}
    return {"success": True, "is_new": bool(is_new), "welcome_bonus": welcome_msg}

# ── profile ───────────────────────────────────────────────────────────────
@app.get("/api/profile")
async def profile(user_id: int):
    user = get_user(user_id)
    if not user: raise HTTPException(404,"Not found")
    _check_temp_skin(user)
    user = get_user(user_id)  # re-fetch after potential update
    owned, equipped = _profile_skins(user_id)

    today = str(date.today())
    gift_available = (user['last_gift_date'] != today) if user['last_gift_date'] else True

    # temp skin info
    temp_skin = None
    if user['temp_skin_id']:
        conn = get_db_connection()
        sk = conn.execute("SELECT id,name,emoji FROM skins WHERE id=?", (user['temp_skin_id'],)).fetchone()
        conn.close()
        if sk:
            temp_skin = {"id":sk['id'],"name":sk['name'],"emoji":sk['emoji'],
                         "expires_at": user['temp_skin_expires']}

    # active events
    from promos import get_active_events
    events = get_active_events()

    return {
        "rank": user['rank'], "wins": user['wins'], "losses": user['losses'],
        "shards": user['shards'], "is_vip": bool(user['is_vip']),
        "daily_tickets": user['daily_tickets'],
        "hero_levels": json.loads(user['hero_levels']),
        "hero_class": user['hero_class'] if 'hero_class' in user.keys() else 'warrior',
        "language": user['language'] if 'language' in user.keys() else 'ru',
        "equipped_skin": equipped, "owned_skins": owned,
        "temp_skin": temp_skin,
        "gift_available": gift_available,
        "username": user['username'],
        "active_events": [{"name":e['name'],"icon":e['icon'],"event_type":e['event_type'],"multiplier":e['multiplier'],"ends_at":e['ends_at']} for e in events],
    }

# ── daily gift ────────────────────────────────────────────────────────────
@app.post("/api/daily_gift")
async def daily_gift(data: dict):
    uid = data.get('user_id')
    if not uid: raise HTTPException(400,"Missing user_id")
    user = get_user(uid)
    if not user: raise HTTPException(404,"Not found")
    today = str(date.today())
    if user['last_gift_date'] == today:
        return {"success":False,"error":"Подарок уже получен сегодня"}

    from promos import get_event_multiplier
    mult = get_event_multiplier('double_shards')

    shards_base = random.randint(30,100)
    shards_reward = int(shards_base * mult)
    tickets_reward = random.randint(1,3)
    update_user_field(uid,'shards', user['shards']+shards_reward)
    update_user_field(uid,'daily_tickets', user['daily_tickets']+tickets_reward)
    update_user_field(uid,'last_gift_date', today)

    rewards = [f"💎 +{shards_reward} осколков{' (x'+str(mult)+' событие!)' if mult>1 else ''}",
               f"🎟️ +{tickets_reward} билетов"]
    skin_reward = None
    if random.random() < 0.12:
        rare_ids = [5,6,9,12,18]
        sid = random.choice(rare_ids)
        conn = get_db_connection()
        already = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (uid,sid)).fetchone()
        conn.close()
        if not already:
            add_skin_to_user(uid, sid)
            conn = get_db_connection()
            sk = conn.execute("SELECT name FROM skins WHERE id=?", (sid,)).fetchone()
            conn.close()
            skin_reward = sk['name'] if sk else "Скин"
            rewards.append(f"🎁 Редкий скин: {skin_reward}!")

    return {"success":True,"rewards":rewards,"shards_earned":shards_reward,
            "tickets_earned":tickets_reward,"skin_reward":skin_reward}

# ── upgrade skill ─────────────────────────────────────────────────────────
@app.post("/api/upgrade_skill")
async def upgrade_skill(data: dict):
    uid = data.get('user_id'); idx = data.get('skill_index')
    if uid is None or idx is None: raise HTTPException(400,"Missing fields")
    user = get_user(uid)
    if not user: raise HTTPException(404,"Not found")
    levels = json.loads(user['hero_levels'])
    if not (0 <= idx < 5): raise HTTPException(400,"Invalid index")
    lv   = levels[idx]
    cost = 50 * lv
    if lv >= 20: return {"success":False,"error":"Максимальный уровень"}
    if user['shards'] < cost: return {"success":False,"error":f"Нужно {cost} 💎"}
    levels[idx] += 1
    update_user_field(uid,'shards', user['shards']-cost)
    update_user_field(uid,'hero_levels', json.dumps(levels))
    return {"success":True,"new_level":levels[idx],"new_shards":user['shards']-cost}

# ── equip skin ────────────────────────────────────────────────────────────
@app.post("/api/equip_skin")
async def equip_skin(data: dict):
    uid = data.get('user_id'); sid = data.get('skin_id')
    if not uid or not sid: raise HTTPException(400,"Missing fields")
    conn = get_db_connection()
    owns = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (uid,sid)).fetchone()
    if not owns:
        # allow equipping temp skin without owning
        user = get_user(uid)
        if not user or user['temp_skin_id'] != sid:
            conn.close(); return {"success":False,"error":"Скин не принадлежит вам"}
    conn.execute("UPDATE user_skins SET equipped=0 WHERE user_id=?", (uid,))
    if owns:
        conn.execute("UPDATE user_skins SET equipped=1 WHERE user_id=? AND skin_id=?", (uid,sid))
    conn.commit(); conn.close()
    update_user_field(uid,'equipped_skin_id', sid)
    return {"success":True}

# ── set hero class ────────────────────────────────────────────────────────
@app.post("/api/set_class")
async def set_class(data: dict):
    uid   = data.get('user_id')
    hclass= data.get('hero_class','warrior')
    valid = ['warrior','mage','archer','rogue','paladin','necromancer','druid']
    if hclass not in valid: return {"success":False,"error":"Invalid class"}
    update_user_field(uid,'hero_class', hclass)
    return {"success":True}

# ── set language ──────────────────────────────────────────────────────────
@app.post("/api/set_language")
async def set_language(data: dict):
    uid = data.get('user_id'); lang = data.get('language','ru')
    if lang not in ['ru','en']: return {"success":False,"error":"Unsupported"}
    update_user_field(uid,'language', lang)
    return {"success":True}

# ── find duel (fixed real matchmaking) ───────────────────────────────────
@app.post("/api/find_duel")
async def find_duel(data: dict):
    uid = data.get('user_id')
    if not uid: raise HTTPException(400,"Missing user_id")
    user = get_user(uid)
    if not user: raise HTTPException(404,"Not found")
    if user['daily_tickets'] <= 0:
        return {"status":"no_tickets"}

    # Check if already in a match
    ready = check_match_ready(uid)
    if ready and "match_id" in ready:
        update_user_field(uid,'daily_tickets', user['daily_tickets']-1)
        return ready

    result = find_match(uid, user)
    if "match_id" in result:
        update_user_field(uid,'daily_tickets', user['daily_tickets']-1)
        return result
    return {"status":"waiting"}

# ── check queue status ────────────────────────────────────────────────────
@app.get("/api/queue_status")
async def queue_status(user_id: int):
    """Poll for match without spending tickets."""
    from game_logic import pending_queue, active_matches
    ready = check_match_ready(user_id)
    if ready and "match_id" in ready:
        # deduct ticket when match found via polling
        user = get_user(user_id)
        if user and user['daily_tickets'] > 0:
            update_user_field(user_id,'daily_tickets', user['daily_tickets']-1)
        return {"status":"found", **ready}
    in_queue = user_id in pending_queue
    return {"status":"waiting" if in_queue else "idle"}

# ── duel action ───────────────────────────────────────────────────────────
@app.post("/api/duel_action")
async def duel_action(data: dict):
    mid = data.get('match_id'); uid = data.get('user_id'); skill = data.get('skill_index')
    if not mid or not uid: raise HTTPException(400,"Missing fields")
    match = active_matches.get(mid)
    if not match:
        return {"error":"Матч не найден","battle_end":True,"winner_id":-1}

    match.regenerate_energy()
    if skill is None:
        p1 = match.player1_id == uid
        return {"player_hp": match.player1_hp if p1 else match.player2_hp,
                "opponent_hp": match.player2_hp if p1 else match.player1_hp,
                "player_energy": match.player1_energy if p1 else match.player2_energy,
                "log":""}

    result = match.apply_skill(uid, skill)
    if "error" in result: return result

    # Bot turn
    if match.player2_id == -1 and match.player2_hp > 0:
        br = match.bot_turn()
        if br and "error" not in br:
            result = br; match.regenerate_energy()

    if match.is_finished():
        winner = match.get_winner()
        loser  = match.player1_id if winner == match.player2_id else match.player2_id
        conn = get_db_connection()
        conn.execute("INSERT INTO battles (player1_id,player2_id,winner_id,log) VALUES (?,?,?,?)",
                     (match.player1_id, match.player2_id, winner, json.dumps(match.log)))
        conn.commit(); conn.close()

        from promos import get_event_multiplier
        mult = get_event_multiplier('double_shards')

        if match.player1_id != -1 and match.player2_id != -1:
            update_elo(winner, loser)
        else:
            human = match.player1_id if match.player1_id != -1 else match.player2_id
            hu = get_user(human)
            if hu:
                if human == winner:
                    update_user_field(human,'shards', hu['shards']+int(15*mult))
                    update_user_field(human,'wins', hu['wins']+1)
                else:
                    update_user_field(human,'shards', hu['shards']+int(5*mult))
                    update_user_field(human,'losses', hu['losses']+1)

        del active_matches[mid]
        return {"battle_end":True,"winner_id":winner,
                "player_hp": result.get("player_hp",0),
                "opponent_hp": result.get("opponent_hp",0),
                "log": result.get("log","")}
    return result

@app.post("/api/end_duel")
async def end_duel(data: dict):
    mid = data.get('match_id')
    if mid and mid in active_matches: del active_matches[mid]
    from game_logic import pending_queue
    uid = data.get('user_id')
    if uid and uid in pending_queue: del pending_queue[uid]
    return {"success":True}

# ── leaderboard ───────────────────────────────────────────────────────────
@app.get("/api/leaderboard")
async def leaderboard():
    conn = get_db_connection()
    rows = conn.execute('''SELECT u.user_id,u.username,u.rank,u.wins,u.is_vip,
                           s.name skin_name,s.emoji skin_emoji
                           FROM users u LEFT JOIN skins s ON u.equipped_skin_id=s.id
                           ORDER BY u.rank DESC LIMIT 20''').fetchall()
    conn.close()
    return [{"user_id":r['user_id'],"username":r['username'],"rank":r['rank'],
             "wins":r['wins'],"is_vip":bool(r['is_vip']),
             "skin_name":r['skin_name'] or 'Страж пустоты',
             "skin_emoji":r['skin_emoji'] or '🧙'} for r in rows]

# ── buy skin (Telegram Stars invoice) ────────────────────────────────────
@app.post("/api/buy_skin")
async def buy_skin(data: dict):
    uid = data.get('user_id'); sid = data.get('skin_id')
    confirm = data.get('confirm', False)
    if not uid or not sid: raise HTTPException(400,"Missing fields")
    conn = get_db_connection()
    skin = conn.execute("SELECT id,name,price_stars FROM skins WHERE id=?", (sid,)).fetchone()
    if not skin: conn.close(); return {"success":False,"error":"Скин не найден"}
    already = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (uid,sid)).fetchone()
    if already: conn.close(); return {"success":False,"error":"Уже куплен"}

    if skin['price_stars'] == 0:
        conn.execute("INSERT OR IGNORE INTO user_skins VALUES (?,?,0)", (uid,sid))
        conn.commit(); conn.close()
        return {"success":True}

    if not confirm:
        # Return invoice link for Telegram Stars
        from config import BOT_TOKEN
        from admin_utils import get_webapp_url
        bot_username = "EcharisBot"  # will be used as fallback
        invoice_link = f"tg://resolve?domain={bot_username}&start=pay_{sid}"
        conn.close()
        return {"success":False,"need_invoice":True,
                "price_stars": skin['price_stars'],
                "skin_name": skin['name'],
                "skin_id": sid,
                "invoice_link": invoice_link}

    # Confirm purchase (called after payment)
    user = get_user(uid)
    conn.execute("INSERT OR IGNORE INTO user_skins VALUES (?,?,0)", (uid,sid))
    new_stars = (user['stars_spent'] if user else 0) + skin['price_stars']
    update_user_field(uid,'stars_spent', new_stars)
    if new_stars >= 5000 and user and not user['is_vip']:
        update_user_field(uid,'is_vip',1)
        conn.execute("INSERT OR IGNORE INTO user_skins VALUES (?,?,0)", (uid,3))
    conn.commit(); conn.close()
    return {"success":True}

# ── skins list ────────────────────────────────────────────────────────────
@app.get("/api/skins_list")
async def skins_list(user_id: int = 0):
    conn = get_db_connection()
    skins = conn.execute("SELECT id,name,rarity,price_stars,stat_bonus,emoji,description,hero_class FROM skins ORDER BY price_stars").fetchall()
    conn.close()
    return [dict(s) for s in skins]

# ── promo code ────────────────────────────────────────────────────────────
@app.post("/api/redeem_promo")
async def redeem_promo(data: dict):
    uid  = data.get('user_id')
    code = data.get('code','').strip()
    if not uid or not code: raise HTTPException(400,"Missing fields")
    from promos import redeem_promo as _redeem
    return _redeem(uid, code)

# ── events ────────────────────────────────────────────────────────────────
@app.get("/api/active_events")
async def active_events():
    from promos import get_active_events
    return get_active_events()

# ── PvE ───────────────────────────────────────────────────────────────────
@app.get("/api/campaign_progress")
async def campaign_progress(user_id: int):
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES
    progress = get_campaign_progress(user_id)
    chapter_names = ["Пробуждение","Теневые тропы","Ледяная цитадель","Огненные пещеры",
                     "Храм душ","Грозовой пик","Бездна","Цитадель времени","Сад эхарисов","Тронный зал"]
    chapters_info = []
    boss_emojis = {"NONE":"👹","INVISIBILITY":"👻","FREEZE":"🧊","BURNING":"🔥",
                   "VAMPIRISM":"🧛","PARALYSIS":"⚡","INSANITY":"🌀","SLOW":"🐌",
                   "REFLECTION":"🪞","ALL":"💀"}
    for n in range(1,11):
        bosses=[]
        for boss in CAMPAIGN_BOSSES[n]:
            mech = boss.mechanics[0].value if boss.mechanics else "NONE"
            bosses.append({"boss_id":boss.boss_id,"name":boss.name,"hp":boss.max_hp,
                           "damage":boss.damage,"emoji":boss_emojis.get(mech.upper(),"👹"),
                           "mechanics":[m.value for m in boss.mechanics],
                           "rewards":boss.rewards,
                           "defeated":boss.boss_id in progress['completed_bosses'],
                           "available":boss.boss_id == progress['current_boss_id']})
        chapters_info.append({"chapter":n,"name":chapter_names[n-1],
                               "completed":n in progress['completed_chapters'],
                               "unlocked":n <= progress['current_chapter'],"bosses":bosses})
    return {"progress":progress,"chapters":chapters_info}

@app.post("/api/pve_start_battle")
async def pve_start_battle(data: dict):
    import copy
    uid = data.get('user_id'); bid = data.get('boss_id')
    if not uid or not bid: raise HTTPException(400,"Missing fields")
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES, PvEBattle, active_pve_battles
    progress = get_campaign_progress(uid)
    boss = next((b for ch in CAMPAIGN_BOSSES.values() for b in ch if b.boss_id==bid), None)
    if not boss: return {"success":False,"error":"Босс не найден"}
    if bid > progress['current_boss_id']: return {"success":False,"error":"Победите предыдущего босса"}
    battle = PvEBattle(uid, copy.deepcopy(boss))
    active_pve_battles[uid] = battle
    state = battle.get_state()
    state['boss_emoji'] = '👹'
    return {"success":True,"state":state}

@app.post("/api/pve_action")
async def pve_action(data: dict):
    uid = data.get('user_id'); skill = data.get('skill_index')
    if not uid or skill is None: raise HTTPException(400,"Missing fields")
    from pve_campaign import active_pve_battles
    battle = active_pve_battles.get(uid)
    if not battle: raise HTTPException(404,"No active battle")
    user = get_user(uid)
    if not user: raise HTTPException(404,"Not found")
    conn = get_db_connection()
    sk = conn.execute("SELECT stat_bonus FROM skins WHERE id=?", (user['equipped_skin_id'],)).fetchone()
    conn.close()
    stats = json.loads(sk['stat_bonus'] if sk and sk['stat_bonus'] else '{}')
    from game_logic import SKILL_BASE_DAMAGE
    result = battle.player_attack(skill, SKILL_BASE_DAMAGE[skill], stats, json.loads(user['hero_levels']))
    return result

@app.post("/api/pve_claim_rewards")
async def pve_claim_rewards(data: dict):
    uid = data.get('user_id')
    if not uid: raise HTTPException(400,"Missing user_id")
    from pve_campaign import active_pve_battles, claim_boss_rewards, update_campaign_progress
    battle = active_pve_battles.get(uid)
    if not battle or not battle.finished or battle.winner != "player":
        return {"success":False,"error":"Нет наград"}
    from promos import get_event_multiplier
    mult = get_event_multiplier('double_shards')
    rewards = dict(battle.boss.rewards)
    rewards['shards'] = int(rewards.get('shards',0) * mult)
    res = claim_boss_rewards(uid, rewards)
    if res['success']:
        update_campaign_progress(uid, battle.boss.boss_id, battle.boss.chapter)
        del active_pve_battles[uid]
    return res

# ── Guilds ────────────────────────────────────────────────────────────────
@app.post("/api/create_guild")
async def create_guild(data: dict):
    from guilds import create_guild as cg
    return cg(data.get('name'), data.get('emoji','🏰'), data.get('description',''), data.get('user_id'))

@app.get("/api/guild_info")
async def guild_info(guild_id: str, user_id: int):
    from guilds import get_guild_info
    info = get_guild_info(guild_id, user_id)
    if not info: raise HTTPException(404,"Not found")
    return info

@app.post("/api/join_guild")
async def join_guild(data: dict):
    from guilds import join_guild as jg
    return jg(data.get('guild_id'), data.get('user_id'))

@app.post("/api/leave_guild")
async def leave_guild(data: dict):
    from guilds import leave_guild as lg
    return lg(data.get('user_id'))

@app.post("/api/promote_member")
async def promote_member(data: dict):
    from guilds import promote_member as pm
    return pm(data.get('leader_id'), data.get('target_id'), data.get('new_role'))

@app.post("/api/contribute_guild")
async def contribute_guild(data: dict):
    from guilds import contribute_to_guild
    return contribute_to_guild(data.get('user_id'), data.get('amount',10))

@app.post("/api/upgrade_building")
async def upgrade_building(data: dict):
    from guilds import upgrade_building as ub
    return ub(data.get('guild_id'), data.get('building_type'), data.get('user_id'))

@app.get("/api/guild_chat")
async def guild_chat(guild_id: str):
    from guilds import get_guild_messages
    return get_guild_messages(guild_id)

@app.post("/api/guild_send_message")
async def guild_send_message(data: dict):
    from guilds import send_guild_message as sgm
    return sgm(data.get('guild_id'), data.get('user_id'), data.get('username'), data.get('message'))

@app.get("/api/search_guilds")
async def search_guilds(query: str=""):
    from guilds import search_guilds as sg
    return sg(query)

@app.get("/api/guild_leaderboard")
async def guild_leaderboard():
    from guilds import get_guild_leaderboard
    return get_guild_leaderboard()

@app.post("/api/start_guild_raid")
async def start_guild_raid(data: dict):
    from guilds import start_guild_raid as sgr
    return sgr(data.get('guild_id'), data.get('boss_level',1))

@app.post("/api/attack_raid_boss")
async def attack_raid_boss(data: dict):
    from guilds import attack_raid_boss as arb
    res = arb(data.get('raid_id'), data.get('user_id'), data.get('damage',0))
    # Update quest progress
    if res.get('success'):
        try:
            conn = get_db_connection()
            m = conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?", (data.get('user_id'),)).fetchone()
            conn.close()
            if m:
                from promos import update_guild_quest_progress
                update_guild_quest_progress(m['guild_id'], 'raid_damage', data.get('damage',0))
        except: pass
    return res

@app.get("/api/my_guild")
async def my_guild(user_id: int):
    conn = get_db_connection()
    m = conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not m: return {"has_guild":False}
    from guilds import get_guild_info
    info = get_guild_info(m['guild_id'], user_id)
    # attach quests
    from promos import get_guild_quests, generate_guild_quests
    generate_guild_quests(m['guild_id'])  # ensure quests exist
    quests = get_guild_quests(m['guild_id'])
    if info: info['quests'] = quests
    return {"has_guild":True,"guild":info}

# ── Guild quests ──────────────────────────────────────────────────────────
@app.post("/api/claim_guild_quest")
async def claim_guild_quest(data: dict):
    from promos import claim_guild_quest as cq
    uid = data.get('user_id')
    conn = get_db_connection()
    m = conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    if not m: return {"success":False,"error":"Не в гильдии"}
    return cq(m['guild_id'], data.get('quest_id'), uid)

# ── Referral ──────────────────────────────────────────────────────────────
@app.post("/api/claim_referral_reward")
async def claim_referral_reward(data: dict):
    uid = data.get('user_id'); ref_uid = data.get('referred_user_id')
    if not uid or not ref_uid: raise HTTPException(400,"Missing fields")
    from game_logic import claim_chain_reward
    result = claim_chain_reward(ref_uid, uid)
    return {"success": result=="success", "error": result if result!="success" else None}

# ── Use ticket ────────────────────────────────────────────────────────────
@app.post("/api/use_ticket")
async def use_ticket(data: dict):
    uid = data.get('user_id')
    if not uid: raise HTTPException(400,"Missing user_id")
    user = get_user(uid)
    if not user: raise HTTPException(404,"Not found")
    if user['daily_tickets'] > 0:
        update_user_field(uid,'daily_tickets', user['daily_tickets']-1)
        return {"success":True,"remaining":user['daily_tickets']-1}
    return {"success":False,"error":"Нет билетов"}

# ── match status ──────────────────────────────────────────────────────────
@app.get("/api/match_status")
async def match_status(match_id: str, user_id: int):
    match = active_matches.get(match_id)
    if not match: return {"status":"not_found"}
    p1 = match.player1_id == user_id
    return {"player_hp": match.player1_hp if p1 else match.player2_hp,
            "opponent_hp": match.player2_hp if p1 else match.player1_hp,
            "player_energy": match.player1_energy if p1 else match.player2_energy,
            "finished": match.is_finished()}

# ── static (LAST) ─────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="web_app", html=True), name="static")
