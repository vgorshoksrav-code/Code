import sqlite3
import json
import os
from config import DB_PATH

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            rank INTEGER DEFAULT 1000,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            shards INTEGER DEFAULT 0,
            stars_spent INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            daily_tickets INTEGER DEFAULT 5,
            last_login_date TEXT,
            last_gift_date TEXT,
            chain_counter INTEGER DEFAULT 0,
            hero_levels TEXT DEFAULT '[1,1,1,1,1]',
            equipped_skin_id INTEGER DEFAULT 4,
            hero_avatar TEXT DEFAULT 'warrior',
            language TEXT DEFAULT 'ru'
        )
    ''')

    # Try to add new columns if they don't exist (migration)
    for col, coldef in [
        ('last_gift_date', 'TEXT'),
        ('hero_avatar', "TEXT DEFAULT 'warrior'"),
        ('language', "TEXT DEFAULT 'ru'"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {coldef}")
        except Exception:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY,
            name TEXT,
            rarity TEXT,
            price_stars INTEGER,
            stat_bonus TEXT,
            animation_url TEXT,
            emoji TEXT DEFAULT '🧙',
            description TEXT DEFAULT ''
        )
    ''')
    for col, coldef in [('emoji', "TEXT DEFAULT '🧙'"), ('description', "TEXT DEFAULT ''")]:
        try:
            cursor.execute(f"ALTER TABLE skins ADD COLUMN {col} {coldef}")
        except Exception:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_skins (
            user_id INTEGER,
            skin_id INTEGER,
            equipped INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, skin_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER,
            referred_id INTEGER PRIMARY KEY,
            reward_claimed INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER,
            player2_id INTEGER,
            winner_id INTEGER,
            log TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_matches (
            user_id INTEGER PRIMARY KEY,
            timestamp INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Guilds tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id TEXT PRIMARY KEY,
            name TEXT UNIQUE,
            emoji TEXT DEFAULT '🏰',
            description TEXT DEFAULT '',
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            war_points INTEGER DEFAULT 0,
            treasury INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_members (
            user_id INTEGER PRIMARY KEY,
            guild_id TEXT,
            role TEXT DEFAULT 'member',
            contribution INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_buildings (
            guild_id TEXT,
            building_type TEXT,
            level INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, building_type)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_raids (
            raid_id TEXT PRIMARY KEY,
            guild_id TEXT,
            boss_name TEXT,
            boss_max_hp INTEGER,
            boss_current_hp INTEGER,
            boss_level INTEGER DEFAULT 1,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_progress (
            user_id INTEGER PRIMARY KEY,
            completed_bosses TEXT DEFAULT '[]',
            completed_chapters TEXT DEFAULT '[]',
            current_boss_id INTEGER DEFAULT 1,
            current_chapter INTEGER DEFAULT 1
        )
    ''')

    # Skins data — расширенный список
    cursor.execute("SELECT COUNT(*) FROM skins")
    if cursor.fetchone()[0] == 0:
        skins_data = [
            (1,  'Призрачный рыцарь',    'rare',      500,  '{"attack_pct":5}',                             '', '⚔️', 'Призрак прошлых сражений'),
            (2,  'Эхарис',               'legendary', 2500, '{"attack_pct":10,"defense_pct":10}',           '', '🌌', 'Воплощение самого Эхариса'),
            (3,  'Повелитель вселенных', 'vip',       5000, '{"attack_pct":15,"defense_pct":15,"energy_pct":15}','','👑', 'Для избранных VIP'),
            (4,  'Страж пустоты',        'common',    0,    '{"defense_pct":1}',                            '', '🧙', 'Стартовый страж'),
            (5,  'Пламенный клинок',     'rare',      300,  '{"attack_pct":3}',                             '', '🔥', 'Клинок из вулканического железа'),
            (6,  'Ледяной маг',          'rare',      400,  '{"defense_pct":5,"energy_pct":3}',             '', '❄️', 'Мастер льда и холода'),
            (7,  'Громовержец',          'epic',      800,  '{"attack_pct":8,"energy_pct":5}',              '', '⚡', 'Призывает молнии небес'),
            (8,  'Теневой убийца',       'epic',      900,  '{"attack_pct":12}',                            '', '🌑', 'Смерть во тьме'),
            (9,  'Лесной друид',         'rare',      350,  '{"defense_pct":3,"energy_pct":5}',             '', '🌿', 'Защитник леса'),
            (10, 'Некромант',            'epic',      1000, '{"attack_pct":7,"defense_pct":7}',             '', '💀', 'Повелитель мёртвых'),
            (11, 'Солнечный паладин',    'legendary', 1800, '{"attack_pct":8,"defense_pct":12}',            '', '☀️', 'Несёт свет в темноту'),
            (12, 'Водный призыватель',   'rare',      450,  '{"energy_pct":10,"defense_pct":2}',            '', '🌊', 'Командует стихией воды'),
            (13, 'Звёздный странник',    'legendary', 2000, '{"attack_pct":12,"energy_pct":8}',             '', '✨', 'Пришёл из другой галактики'),
            (14, 'Кровавый берсерк',     'epic',      1200, '{"attack_pct":15,"defense_pct":-3}',           '', '🩸', 'Ярость без границ'),
            (15, 'Кристальный голем',    'epic',      1100, '{"defense_pct":15,"energy_pct":-2}',           '', '💎', 'Непробиваемая броня'),
        ]
        cursor.executemany(
            'INSERT INTO skins (id,name,rarity,price_stars,stat_bonus,animation_url,emoji,description) VALUES (?,?,?,?,?,?,?,?)',
            skins_data
        )

    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('webapp_url', ?)", ('https://ваш-проект.amvera.io',))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else None

def set_setting(key, value):
    conn = get_db_connection()
    conn.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def create_or_update_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, hero_levels, equipped_skin_id, daily_tickets)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, '[1,1,1,1,1]', 4, 5))
        cursor.execute("INSERT OR IGNORE INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, ?)", (user_id, 4, 1))
        conn.commit()
    else:
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()
    conn.close()

def update_user_field(user_id, field, value):
    conn = get_db_connection()
    conn.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def add_skin_to_user(user_id, skin_id):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (user_id, skin_id))
    conn.commit()
    conn.close()
