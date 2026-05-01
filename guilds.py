import json
import random
import uuid
from datetime import datetime, timedelta
from database import get_user, update_user_field, get_db_connection
from enum import Enum

class GuildRole(Enum):
    LEADER = "leader"
    OFFICER = "officer"
    VETERAN = "veteran"
    MEMBER = "member"

class GuildBuilding(Enum):
    ALTAR = "altar"          # +опыт
    FORGE = "forge"          # +урон
    LIBRARY = "library"      # -стоимость скиллов
    WATCHTOWER = "watchtower"  # +защита в войнах

# ------------------------------------------------------------
# Управление гильдиями
# ------------------------------------------------------------

def init_guild_tables():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS guilds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '🏰',
            description TEXT DEFAULT '',
            leader_id INTEGER NOT NULL,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            war_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (leader_id) REFERENCES users(user_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_members (
            user_id INTEGER PRIMARY KEY,
            guild_id TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            contribution INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_buildings (
            guild_id TEXT NOT NULL,
            building_type TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, building_type),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_wars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            war_id TEXT UNIQUE NOT NULL,
            guild1_id TEXT NOT NULL,
            guild2_id TEXT NOT NULL,
            guild1_points INTEGER DEFAULT 0,
            guild2_points INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',  -- pending, active, finished
            winner_id TEXT,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            FOREIGN KEY (guild1_id) REFERENCES guilds(guild_id),
            FOREIGN KEY (guild2_id) REFERENCES guilds(guild_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_raids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raid_id TEXT UNIQUE NOT NULL,
            guild_id TEXT NOT NULL,
            boss_name TEXT NOT NULL,
            boss_max_hp INTEGER NOT NULL,
            boss_current_hp INTEGER NOT NULL,
            status TEXT DEFAULT 'active',  -- active, completed
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        );
        
        CREATE TABLE IF NOT EXISTS guild_raid_damage (
            user_id INTEGER NOT NULL,
            raid_id TEXT NOT NULL,
            damage INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, raid_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (raid_id) REFERENCES guild_raids(raid_id)
        );
    ''')
    conn.commit()
    conn.close()

# Вызываем при старте
init_guild_tables()

# ------------------------------------------------------------
# CRUD операции
# ------------------------------------------------------------

def create_guild(name, emoji, description, leader_id):
    """Создание новой гильдии"""
    conn = get_db_connection()
    
    # Проверяем, не состоит ли уже в гильдии
    member = conn.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (leader_id,)).fetchone()
    if member:
        conn.close()
        return {"success": False, "error": "Вы уже состоите в гильдии"}
    
    # Проверяем осколки
    user = get_user(leader_id)
    if not user or user['shards'] < 500:
        conn.close()
        return {"success": False, "error": "Недостаточно осколков (нужно 500)"}
    
    # Списываем осколки
    update_user_field(leader_id, 'shards', user['shards'] - 500)
    
    guild_id = str(uuid.uuid4())[:8]
    
    conn.execute('''
        INSERT INTO guilds (guild_id, name, emoji, description, leader_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (guild_id, name, emoji, description, leader_id))
    
    conn.execute('''
        INSERT INTO guild_members (user_id, guild_id, role)
        VALUES (?, ?, ?)
    ''', (leader_id, guild_id, GuildRole.LEADER.value))
    
    # Создаём базовые здания
    for building in GuildBuilding:
        conn.execute('''
            INSERT INTO guild_buildings (guild_id, building_type)
            VALUES (?, ?)
        ''', (guild_id, building.value))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "guild_id": guild_id}

def get_guild_info(guild_id, user_id=None):
    """Полная информация о гильдии"""
    conn = get_db_connection()
    
    guild = conn.execute('''
        SELECT g.*, u.username as leader_name
        FROM guilds g
        JOIN users u ON g.leader_id = u.user_id
        WHERE g.guild_id = ?
    ''', (guild_id,)).fetchone()
    
    if not guild:
        conn.close()
        return None
    
    # Участники
    members = conn.execute('''
        SELECT gm.*, u.username, u.rank, u.wins,
               s.name as skin_name
        FROM guild_members gm
        JOIN users u ON gm.user_id = u.user_id
        LEFT JOIN skins s ON u.equipped_skin_id = s.id
        WHERE gm.guild_id = ?
        ORDER BY 
            CASE gm.role 
                WHEN 'leader' THEN 1 
                WHEN 'officer' THEN 2 
                WHEN 'veteran' THEN 3 
                ELSE 4 
            END,
            u.rank DESC
    ''', (guild_id,)).fetchall()
    
    # Здания
    buildings = conn.execute('''
        SELECT * FROM guild_buildings WHERE guild_id = ?
    ''', (guild_id,)).fetchall()
    
    # Активная война
    active_war = conn.execute('''
        SELECT * FROM guild_wars 
        WHERE (guild1_id = ? OR guild2_id = ?) AND status = 'active'
    ''', (guild_id, guild_id)).fetchone()
    
    # Активный рейд
    active_raid = conn.execute('''
        SELECT * FROM guild_raids 
        WHERE guild_id = ? AND status = 'active'
    ''', (guild_id,)).fetchone()
    
    # Роль пользователя (если передан)
    user_role = None
    if user_id:
        member = conn.execute('''
            SELECT role FROM guild_members WHERE user_id = ?
        ''', (user_id,)).fetchone()
        if member:
            user_role = member['role']
    
    # Для подсчёта опыта до следующего уровня
    exp_for_next = guild['level'] * 1000
    
    conn.close()
    
    return {
        "guild_id": guild['guild_id'],
        "name": guild['name'],
        "emoji": guild['emoji'],
        "description": guild['description'],
        "level": guild['level'],
        "experience": guild['experience'],
        "exp_for_next": exp_for_next,
        "war_points": guild['war_points'],
        "leader_id": guild['leader_id'],
        "leader_name": guild['leader_name'],
        "created_at": guild['created_at'],
        "members": [{
            "user_id": m['user_id'],
            "username": m['username'],
            "role": m['role'],
            "rank": m['rank'],
            "wins": m['wins'],
            "contribution": m['contribution'],
            "skin_name": m['skin_name'] or "Базовый",
            "joined_at": m['joined_at']
        } for m in members],
        "buildings": [{
            "type": b['building_type'],
            "level": b['level'],
            "bonus": get_building_bonus(b['building_type'], b['level'])
        } for b in buildings],
        "active_war": dict(active_war) if active_war else None,
        "active_raid": dict(active_raid) if active_raid else None,
        "user_role": user_role
    }

def get_building_bonus(building_type, level):
    """Возвращает бонус от здания"""
    bonuses = {
        "altar": {"name": "Алтарь", "bonus": f"+{level * 5}% к опыту"},
        "forge": {"name": "Кузница", "bonus": f"+{level * 3}% к урону"},
        "library": {"name": "Библиотека", "bonus": f"-{level * 2}% стоимости скиллов"},
        "watchtower": {"name": "Сторожевая башня", "bonus": f"+{level * 4}% к защите в войнах"}
    }
    return bonuses.get(building_type, {"name": building_type, "bonus": "+0"})

def join_guild(guild_id, user_id):
    """Вступление в гильдию"""
    conn = get_db_connection()
    
    # Проверяем, не в гильдии ли уже
    member = conn.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (user_id,)).fetchone()
    if member:
        conn.close()
        return {"success": False, "error": "Вы уже состоите в гильдии"}
    
    # Проверяем существование гильдии
    guild = conn.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)).fetchone()
    if not guild:
        conn.close()
        return {"success": False, "error": "Гильдия не найдена"}
    
    # Проверяем лимит (30 + 5 за уровень)
    member_count = conn.execute("SELECT COUNT(*) as count FROM guild_members WHERE guild_id = ?", (guild_id,)).fetchone()['count']
    max_members = 30 + (guild['level'] - 1) * 5
    if member_count >= max_members:
        conn.close()
        return {"success": False, "error": f"Гильдия заполнена (макс. {max_members})"}
    
    conn.execute('''
        INSERT INTO guild_members (user_id, guild_id, role)
        VALUES (?, ?, ?)
    ''', (user_id, guild_id, GuildRole.MEMBER.value))
    
    # Добавляем опыт гильдии
    add_guild_experience(conn, guild_id, 100)
    
    conn.commit()
    conn.close()
    
    return {"success": True}

def leave_guild(user_id):
    """Выход из гильдии"""
    conn = get_db_connection()
    
    member = conn.execute("SELECT * FROM guild_members WHERE user_id = ?", (user_id,)).fetchone()
    if not member:
        conn.close()
        return {"success": False, "error": "Вы не состоите в гильдии"}
    
    if member['role'] == GuildRole.LEADER.value:
        conn.close()
        return {"success": False, "error": "Лидер не может покинуть гильдию. Передайте лидерство или распустите гильдию."}
    
    conn.execute("DELETE FROM guild_members WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

def promote_member(leader_id, target_id, new_role):
    """Повышение/понижение участника"""
    conn = get_db_connection()
    
    # Проверяем, что лидер
    leader = conn.execute("SELECT * FROM guild_members WHERE user_id = ? AND role = ?", (leader_id, GuildRole.LEADER.value)).fetchone()
    if not leader:
        conn.close()
        return {"success": False, "error": "Только лидер может менять роли"}
    
    # Проверяем, что цель в той же гильдии
    target = conn.execute("SELECT * FROM guild_members WHERE user_id = ? AND guild_id = ?", (target_id, leader['guild_id'])).fetchone()
    if not target:
        conn.close()
        return {"success": False, "error": "Игрок не в вашей гильдии"}
    
    if target['role'] == GuildRole.LEADER.value:
        conn.close()
        return {"success": False, "error": "Нельзя изменить роль лидера"}
    
    conn.execute("UPDATE guild_members SET role = ? WHERE user_id = ?", (new_role, target_id))
    
    # Если повышаем до лидера — передаём лидерство
    if new_role == GuildRole.LEADER.value:
        conn.execute("UPDATE guild_members SET role = ? WHERE user_id = ?", (GuildRole.OFFICER.value, leader_id))
        conn.execute("UPDATE guilds SET leader_id = ? WHERE guild_id = ?", (target_id, leader['guild_id']))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

def add_guild_experience(conn, guild_id, amount):
    """Добавляет опыт гильдии и проверяет повышение уровня"""
    guild = conn.execute("SELECT level, experience FROM guilds WHERE guild_id = ?", (guild_id,)).fetchone()
    if not guild:
        return
    
    new_exp = guild['experience'] + amount
    new_level = guild['level']
    
    while new_exp >= new_level * 1000:
        new_exp -= new_level * 1000
        new_level += 1
    
    conn.execute('''
        UPDATE guilds SET level = ?, experience = ? WHERE guild_id = ?
    ''', (new_level, new_exp, guild_id))

def upgrade_building(guild_id, building_type, user_id):
    """Улучшение здания гильдии"""
    conn = get_db_connection()
    
    # Проверяем права (лидер или офицер)
    member = conn.execute('''
        SELECT role FROM guild_members 
        WHERE user_id = ? AND guild_id = ?
    ''', (user_id, guild_id)).fetchone()
    
    if not member or member['role'] not in [GuildRole.LEADER.value, GuildRole.OFFICER.value]:
        conn.close()
        return {"success": False, "error": "Недостаточно прав"}
    
    building = conn.execute('''
        SELECT level FROM guild_buildings 
        WHERE guild_id = ? AND building_type = ?
    ''', (guild_id, building_type)).fetchone()
    
    if not building:
        conn.close()
        return {"success": False, "error": "Здание не найдено"}
    
    # Стоимость улучшения
    cost = building['level'] * 200
    guild = conn.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)).fetchone()
    
    # Проверяем общий вклад участников (упрощённо — используем war_points)
    if guild['war_points'] < cost:
        conn.close()
        return {"success": False, "error": f"Недостаточно очков гильдии (нужно {cost})"}
    
    conn.execute("UPDATE guilds SET war_points = war_points - ? WHERE guild_id = ?", (cost, guild_id))
    conn.execute('''
        UPDATE guild_buildings SET level = level + 1 
        WHERE guild_id = ? AND building_type = ?
    ''', (guild_id, building_type))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "new_level": building['level'] + 1}

def contribute_to_guild(user_id, amount):
    """Внесение вклада в гильдию (осколками)"""
    conn = get_db_connection()
    
    member = conn.execute("SELECT * FROM guild_members WHERE user_id = ?", (user_id,)).fetchone()
    if not member:
        conn.close()
        return {"success": False, "error": "Вы не в гильдии"}
    
    user = get_user(user_id)
    if user['shards'] < amount:
        conn.close()
        return {"success": False, "error": "Недостаточно осколков"}
    
    # Списываем осколки
    update_user_field(user_id, 'shards', user['shards'] - amount)
    
    # Добавляем очки гильдии (1 осколок = 2 очка)
    conn.execute("UPDATE guilds SET war_points = war_points + ? WHERE guild_id = ?", (amount * 2, member['guild_id']))
    
    # Увеличиваем вклад игрока
    conn.execute("UPDATE guild_members SET contribution = contribution + ? WHERE user_id = ?", (amount, user_id))
    
    # Добавляем опыт гильдии
    add_guild_experience(conn, member['guild_id'], amount)
    
    conn.commit()
    conn.close()
    
    return {"success": True}

# ------------------------------------------------------------
# Чат гильдии
# ------------------------------------------------------------

def send_guild_message(guild_id, user_id, username, message):
    """Отправка сообщения в чат гильдии"""
    if len(message) > 500:
        return {"success": False, "error": "Сообщение слишком длинное"}
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO guild_chat (guild_id, user_id, username, message)
        VALUES (?, ?, ?, ?)
    ''', (guild_id, user_id, username, message))
    conn.commit()
    conn.close()
    
    return {"success": True}

def get_guild_messages(guild_id, limit=50):
    """Получение последних сообщений чата"""
    conn = get_db_connection()
    messages = conn.execute('''
        SELECT * FROM guild_chat 
        WHERE guild_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (guild_id, limit)).fetchall()
    conn.close()
    
    return [{
        "user_id": m['user_id'],
        "username": m['username'],
        "message": m['message'],
        "timestamp": m['timestamp']
    } for m in reversed(messages)]

# ------------------------------------------------------------
# Войны гильдий
# ------------------------------------------------------------

def start_guild_war(guild1_id, guild2_id):
    """Запуск войны между гильдиями"""
    war_id = str(uuid.uuid4())[:8]
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO guild_wars (war_id, guild1_id, guild2_id, status, started_at)
        VALUES (?, ?, ?, 'active', ?)
    ''', (war_id, guild1_id, guild2_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {"success": True, "war_id": war_id}

def add_war_points(war_id, guild_id, points):
    """Добавление очков в войне"""
    conn = get_db_connection()
    
    war = conn.execute("SELECT * FROM guild_wars WHERE war_id = ? AND status = 'active'", (war_id,)).fetchone()
    if not war:
        conn.close()
        return {"success": False, "error": "Война не найдена или завершена"}
    
    if guild_id == war['guild1_id']:
        conn.execute("UPDATE guild_wars SET guild1_points = guild1_points + ? WHERE war_id = ?", (points, war_id))
    else:
        conn.execute("UPDATE guild_wars SET guild2_points = guild2_points + ? WHERE war_id = ?", (points, war_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

def end_guild_war(war_id):
    """Завершение войны и начисление наград"""
    conn = get_db_connection()
    
    war = conn.execute("SELECT * FROM guild_wars WHERE war_id = ?", (war_id,)).fetchone()
    if not war:
        conn.close()
        return {"success": False, "error": "Война не найдена"}
    
    winner_id = war['guild1_id'] if war['guild1_points'] > war['guild2_points'] else war['guild2_id']
    loser_id = war['guild2_id'] if winner_id == war['guild1_id'] else war['guild1_id']
    
    conn.execute('''
        UPDATE guild_wars SET status = 'finished', winner_id = ?, ended_at = ?
        WHERE war_id = ?
    ''', (winner_id, datetime.now().isoformat(), war_id))
    
    # Награды: +500 war_points победителю, +100 проигравшему
    conn.execute("UPDATE guilds SET war_points = war_points + 500 WHERE guild_id = ?", (winner_id,))
    conn.execute("UPDATE guilds SET war_points = war_points + 100 WHERE guild_id = ?", (loser_id,))
    
    # Награды участникам
    winner_members = conn.execute("SELECT user_id FROM guild_members WHERE guild_id = ?", (winner_id,)).fetchall()
    loser_members = conn.execute("SELECT user_id FROM guild_members WHERE guild_id = ?", (loser_id,)).fetchall()
    
    for m in winner_members:
        user = get_user(m['user_id'])
        if user:
            update_user_field(m['user_id'], 'shards', user['shards'] + 200)
    
    for m in loser_members:
        user = get_user(m['user_id'])
        if user:
            update_user_field(m['user_id'], 'shards', user['shards'] + 50)
    
    conn.commit()
    conn.close()
    
    return {"success": True, "winner_id": winner_id}

# ------------------------------------------------------------
# Рейды
# ------------------------------------------------------------

RAID_BOSSES = [
    {"name": "Древний дракон", "hp": 100000, "rewards": {"shards": 500, "skin_id": None}},
    {"name": "Титан бездны", "hp": 250000, "rewards": {"shards": 1000, "skin_id": 1}},
    {"name": "Король элементалей", "hp": 500000, "rewards": {"shards": 2000, "skin_id": 2}},
    {"name": "Повелитель хаоса", "hp": 1000000, "rewards": {"shards": 5000, "skin_id": 3}},
]

def start_guild_raid(guild_id, boss_level=1):
    """Запуск рейда гильдии"""
    if boss_level < 1 or boss_level > 4:
        return {"success": False, "error": "Неверный уровень босса"}
    
    boss_data = RAID_BOSSES[boss_level - 1]
    raid_id = str(uuid.uuid4())[:8]
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO guild_raids (raid_id, guild_id, boss_name, boss_max_hp, boss_current_hp)
        VALUES (?, ?, ?, ?, ?)
    ''', (raid_id, guild_id, boss_data['name'], boss_data['hp'], boss_data['hp']))
    conn.commit()
    conn.close()
    
    return {"success": True, "raid_id": raid_id}

def attack_raid_boss(raid_id, user_id, damage):
    """Атака рейдового босса"""
    conn = get_db_connection()
    
    raid = conn.execute("SELECT * FROM guild_raids WHERE raid_id = ? AND status = 'active'", (raid_id,)).fetchone()
    if not raid:
        conn.close()
        return {"success": False, "error": "Рейд не найден или завершён"}
    
    new_hp = max(0, raid['boss_current_hp'] - damage)
    conn.execute("UPDATE guild_raids SET boss_current_hp = ? WHERE raid_id = ?", (new_hp, raid_id))
    
    # Сохраняем урон игрока
    conn.execute('''
        INSERT INTO guild_raid_damage (user_id, raid_id, damage)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, raid_id) DO UPDATE SET damage = damage + ?
    ''', (user_id, raid_id, damage, damage))
    
    # Добавляем очки гильдии
    conn.execute("UPDATE guilds SET war_points = war_points + ? WHERE guild_id = ?", (damage // 10, raid['guild_id']))
    
    if new_hp <= 0:
        # Рейд завершён
        conn.execute('''
            UPDATE guild_raids SET status = 'completed', ended_at = ? WHERE raid_id = ?
        ''', (datetime.now().isoformat(), raid_id))
        
        # Распределяем награды
        boss_level = 1
        for i, boss in enumerate(RAID_BOSSES):
            if boss['name'] == raid['boss_name']:
                boss_level = i + 1
                break
        
        rewards = RAID_BOSSES[boss_level - 1]['rewards']
        
        # Топ-3 по урону получают бонус
        top_damagers = conn.execute('''
            SELECT user_id, damage FROM guild_raid_damage 
            WHERE raid_id = ? 
            ORDER BY damage DESC 
            LIMIT 3
        ''', (raid_id,)).fetchall()
        
        # Всем участникам базовые награды
        all_participants = conn.execute('''
            SELECT user_id FROM guild_raid_damage WHERE raid_id = ?
        ''', (raid_id,)).fetchall()
        
        for p in all_participants:
            user = get_user(p['user_id'])
            if user:
                update_user_field(p['user_id'], 'shards', user['shards'] + rewards['shards'] // len(all_participants))
        
        # Топ-3 дополнительно
        for i, td in enumerate(top_damagers):
            user = get_user(td['user_id'])
            if user:
                bonus = [300, 200, 100][i]
                update_user_field(td['user_id'], 'shards', user['shards'] + bonus)
                if i == 0 and rewards['skin_id']:
                    from database import add_skin_to_user
                    add_skin_to_user(td['user_id'], rewards['skin_id'])
    
    conn.commit()
    conn.close()
    
    return {"success": True, "boss_current_hp": new_hp, "raid_completed": new_hp <= 0}

# ------------------------------------------------------------
# Поиск и список гильдий
# ------------------------------------------------------------

def search_guilds(query=""):
    """Поиск гильдий по названию"""
    conn = get_db_connection()
    
    if query:
        guilds = conn.execute('''
            SELECT g.*, u.username as leader_name, 
                   (SELECT COUNT(*) FROM guild_members WHERE guild_id = g.guild_id) as member_count
            FROM guilds g
            JOIN users u ON g.leader_id = u.user_id
            WHERE g.name LIKE ?
            ORDER BY g.level DESC, g.war_points DESC
            LIMIT 20
        ''', (f'%{query}%',)).fetchall()
    else:
        guilds = conn.execute('''
            SELECT g.*, u.username as leader_name,
                   (SELECT COUNT(*) FROM guild_members WHERE guild_id = g.guild_id) as member_count
            FROM guilds g
            JOIN users u ON g.leader_id = u.user_id
            ORDER BY g.level DESC, g.war_points DESC
            LIMIT 20
        ''',).fetchall()
    
    conn.close()
    
    return [{
        "guild_id": g['guild_id'],
        "name": g['name'],
        "emoji": g['emoji'],
        "level": g['level'],
        "war_points": g['war_points'],
        "member_count": g['member_count'],
        "leader_name": g['leader_name']
    } for g in guilds]

def get_guild_leaderboard():
    """Топ гильдий"""
    conn = get_db_connection()
    
    guilds = conn.execute('''
        SELECT g.guild_id, g.name, g.emoji, g.level, g.war_points,
               (SELECT COUNT(*) FROM guild_members WHERE guild_id = g.guild_id) as member_count,
               u.username as leader_name
        FROM guilds g
        JOIN users u ON g.leader_id = u.user_id
        ORDER BY g.war_points DESC
        LIMIT 20
    ''',).fetchall()
    
    conn.close()
    
    return [dict(g) for g in guilds]
