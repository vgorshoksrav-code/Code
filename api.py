from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import time
from database import get_user, update_user_field, get_db_connection, create_or_update_user
from game_logic import find_match, check_match_ready, active_matches, update_elo, claim_chain_reward, get_opponent_info
from admin_utils import get_all_skins
import uuid

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/profile")
async def profile(user_id: int):
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    owned_skins = []
    conn = get_db_connection()
    rows = conn.execute("SELECT skin_id, equipped FROM user_skins WHERE user_id = ?", (user_id,)).fetchall()
    for row in rows:
        skin = conn.execute("SELECT name, rarity, stat_bonus FROM skins WHERE id = ?", (row['skin_id'],)).fetchone()
        if skin:
            owned_skins.append({
                "id": row['skin_id'],
                "name": skin['name'],
                "rarity": skin['rarity'],
                "equipped": bool(row['equipped'])
            })
    conn.close()
    # Получить экипированный скин
    equipped_skin = None
    for s in owned_skins:
        if s['equipped']:
            equipped_skin = {"id": s['id'], "name": s['name'], "stat_bonus": json.loads(skin['stat_bonus']) if skin else {}}
            break
    if not equipped_skin and owned_skins:
        equipped_skin = {"id": owned_skins[0]['id'], "name": owned_skins[0]['name'], "stat_bonus": {}}
    return {
        "rank": user['rank'],
        "wins": user['wins'],
        "losses": user['losses'],
        "shards": user['shards'],
        "is_vip": bool(user['is_vip']),
        "daily_tickets": user['daily_tickets'],
        "hero_levels": json.loads(user['hero_levels']),
        "equipped_skin": equipped_skin,
        "owned_skins": owned_skins
    }

@app.post("/api/upgrade_skill")
async def upgrade_skill(data: dict):
    user_id = data['user_id']
    skill_index = data['skill_index']
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    levels = json.loads(user['hero_levels'])
    if skill_index < 0 or skill_index >= 5:
        raise HTTPException(400, "Invalid skill index")
    current = levels[skill_index]
    cost = 50 * current
    if user['shards'] < cost:
        return {"success": False, "error": "Not enough shards"}
    new_shards = user['shards'] - cost
    levels[skill_index] = current + 1
    update_user_field(user_id, 'shards', new_shards)
    update_user_field(user_id, 'hero_levels', json.dumps(levels))
    return {"success": True, "new_level": current+1, "new_shards": new_shards}

@app.post("/api/equip_skin")
async def equip_skin(data: dict):
    user_id = data['user_id']
    skin_id = data['skin_id']
    conn = get_db_connection()
    # Проверяем, есть ли скин у пользователя
    owns = conn.execute("SELECT 1 FROM user_skins WHERE user_id = ? AND skin_id = ?", (user_id, skin_id)).fetchone()
    if not owns:
        conn.close()
        return {"success": False, "error": "Skin not owned"}
    # Снимаем экипировку со всех других скинов
    conn.execute("UPDATE user_skins SET equipped = 0 WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE user_skins SET equipped = 1 WHERE user_id = ? AND skin_id = ?", (user_id, skin_id))
    update_user_field(user_id, 'equipped_skin_id', skin_id)
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/find_duel")
async def find_duel(data: dict):
    user_id = data['user_id']
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    # Используем ежедневные билеты
    if user['daily_tickets'] <= 0:
        return {"status": "no_tickets"}
    # Проверяем готовый матч (после ожидания)
    ready = check_match_ready(user_id)
    if ready:
        return ready
    # Ищем или ставим в очередь
    result = find_match(user_id, user)
    if "match_id" in result:
        # Если сразу нашли соперника, списываем билет
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return result
    else:
        return {"status": "waiting"}

@app.post("/api/duel_action")
async def duel_action(data: dict):
    match_id = data['match_id']
    user_id = data['user_id']
    skill_index = data.get('skill_index')
    if match_id not in active_matches:
        raise HTTPException(404, "Match not found")
    match = active_matches[match_id]
    if skill_index is None:
        # Если без скилла, просто возвращаем состояние
        if match.player1_id == user_id:
            return {"player_hp": match.player1_hp, "opponent_hp": match.player2_hp, "player_energy": match.player1_energy, "log": ""}
        else:
            return {"player_hp": match.player2_hp, "opponent_hp": match.player1_hp, "player_energy": match.player2_energy, "log": ""}
    result = match.apply_skill(user_id, skill_index)
    if "error" in result:
        return {"error": result["error"]}
    # Если битва закончена
    if match.player1_hp <= 0 or match.player2_hp <= 0:
        winner = match.player1_id if match.player1_hp > 0 else match.player2_id
        loser = match.player2_id if winner == match.player1_id else match.player1_id
        # Сохраняем битву и обновляем ELO
        conn = get_db_connection()
        conn.execute("INSERT INTO battles (player1_id, player2_id, winner_id, log) VALUES (?,?,?,?)",
                     (match.player1_id, match.player2_id, winner, json.dumps(match.log)))
        conn.commit()
        conn.close()
        if loser != -1:
            update_elo(winner, loser)
        # Удаляем матч
        del active_matches[match_id]
        return {"battle_end": True, "winner_id": winner, "player_hp": result.get("player_hp",0), "opponent_hp": result.get("opponent_hp",0), "log": result.get("log","")}
    # Ход бота, если противник - бот
    if match.player2_id == -1 and match.player2_hp > 0:
        bot_result = match.bot_turn()
        if bot_result:
            result = bot_result
    return result

@app.post("/api/end_duel")
async def end_duel(data: dict):
    # Если клиент форсированно завершает дуэль (например, вышел)
    match_id = data['match_id']
    if match_id in active_matches:
        del active_matches[match_id]
    return {"success": True}

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

@app.post("/api/buy_skin")
async def buy_skin(data: dict):
    user_id = data['user_id']
    skin_id = data['skin_id']
    conn = get_db_connection()
    skin = conn.execute("SELECT price_stars, name FROM skins WHERE id = ?", (skin_id,)).fetchone()
    if not skin:
        conn.close()
        return {"success": False, "error": "Skin not found"}
    # Проверяем, есть ли уже
    already = conn.execute("SELECT 1 FROM user_skins WHERE user_id = ? AND skin_id = ?", (user_id, skin_id)).fetchone()
    if already:
        conn.close()
        return {"success": False, "error": "Already owned"}
    # Здесь должна быть реальная интеграция с Telegram Stars invoice.
    # Для демонстрации возвращаем заглушку и эмулируем успешную покупку при повторном запросе с confirmation=true
    if data.get('confirm'):
        # Добавляем скин пользователю
        conn.execute("INSERT INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (user_id, skin_id))
        # Списываем звезды (stars_spent)
        user = get_user(user_id)
        new_spent = user['stars_spent'] + skin['price_stars']
        update_user_field(user_id, 'stars_spent', new_spent)
        if new_spent >= 5000 and user['is_vip'] == 0:
            update_user_field(user_id, 'is_vip', 1)
            add_skin_to_user(user_id, 3)
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Skin {skin['name']} purchased"}
    else:
        conn.close()
        # Здесь должен быть вызов Telegram invoice. Возвращаем флаг, что нужно открыть диалог оплаты.
        return {"success": False, "need_invoice": True, "invoice_link": f"https://t.me/ваш_бот?start=pay_{skin_id}"}

# Функция add_skin_to_user (импорт из database)
from database import add_skin_to_user

@app.post("/api/claim_referral_reward")
async def claim_referral_reward(data: dict):
    user_id = data['user_id']
    referred_user_id = data.get('referred_user_id')
    if not referred_user_id:
        return {"success": False, "error": "Missing referred_user_id"}
    result = claim_chain_reward(referred_user_id, user_id)
    if result == "success":
        return {"success": True, "message": "Reward claimed"}
    elif result == "already_claimed":
        return {"success": False, "error": "Already claimed"}
    else:
        return {"success": False, "error": "Error"}

@app.post("/api/use_ticket")
async def use_ticket(data: dict):
    user_id = data['user_id']
    user = get_user(user_id)
    if user and user['daily_tickets'] > 0:
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return {"success": True, "remaining": new_tickets}
    return {"success": False, "error": "No tickets left"}
