import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import get_user, update_user_field, get_db_connection, create_or_update_user, add_skin_to_user
from game_logic import find_match, check_match_ready, active_matches, update_elo, claim_chain_reward, get_skin_name
from admin_utils import get_all_skins

app = FastAPI(title="Echaris API", description="API для игры Эхарис: Дуэль душ")

# Разрешаем CORS для работы mini-app из Telegram
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# 1. Получение профиля пользователя
# ----------------------------------------------------------------------
@app.get("/api/profile")
async def profile(user_id: int):
    """Возвращает полную информацию о пользователе"""
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Получаем список скинов пользователя
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

    # Если экипированный скин не найден, но есть хоть один скин – берём первый
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


# ----------------------------------------------------------------------
# 2. Улучшение скилла
# ----------------------------------------------------------------------
@app.post("/api/upgrade_skill")
async def upgrade_skill(data: dict):
    """Улучшает уровень скилла за осколки"""
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


# ----------------------------------------------------------------------
# 3. Экипировка скина
# ----------------------------------------------------------------------
@app.post("/api/equip_skin")
async def equip_skin(data: dict):
    """Экипирует скин на персонажа"""
    user_id = data.get('user_id')
    skin_id = data.get('skin_id')
    
    if not user_id or not skin_id:
        raise HTTPException(400, "Missing user_id or skin_id")
    
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


# ----------------------------------------------------------------------
# 4. Поиск дуэли
# ----------------------------------------------------------------------
@app.post("/api/find_duel")
async def find_duel(data: dict):
    """Ищет соперника для PvP боя"""
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(400, "Missing user_id")
    
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Проверка билетов
    if user['daily_tickets'] <= 0:
        return {"status": "no_tickets"}
    
    # Проверяем, не готов ли уже матч (после ожидания)
    ready = check_match_ready(user_id)
    if ready:
        # Списываем билет
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return ready
    
    # Ищем или ставим в очередь
    result = find_match(user_id, user)
    if "match_id" in result:
        # Сразу нашли соперника, списываем билет
        new_tickets = user['daily_tickets'] - 1
        update_user_field(user_id, 'daily_tickets', new_tickets)
        return result
    else:
        return {"status": "waiting"}


# ----------------------------------------------------------------------
# 5. Действие в бою
# ----------------------------------------------------------------------
@app.post("/api/duel_action")
async def duel_action(data: dict):
    """Выполняет действие в бою (использование скилла)"""
    match_id = data.get('match_id')
    user_id = data.get('user_id')
    skill_index = data.get('skill_index')
    
    if not match_id or not user_id:
        raise HTTPException(400, "Missing match_id or user_id")
    
    match = active_matches.get(match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    
    # Если skill_index не передан – просто возвращаем текущее состояние (для обновления UI)
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
    
    # Применяем скилл
    result = match.apply_skill(user_id, skill_index)
    if "error" in result:
        return {"error": result["error"]}
    
    # Регенерируем энергию (1 ед. в секунду – вызывается каждый раз при действии)
    match.regenerate_energy()
    
    # Ход бота, если противник – бот
    if match.player2_id == -1 and match.player2_hp > 0:
        bot_result = match.bot_turn()
        if bot_result:
            result = bot_result
            match.regenerate_energy()
    
    # Проверяем, не закончился ли бой
    if match.is_finished():
        winner = match.get_winner()
        loser = match.player1_id if winner == match.player2_id else match.player2_id
        
        # Сохраняем битву в БД
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO battles (player1_id, player2_id, winner_id, log) VALUES (?,?,?,?)",
            (match.player1_id, match.player2_id, winner, json.dumps(match.log))
        )
        conn.commit()
        conn.close()
        
        # Обновляем ELO и награды (только если проигравший – не бот)
        if loser != -1:
            update_elo(winner, loser)
        
        # Удаляем матч из активных
        del active_matches[match_id]
        return {
            "battle_end": True,
            "winner_id": winner,
            "player_hp": result.get("player_hp", 0),
            "opponent_hp": result.get("opponent_hp", 0),
            "log": result.get("log", "")
        }
    
    return result


# ----------------------------------------------------------------------
# 6. Принудительное завершение дуэли
# ----------------------------------------------------------------------
@app.post("/api/end_duel")
async def end_duel(data: dict):
    """Принудительно завершает дуэль (например, при выходе из боя)"""
    match_id = data.get('match_id')
    if match_id and match_id in active_matches:
        del active_matches[match_id]
    return {"success": True}


# ----------------------------------------------------------------------
# 7. Таблица лидеров
# ----------------------------------------------------------------------
@app.get("/api/leaderboard")
async def leaderboard():
    """Возвращает топ-20 игроков по рейтингу"""
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


# ----------------------------------------------------------------------
# 8. Покупка скина
# ----------------------------------------------------------------------
@app.post("/api/buy_skin")
async def buy_skin(data: dict):
    """Покупка скина за Telegram Stars"""
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
    
    # Проверяем, не владеет ли уже
    already = conn.execute("SELECT 1 FROM user_skins WHERE user_id = ? AND skin_id = ?", (user_id, skin_id)).fetchone()
    if already:
        conn.close()
        return {"success": False, "error": "Already owned"}
    
    if not confirm:
        # Первый шаг: возвращаем запрос на оплату через Telegram Stars
        conn.close()
        return {
            "success": False,
            "need_invoice": True,
            "invoice_link": f"https://t.me/ваш_бот?start=pay_{skin_id}"
        }
    else:
        # Подтверждение покупки (после успешной оплаты)
        conn.execute("INSERT INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (user_id, skin_id))
        user = get_user(user_id)
        new_stars = user['stars_spent'] + skin['price_stars']
        update_user_field(user_id, 'stars_spent', new_stars)
        if new_stars >= 5000 and user['is_vip'] == 0:
            update_user_field(user_id, 'is_vip', 1)
            add_skin_to_user(user_id, 3)  # выдаём VIP-скин
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Skin {skin['name']} purchased"}


# ----------------------------------------------------------------------
# 9. Активация реферальной награды
# ----------------------------------------------------------------------
@app.post("/api/claim_referral_reward")
async def claim_referral_reward(data: dict):
    """Активация цепной награды за приглашение друга"""
    user_id = data.get('user_id')      # referrer (тот, кто пригласил)
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


# ----------------------------------------------------------------------
# 10. Использовать ежедневный билет
# ----------------------------------------------------------------------
@app.post("/api/use_ticket")
async def use_ticket(data: dict):
    """Использует один ежедневный билет на дуэль"""
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


# ----------------------------------------------------------------------
# 11. Список всех скинов (для магазина)
# ----------------------------------------------------------------------
@app.get("/api/skins_list")
async def skins_list(user_id: int):
    """Возвращает список всех доступных скинов"""
    conn = get_db_connection()
    skins = conn.execute("SELECT id, name, rarity, price_stars, stat_bonus FROM skins").fetchall()
    conn.close()
    return [dict(skin) for skin in skins]


# ----------------------------------------------------------------------
# 12. Проверка статуса матча (для polling)
# ----------------------------------------------------------------------
@app.get("/api/match_status")
async def match_status(match_id: str, user_id: int):
    """Возвращает текущее состояние матча"""
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


# ----------------------------------------------------------------------
# 13. Корневой эндпоинт (проверка работоспособности)
# ----------------------------------------------------------------------
@app.get("/")
async def root():
    """Проверка, что API работает"""
    return {"status": "ok", "message": "Echaris API is running"}


# ----------------------------------------------------------------------
# 14. Health check для Amvera
# ----------------------------------------------------------------------
@app.get("/health")
async def health():
    """Health check endpoint для Amvera"""
    return {"status": "healthy"}
