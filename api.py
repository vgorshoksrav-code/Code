import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from database import get_user, update_user_field, get_db_connection, create_or_update_user, add_skin_to_user
from game_logic import find_match, check_match_ready, active_matches, update_elo, claim_chain_reward, get_skin_name
from admin_utils import get_all_skins

app = FastAPI(title="Echaris API", description="API для игры Эхарис: Дуэль душ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# 1. Health check (должен быть ДО монтирования статики)
# ------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy"}

# ------------------------------------------------------------
# 2. Профиль пользователя
# ------------------------------------------------------------
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
        skin = conn.execute("SELECT id, name, rarity, stat_bonus FROM skins WHERE id = ?", (row['skin_id'],)).fetchone()
        if skin:
            skin_dict = {
                "id": skin['id'],
                "name": skin['name'],
                "rarity": skin['rarity'],
                "equipped": bool(row['equipped'])
            }
            owned_skins.append(skin_dict)
            if row['equipped']:
                equipped_skin_data = {
                    "id": skin['id'],
                    "name": skin['name'],
                    "stat_bonus": json.loads(skin['stat_bonus']) if skin['stat_bonus'] else {}
                }
    conn.close()

    if not equipped_skin_data and owned_skins:
        equipped_skin_data = {
            "id": owned_skins[0]['id'],
            "name": owned_skins[0]['name'],
            "stat_bonus": {}
        }
    elif not equipped_skin_data:
        equipped_skin_data = {
            "id": 4,
            "name": "Страж пустоты",
            "stat_bonus": {"defense_pct": 1}
        }

    return {
        "rank": user['rank'],
        "wins": user['wins'],
        "losses": user['losses'],
        "shards": user['shards'],
        "is_vip": bool(user['is_vip']),
        "daily_tickets": user['daily_tickets'],
        "hero_levels": json.loads(user['hero_levels']),
        "equipped_skin": equipped_skin_data,
        "owned_skins": owned_skins
    }

# ------------------------------------------------------------
# 3. Улучшение скилла
# ------------------------------------------------------------
@app.post("/api/upgrade_skill")
async def upgrade_skill(data: dict):
    user_id = data.get('user_id')
    skill_index = data.get('skill_index')
    if user_id is None or skill_index is None:
        raise HTTPException(400, "Missing user_id or skill_index")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    levels = json.loads(user['hero_levels'])
    if skill_index < 0 or skill_index >= 5:
        raise HTTPException(400, "Invalid skill index")
    current_level = levels[skill_index]
    cost = 50 * current_level
    if user['shards'] < cost:
        return {"success": False, "error": "Not enough shards"}
    new_shards = user['shards'] - cost
    levels[skill_index] = current_level + 1
    update_user_field(user_id, 'shards', new_shards)
    update_user_field(user_id, 'hero_levels', json.dumps(levels))
    return {"success": True, "new_level": current_level + 1, "new_shards": new_shards}

# ------------------------------------------------------------
# 4. Экипировка скина
# ------------------------------------------------------------
@app.post("/api/equip_skin")
async def equip_skin(data: dict):
    user_id = data.get('user_id')
    skin_id = data.get('skin_id')
    if not user_id or not skin_id:
        raise HTTPException(400, "Missing user_id or skin_id")
    conn = get_db_connection()
    owns = conn.execute("SELECT 1 FROM user_skins WHERE user_id = ? AND skin_id = ?", (user_id, skin_id)).fetchone()
    if not owns:
        conn.close()
        return {"success": False, "error": "Skin not owned"}
    conn.execute("UPDATE user_skins SET equipped = 0 WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE user_skins SET equipped = 1 WHERE user_id = ? AND skin_id = ?", (user_id, skin_id))
    update_user_field(user_id, 'equipped_skin_id', skin_id)
    conn.commit()
    conn.close()
    return {"success": True}

# ------------------------------------------------------------
# 5. Поиск дуэли
# ------------------------------------------------------------
@app.post("/api/find_duel")
async def find_duel(data: dict):
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user['daily_tickets'] <= 0:
        return {"status": "no_tickets"}

    ready = check_match_ready(user_id)
    if ready:
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return ready

    result = find_match(user_id, user)
    if "match_id" in result:
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return result
    else:
        return {"status": "waiting"}

# ------------------------------------------------------------
# 6. Действие в бою
# ------------------------------------------------------------
@app.post("/api/duel_action")
async def duel_action(data: dict):
    match_id = data.get('match_id')
    user_id = data.get('user_id')
    skill_index = data.get('skill_index')

    if not match_id or not user_id:
        raise HTTPException(400, "Missing match_id or user_id")
    match = active_matches.get(match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    # Регенерация энергии каждый раз при запросе
    match.regenerate_energy()

    if skill_index is None:
        if match.player1_id == user_id:
            return {
                "player_hp": match.player1_hp,
                "opponent_hp": match.player2_hp,
                "player_energy": match.player1_energy,
                "log": ""
            }
        else:
            return {
                "player_hp": match.player2_hp,
                "opponent_hp": match.player1_hp,
                "player_energy": match.player2_energy,
                "log": ""
            }

    result = match.apply_skill(user_id, skill_index)
    if "error" in result:
        return {"error": result["error"]}

    if match.player2_id == -1 and match.player2_hp > 0:
        bot_result = match.bot_turn()
        if bot_result:
            result = bot_result
            match.regenerate_energy()

    if match.is_finished():
        winner = match.get_winner()
        loser = match.player1_id if winner == match.player2_id else match.player2_id

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO battles (player1_id, player2_id, winner_id, log) VALUES (?,?,?,?)",
            (match.player1_id, match.player2_id, winner, json.dumps(match.log))
        )
        conn.commit()
        conn.close()

        if match.player1_id != -1 and match.player2_id != -1:
            update_elo(winner, loser)
        else:
            human_player = match.player1_id if match.player1_id != -1 else match.player2_id
            human_user = get_user(human_player)
            if human_user:
                if human_player == winner:
                    update_user_field(human_player, 'shards', human_user['shards'] + 10)
                    update_user_field(human_player, 'wins', human_user['wins'] + 1)
                else:
                    update_user_field(human_player, 'shards', human_user['shards'] + 3)
                    update_user_field(human_player, 'losses', human_user['losses'] + 1)

        del active_matches[match_id]
        return {
            "battle_end": True,
            "winner_id": winner,
            "player_hp": result.get("player_hp", 0),
            "opponent_hp": result.get("opponent_hp", 0),
            "log": result.get("log", "")
        }

    return result

# ------------------------------------------------------------
# 7. Принудительное завершение дуэли
# ------------------------------------------------------------
@app.post("/api/end_duel")
async def end_duel(data: dict):
    match_id = data.get('match_id')
    if match_id and match_id in active_matches:
        del active_matches[match_id]
    return {"success": True}

# ------------------------------------------------------------
# 8. Таблица лидеров
# ------------------------------------------------------------
@app.get("/api/leaderboard")
async def leaderboard():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.user_id, u.username, u.rank, u.wins, s.name as skin_name
        FROM users u
        LEFT JOIN skins s ON u.equipped_skin_id = s.id
        ORDER BY u.rank DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "user_id": row['user_id'],
            "username": row['username'],
            "rank": row['rank'],
            "wins": row['wins'],
            "skin_name": row['skin_name'] or "Базовый"
        })
    return result

# ------------------------------------------------------------
# 9. Покупка скина
# ------------------------------------------------------------
@app.post("/api/buy_skin")
async def buy_skin(data: dict):
    user_id = data.get('user_id')
    skin_id = data.get('skin_id')
    confirm = data.get('confirm', False)
    if not user_id or not skin_id:
        raise HTTPException(400, "Missing user_id or skin_id")
    conn = get_db_connection()
    skin = conn.execute("SELECT id, name, price_stars FROM skins WHERE id = ?", (skin_id,)).fetchone()
    if not skin:
        conn.close()
        return {"success": False, "error": "Skin not found"}
    already = conn.execute("SELECT 1 FROM user_skins WHERE user_id = ? AND skin_id = ?", (user_id, skin_id)).fetchone()
    if already:
        conn.close()
        return {"success": False, "error": "Already owned"}
    if not confirm:
        conn.close()
        return {
            "success": False,
            "need_invoice": True,
            "invoice_link": f"https://t.me/ваш_бот?start=pay_{skin_id}"
        }
    conn.execute("INSERT INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (user_id, skin_id))
    user = get_user(user_id)
    new_stars = user['stars_spent'] + skin['price_stars']
    update_user_field(user_id, 'stars_spent', new_stars)
    if new_stars >= 5000 and user['is_vip'] == 0:
        update_user_field(user_id, 'is_vip', 1)
        add_skin_to_user(user_id, 3)
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Skin {skin['name']} purchased"}

# ------------------------------------------------------------
# 10. Активация реферальной награды
# ------------------------------------------------------------
@app.post("/api/claim_referral_reward")
async def claim_referral_reward(data: dict):
    user_id = data.get('user_id')
    referred_user_id = data.get('referred_user_id')
    if not user_id or not referred_user_id:
        raise HTTPException(400, "Missing user_id or referred_user_id")
    result = claim_chain_reward(referred_user_id, user_id)
    if result == "success":
        return {"success": True, "message": "Reward claimed"}
    elif result == "already_claimed":
        return {"success": False, "error": "Already claimed"}
    else:
        return {"success": False, "error": "Error"}

# ------------------------------------------------------------
# 11. Использовать ежедневный билет
# ------------------------------------------------------------
@app.post("/api/use_ticket")
async def use_ticket(data: dict):
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user['daily_tickets'] > 0:
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return {"success": True, "remaining": new_tickets}
    return {"success": False, "error": "No tickets left"}

# ------------------------------------------------------------
# 12. Список всех скинов (магазин)
# ------------------------------------------------------------
@app.get("/api/skins_list")
async def skins_list(user_id: int):
    conn = get_db_connection()
    skins = conn.execute("SELECT id, name, rarity, price_stars, stat_bonus FROM skins").fetchall()
    conn.close()
    return [dict(skin) for skin in skins]

# ------------------------------------------------------------
# 13. Проверка статуса матча
# ------------------------------------------------------------
@app.get("/api/match_status")
async def match_status(match_id: str, user_id: int):
    match = active_matches.get(match_id)
    if not match:
        return {"status": "not_found"}
    if match.player1_id == user_id:
        return {
            "player_hp": match.player1_hp,
            "opponent_hp": match.player2_hp,
            "player_energy": match.player1_energy,
            "finished": match.is_finished()
        }
    else:
        return {
            "player_hp": match.player2_hp,
            "opponent_hp": match.player1_hp,
            "player_energy": match.player2_energy,
            "finished": match.is_finished()
        }

# ------------------------------------------------------------
# 14. PvE Кампания - получить прогресс
# ------------------------------------------------------------
@app.get("/api/campaign_progress")
async def campaign_progress(user_id: int):
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES
    progress = get_campaign_progress(user_id)
    
    chapters_info = []
    chapter_names = [
        "Пробуждение", "Теневые тропы", "Ледяная цитадель",
        "Огненные пещеры", "Храм душ", "Грозовой пик",
        "Бездна", "Цитадель времени", "Сад эхарисов", "Тронный зал"
    ]
    
    for ch_num in range(1, 11):
        bosses = []
        for boss in CAMPAIGN_BOSSES[ch_num]:
            bosses.append({
                "boss_id": boss.boss_id,
                "name": boss.name,
                "hp": boss.max_hp,
                "damage": boss.damage,
                "mechanics": [m.value for m in boss.mechanics],
                "rewards": boss.rewards,
                "defeated": boss.boss_id in progress['completed_bosses'],
                "available": boss.boss_id == progress['current_boss_id']
            })
        chapters_info.append({
            "chapter": ch_num,
            "name": chapter_names[ch_num - 1],
            "completed": ch_num in progress['completed_chapters'],
            "unlocked": ch_num <= progress['current_chapter'],
            "bosses": bosses
        })
    
    return {
        "progress": progress,
        "chapters": chapters_info
    }

# ------------------------------------------------------------
# 15. PvE - начать бой с боссом
# ------------------------------------------------------------
@app.post("/api/pve_start_battle")
async def pve_start_battle(data: dict):
    user_id = data.get('user_id')
    boss_id = data.get('boss_id')
    
    if not user_id or not boss_id:
        raise HTTPException(400, "Missing user_id or boss_id")
    
    from pve_campaign import get_campaign_progress, CAMPAIGN_BOSSES, PvEBattle, active_pve_battles
    import copy
    
    progress = get_campaign_progress(user_id)
    
    # Проверяем, что босс существует и доступен
    boss = None
    for ch_bosses in CAMPAIGN_BOSSES.values():
        for b in ch_bosses:
            if b.boss_id == boss_id:
                boss = b
                break
        if boss:
            break
    
    if not boss:
        return {"success": False, "error": "Босс не найден"}
    
    if boss_id > progress['current_boss_id']:
        return {"success": False, "error": "Сначала победите предыдущего босса"}
    
    # Создаём копию босса и начинаем битву
    battle = PvEBattle(user_id, copy.deepcopy(boss))
    active_pve_battles[user_id] = battle
    
    return {
        "success": True,
        "state": battle.get_state()
    }

# ------------------------------------------------------------
# 16. PvE - действие в бою
# ------------------------------------------------------------
@app.post("/api/pve_action")
async def pve_action(data: dict):
    user_id = data.get('user_id')
    skill_index = data.get('skill_index')
    
    if not user_id or skill_index is None:
        raise HTTPException(400, "Missing user_id or skill_index")
    
    from pve_campaign import active_pve_battles
    battle = active_pve_battles.get(user_id)
    if not battle:
        raise HTTPException(404, "Нет активного боя")
    
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    equipped_skin_id = user['equipped_skin_id']
    conn = get_db_connection()
    skin = conn.execute("SELECT stat_bonus FROM skins WHERE id = ?", (equipped_skin_id,)).fetchone()
    conn.close()
    player_stats = json.loads(skin['stat_bonus']) if skin and skin['stat_bonus'] else {}
    
    hero_levels = json.loads(user['hero_levels'])
    
    from game_logic import SKILL_BASE_DAMAGE
    result = battle.player_attack(skill_index, SKILL_BASE_DAMAGE[skill_index], player_stats, hero_levels)
    
    if "error" in result:
        return {"error": result["error"]}
    
    return result

# ------------------------------------------------------------
# 17. PvE - забрать награду
# ------------------------------------------------------------
@app.post("/api/pve_claim_rewards")
async def pve_claim_rewards(data: dict):
    user_id = data.get('user_id')
    
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    
    from pve_campaign import active_pve_battles, claim_boss_rewards, update_campaign_progress
    
    battle = active_pve_battles.get(user_id)
    if not battle or not battle.finished or battle.winner != "player":
        return {"success": False, "error": "Нет доступных наград"}
    
    rewards_result = claim_boss_rewards(user_id, battle.boss.rewards)
    
    if rewards_result['success']:
        update_campaign_progress(user_id, battle.boss.boss_id, battle.boss.chapter)
        del active_pve_battles[user_id]
    
    return rewards_result

# ------------------------------------------------------------
# Монтирование статики (ДОЛЖНО быть последним)
# ------------------------------------------------------------
app.mount("/", StaticFiles(directory="web_app", html=True), name="static")
