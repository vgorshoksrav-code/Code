import json
import uuid
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from database import get_user, update_user_field, get_db_connection, create_or_update_user, add_skin_to_user
from game_logic import find_match, check_match_ready, active_matches, update_elo, claim_chain_reward, get_skin_name
from admin_utils import get_all_skins

app = FastAPI(title="Echaris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy"}

# ── Register / init user ─────────────────────────────────────────────────
@app.post("/api/register")
async def register(data: dict):
    user_id = data.get("user_id")
    username = data.get("username", f"user_{user_id}")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    create_or_update_user(user_id, username)
    user = get_user(user_id)
    is_new = user["wins"] == 0 and user["losses"] == 0 and user["shards"] == 0
    return {"success": True, "is_new": is_new}

# ── Profile ──────────────────────────────────────────────────────────────
@app.get("/api/profile")
async def profile(user_id: int):
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    conn = get_db_connection()
    rows = conn.execute("SELECT skin_id, equipped FROM user_skins WHERE user_id = ?", (user_id,)).fetchall()
    owned_skins = []
    equipped_skin_data = None
    for row in rows:
        skin = conn.execute(
            "SELECT id, name, rarity, stat_bonus, emoji, description FROM skins WHERE id = ?",
            (row["skin_id"],)
        ).fetchone()
        if skin:
            skin_dict = {
                "id": skin["id"], "name": skin["name"], "rarity": skin["rarity"],
                "equipped": bool(row["equipped"]),
                "emoji": skin["emoji"] or "🧙",
                "description": skin["description"] or ""
            }
            owned_skins.append(skin_dict)
            if row["equipped"]:
                equipped_skin_data = {
                    "id": skin["id"], "name": skin["name"],
                    "emoji": skin["emoji"] or "🧙",
                    "stat_bonus": json.loads(skin["stat_bonus"]) if skin["stat_bonus"] else {}
                }
    conn.close()
    if not equipped_skin_data:
        equipped_skin_data = {"id": 4, "name": "Страж пустоты", "emoji": "🧙", "stat_bonus": {"defense_pct": 1}}

    today = str(date.today())
    gift_available = (user["last_gift_date"] != today) if user["last_gift_date"] else True

    return {
        "rank": user["rank"], "wins": user["wins"], "losses": user["losses"],
        "shards": user["shards"], "is_vip": bool(user["is_vip"]),
        "daily_tickets": user["daily_tickets"],
        "hero_levels": json.loads(user["hero_levels"]),
        "equipped_skin": equipped_skin_data,
        "owned_skins": owned_skins,
        "hero_avatar": user["hero_avatar"] if "hero_avatar" in user.keys() else "warrior",
        "language": user["language"] if "language" in user.keys() else "ru",
        "gift_available": gift_available,
        "username": user["username"],
    }

# ── Daily gift ───────────────────────────────────────────────────────────
@app.post("/api/daily_gift")
async def daily_gift(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    today = str(date.today())
    if user["last_gift_date"] == today:
        return {"success": False, "error": "Подарок уже получен сегодня"}
    import random
    rewards = []
    shards_reward = random.randint(30, 100)
    tickets_reward = random.randint(1, 3)
    new_shards = user["shards"] + shards_reward
    new_tickets = user["daily_tickets"] + tickets_reward
    update_user_field(user_id, "shards", new_shards)
    update_user_field(user_id, "daily_tickets", new_tickets)
    update_user_field(user_id, "last_gift_date", today)
    rewards.append(f"💎 +{shards_reward} осколков")
    rewards.append(f"🎟️ +{tickets_reward} билетов")
    # Random rare skin chance 10%
    skin_reward = None
    if random.random() < 0.10:
        rare_skins = [5, 6, 9, 12]
        skin_id = random.choice(rare_skins)
        conn = get_db_connection()
        already = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (user_id, skin_id)).fetchone()
        conn.close()
        if not already:
            add_skin_to_user(user_id, skin_id)
            conn = get_db_connection()
            skin_name = conn.execute("SELECT name FROM skins WHERE id=?", (skin_id,)).fetchone()
            conn.close()
            skin_reward = skin_name["name"] if skin_name else "Скин"
            rewards.append(f"🎁 Редкий скин: {skin_reward}!")
    return {"success": True, "rewards": rewards, "shards_earned": shards_reward, "tickets_earned": tickets_reward, "skin_reward": skin_reward}

# ── Upgrade skill ────────────────────────────────────────────────────────
@app.post("/api/upgrade_skill")
async def upgrade_skill(data: dict):
    user_id = data.get("user_id")
    skill_index = data.get("skill_index")
    if user_id is None or skill_index is None:
        raise HTTPException(400, "Missing fields")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    levels = json.loads(user["hero_levels"])
    if not (0 <= skill_index < 5):
        raise HTTPException(400, "Invalid skill index")
    current_level = levels[skill_index]
    if current_level >= 20:
        return {"success": False, "error": "Максимальный уровень"}
    cost = 50 * current_level
    if user["shards"] < cost:
        return {"success": False, "error": f"Нужно {cost} 💎, у вас {user['shards']}"}
    levels[skill_index] = current_level + 1
    update_user_field(user_id, "shards", user["shards"] - cost)
    update_user_field(user_id, "hero_levels", json.dumps(levels))
    return {"success": True, "new_level": current_level + 1, "new_shards": user["shards"] - cost}

# ── Equip skin ───────────────────────────────────────────────────────────
@app.post("/api/equip_skin")
async def equip_skin(data: dict):
    user_id = data.get("user_id")
    skin_id = data.get("skin_id")
    if not user_id or not skin_id:
        raise HTTPException(400, "Missing fields")
    conn = get_db_connection()
    owns = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (user_id, skin_id)).fetchone()
    if not owns:
        conn.close()
        return {"success": False, "error": "Скин не принадлежит вам"}
    conn.execute("UPDATE user_skins SET equipped=0 WHERE user_id=?", (user_id,))
    conn.execute("UPDATE user_skins SET equipped=1 WHERE user_id=? AND skin_id=?", (user_id, skin_id))
    conn.commit()
    conn.close()
    update_user_field(user_id, "equipped_skin_id", skin_id)
    return {"success": True}

# ── Set hero avatar ──────────────────────────────────────────────────────
@app.post("/api/set_avatar")
async def set_avatar(data: dict):
    user_id = data.get("user_id")
    avatar = data.get("avatar", "warrior")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    valid = ["warrior", "mage", "archer", "rogue", "paladin", "necromancer"]
    if avatar not in valid:
        return {"success": False, "error": "Неверный аватар"}
    update_user_field(user_id, "hero_avatar", avatar)
    return {"success": True}

# ── Set language ─────────────────────────────────────────────────────────
@app.post("/api/set_language")
async def set_language(data: dict):
    user_id = data.get("user_id")
    lang = data.get("language", "ru")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    if lang not in ["ru", "en"]:
        return {"success": False, "error": "Unsupported language"}
    update_user_field(user_id, "language", lang)
    return {"success": True}

# ── Find duel ────────────────────────────────────────────────────────────
@app.post("/api/find_duel")
async def find_duel(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user["daily_tickets"] <= 0:
        return {"status": "no_tickets"}

    ready = check_match_ready(user_id)
    if ready and "match_id" in ready:
        update_user_field(user_id, "daily_tickets", user["daily_tickets"] - 1)
        return ready

    result = find_match(user_id, user)
    if "match_id" in result:
        update_user_field(user_id, "daily_tickets", user["daily_tickets"] - 1)
        return result
    return {"status": "waiting"}

# ── Duel action ──────────────────────────────────────────────────────────
@app.post("/api/duel_action")
async def duel_action(data: dict):
    match_id = data.get("match_id")
    user_id = data.get("user_id")
    skill_index = data.get("skill_index")
    if not match_id or not user_id:
        raise HTTPException(400, "Missing fields")
    match = active_matches.get(match_id)
    if not match:
        return {"error": "Матч не найден", "battle_end": True, "winner_id": -1}

    match.regenerate_energy()

    if skill_index is None:
        p1 = match.player1_id == user_id
        return {
            "player_hp": match.player1_hp if p1 else match.player2_hp,
            "opponent_hp": match.player2_hp if p1 else match.player1_hp,
            "player_energy": match.player1_energy if p1 else match.player2_energy,
            "log": ""
        }

    result = match.apply_skill(user_id, skill_index)
    if "error" in result:
        return result

    if match.player2_id == -1 and match.player2_hp > 0:
        bot_result = match.bot_turn()
        if bot_result and "error" not in bot_result:
            result = bot_result
            match.regenerate_energy()

    if match.is_finished():
        winner = match.get_winner()
        loser = match.player1_id if winner == match.player2_id else match.player2_id
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO battles (player1_id,player2_id,winner_id,log) VALUES (?,?,?,?)",
            (match.player1_id, match.player2_id, winner, json.dumps(match.log))
        )
        conn.commit()
        conn.close()
        if match.player1_id != -1 and match.player2_id != -1:
            update_elo(winner, loser)
        else:
            human = match.player1_id if match.player1_id != -1 else match.player2_id
            hu = get_user(human)
            if hu:
                if human == winner:
                    update_user_field(human, "shards", hu["shards"] + 15)
                    update_user_field(human, "wins", hu["wins"] + 1)
                else:
                    update_user_field(human, "shards", hu["shards"] + 5)
                    update_user_field(human, "losses", hu["losses"] + 1)
        del active_matches[match_id]
        return {
            "battle_end": True, "winner_id": winner,
            "player_hp": result.get("player_hp", 0),
            "opponent_hp": result.get("opponent_hp", 0),
            "log": result.get("log", "")
        }
    return result

# ── End duel ─────────────────────────────────────────────────────────────
@app.post("/api/end_duel")
async def end_duel(data: dict):
    match_id = data.get("match_id")
    if match_id and match_id in active_matches:
        del active_matches[match_id]
    return {"success": True}

# ── Leaderboard ───────────────────────────────────────────────────────────
@app.get("/api/leaderboard")
async def leaderboard():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.user_id, u.username, u.rank, u.wins, u.is_vip, s.name as skin_name, s.emoji as skin_emoji
        FROM users u
        LEFT JOIN skins s ON u.equipped_skin_id = s.id
        ORDER BY u.rank DESC LIMIT 20
    ''').fetchall()
    conn.close()
    return [{"user_id": r["user_id"], "username": r["username"], "rank": r["rank"],
             "wins": r["wins"], "is_vip": bool(r["is_vip"]),
             "skin_name": r["skin_name"] or "Страж пустоты",
             "skin_emoji": r["skin_emoji"] or "🧙"} for r in rows]

# ── Buy skin ──────────────────────────────────────────────────────────────
@app.post("/api/buy_skin")
async def buy_skin(data: dict):
    user_id = data.get("user_id")
    skin_id = data.get("skin_id")
    confirm = data.get("confirm", False)
    if not user_id or not skin_id:
        raise HTTPException(400, "Missing fields")
    conn = get_db_connection()
    skin = conn.execute("SELECT id,name,price_stars FROM skins WHERE id=?", (skin_id,)).fetchone()
    if not skin:
        conn.close()
        return {"success": False, "error": "Скин не найден"}
    already = conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?", (user_id, skin_id)).fetchone()
    if already:
        conn.close()
        return {"success": False, "error": "Уже куплен"}
    if not confirm:
        conn.close()
        return {"success": False, "need_invoice": True, "price_stars": skin["price_stars"], "skin_name": skin["name"]}
    conn.execute("INSERT INTO user_skins (user_id,skin_id,equipped) VALUES (?,?,0)", (user_id, skin_id))
    user = get_user(user_id)
    new_stars = user["stars_spent"] + skin["price_stars"]
    update_user_field(user_id, "stars_spent", new_stars)
    if new_stars >= 5000 and user["is_vip"] == 0:
        update_user_field(user_id, "is_vip", 1)
        conn.execute("INSERT OR IGNORE INTO user_skins (user_id,skin_id,equipped) VALUES (?,?,0)", (user_id, 3))
    conn.commit()
    conn.close()
    return {"success": True}

# ── Skins list ────────────────────────────────────────────────────────────
@app.get("/api/skins_list")
async def skins_list(user_id: int = 0):
    conn = get_db_connection()
    skins = conn.execute("SELECT id,name,rarity,price_stars,stat_bonus,emoji,description FROM skins ORDER BY price_stars").fetchall()
    conn.close()
    return [dict(s) for s in skins]

# ── Match status ──────────────────────────────────────────────────────────
@app.get("/api/match_status")
async def match_status(match_id: str, user_id: int):
    match = active_matches.get(match_id)
    if not match:
        return {"status": "not_found"}
    p1 = match.player1_id == user_id
    return {
        "player_hp": match.player1_hp if p1 else match.player2_hp,
        "opponent_hp": match.player2_hp if p1 else match.player1_hp,
        "player_energy": match.player1_energy if p1 else match.player2_energy,
        "finished": match.is_finished()
    }

# ── Claim referral reward ─────────────────────────────────────────────────
@app.post("/api/claim_referral_reward")
async def claim_referral_reward(data: dict):
    user_id = data.get("user_id")
    referred_user_id = data.get("referred_user_id")
    if not user_id or not referred_user_id:
        raise HTTPException(400, "Missing fields")
    result = claim_chain_reward(referred_user_id, user_id)
    if result == "success":
        return {"success": True}
    return {"success": False, "error": result}

# ── Use ticket ────────────────────────────────────────────────────────────
@app.post("/api/use_ticket")
async def use_ticket(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user["daily_tickets"] > 0:
        update_user_field(user_id, "daily_tickets", user["daily_tickets"] - 1)
        return {"success": True, "remaining": user["daily_tickets"] - 1}
    return {"success": False, "error": "Нет билетов"}

# ── PvE Campaign ──────────────────────────────────────────────────────────
@app.get("/api/campaign_progress")
async def campaign_progress(user_id: int):
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES
    progress = get_campaign_progress(user_id)
    chapter_names = [
        "Пробуждение", "Теневые тропы", "Ледяная цитадель",
        "Огненные пещеры", "Храм душ", "Грозовой пик",
        "Бездна", "Цитадель времени", "Сад эхарисов", "Тронный зал"
    ]
    chapters_info = []
    for ch_num in range(1, 11):
        bosses = []
        for boss in CAMPAIGN_BOSSES[ch_num]:
            bosses.append({
                "boss_id": boss.boss_id, "name": boss.name,
                "hp": boss.max_hp, "damage": boss.damage,
                "mechanics": [m.value for m in boss.mechanics],
                "rewards": boss.rewards,
                "defeated": boss.boss_id in progress["completed_bosses"],
                "available": boss.boss_id == progress["current_boss_id"]
            })
        chapters_info.append({
            "chapter": ch_num, "name": chapter_names[ch_num - 1],
            "completed": ch_num in progress["completed_chapters"],
            "unlocked": ch_num <= progress["current_chapter"],
            "bosses": bosses
        })
    return {"progress": progress, "chapters": chapters_info}

@app.post("/api/pve_start_battle")
async def pve_start_battle(data: dict):
    import copy
    user_id = data.get("user_id")
    boss_id = data.get("boss_id")
    if not user_id or not boss_id:
        raise HTTPException(400, "Missing fields")
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES, PvEBattle, active_pve_battles
    progress = get_campaign_progress(user_id)
    boss = None
    for ch_bosses in CAMPAIGN_BOSSES.values():
        for b in ch_bosses:
            if b.boss_id == boss_id:
                boss = b; break
        if boss: break
    if not boss:
        return {"success": False, "error": "Босс не найден"}
    if boss_id > progress["current_boss_id"]:
        return {"success": False, "error": "Сначала победите предыдущего босса"}
    battle = PvEBattle(user_id, copy.deepcopy(boss))
    active_pve_battles[user_id] = battle
    return {"success": True, "state": battle.get_state()}

@app.post("/api/pve_action")
async def pve_action(data: dict):
    user_id = data.get("user_id")
    skill_index = data.get("skill_index")
    if not user_id or skill_index is None:
        raise HTTPException(400, "Missing fields")
    from pve_campaign import active_pve_battles
    battle = active_pve_battles.get(user_id)
    if not battle:
        raise HTTPException(404, "Нет активного боя")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    conn = get_db_connection()
    skin = conn.execute("SELECT stat_bonus FROM skins WHERE id=?", (user["equipped_skin_id"],)).fetchone()
    conn.close()
    player_stats = json.loads(skin["stat_bonus"]) if skin and skin["stat_bonus"] else {}
    hero_levels = json.loads(user["hero_levels"])
    from game_logic import SKILL_BASE_DAMAGE
    result = battle.player_attack(skill_index, SKILL_BASE_DAMAGE[skill_index], player_stats, hero_levels)
    if "error" in result:
        return result
    return result

@app.post("/api/pve_claim_rewards")
async def pve_claim_rewards(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    from pve_campaign import active_pve_battles, claim_boss_rewards, update_campaign_progress
    battle = active_pve_battles.get(user_id)
    if not battle or not battle.finished or battle.winner != "player":
        return {"success": False, "error": "Нет наград"}
    rewards_result = claim_boss_rewards(user_id, battle.boss.rewards)
    if rewards_result["success"]:
        update_campaign_progress(user_id, battle.boss.boss_id, battle.boss.chapter)
        del active_pve_battles[user_id]
    return rewards_result

# ── Guild endpoints ───────────────────────────────────────────────────────
@app.post("/api/create_guild")
async def create_guild(data: dict):
    from guilds import create_guild
    return create_guild(data.get("name"), data.get("emoji", "🏰"), data.get("description", ""), data.get("user_id"))

@app.get("/api/guild_info")
async def guild_info(guild_id: str, user_id: int):
    from guilds import get_guild_info
    info = get_guild_info(guild_id, user_id)
    if not info:
        raise HTTPException(404, "Гильдия не найдена")
    return info

@app.post("/api/join_guild")
async def join_guild(data: dict):
    from guilds import join_guild
    return join_guild(data.get("guild_id"), data.get("user_id"))

@app.post("/api/leave_guild")
async def leave_guild(data: dict):
    from guilds import leave_guild
    return leave_guild(data.get("user_id"))

@app.post("/api/promote_member")
async def promote_member(data: dict):
    from guilds import promote_member
    return promote_member(data.get("leader_id"), data.get("target_id"), data.get("new_role"))

@app.post("/api/contribute_guild")
async def contribute_guild(data: dict):
    from guilds import contribute_to_guild
    return contribute_to_guild(data.get("user_id"), data.get("amount", 10))

@app.post("/api/upgrade_building")
async def upgrade_building(data: dict):
    from guilds import upgrade_building
    return upgrade_building(data.get("guild_id"), data.get("building_type"), data.get("user_id"))

@app.get("/api/guild_chat")
async def guild_chat(guild_id: str):
    from guilds import get_guild_messages
    return get_guild_messages(guild_id)

@app.post("/api/guild_send_message")
async def guild_send_message(data: dict):
    from guilds import send_guild_message
    return send_guild_message(data.get("guild_id"), data.get("user_id"), data.get("username"), data.get("message"))

@app.get("/api/search_guilds")
async def search_guilds(query: str = ""):
    from guilds import search_guilds
    return search_guilds(query)

@app.get("/api/guild_leaderboard")
async def guild_leaderboard():
    from guilds import get_guild_leaderboard
    return get_guild_leaderboard()

@app.post("/api/start_guild_raid")
async def start_guild_raid(data: dict):
    from guilds import start_guild_raid
    return start_guild_raid(data.get("guild_id"), data.get("boss_level", 1))

@app.post("/api/attack_raid_boss")
async def attack_raid_boss(data: dict):
    from guilds import attack_raid_boss
    return attack_raid_boss(data.get("raid_id"), data.get("user_id"), data.get("damage", 0))

@app.get("/api/my_guild")
async def my_guild(user_id: int):
    conn = get_db_connection()
    member = conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not member:
        return {"has_guild": False}
    from guilds import get_guild_info
    info = get_guild_info(member["guild_id"], user_id)
    return {"has_guild": True, "guild": info}

# ── Static (must be last) ─────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="web_app", html=True), name="static")
