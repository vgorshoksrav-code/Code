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

    # ... (все остальные таблицы, как в предыдущей версии) ...
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
            daily_tickets INTEGER DEFAULT 3,
            last_login_date TEXT,
            chain_counter INTEGER DEFAULT 0,
            hero_levels TEXT DEFAULT '[1,1,1,1,1]',
            equipped_skin_id INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY,
            name TEXT,
            rarity TEXT,
            price_stars INTEGER,
            stat_bonus TEXT,
            animation_url TEXT
        )
    ''')
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
    # Новая таблица для настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Заполнение начальными скинами
    cursor.execute("SELECT COUNT(*) FROM skins")
    if cursor.fetchone()[0] == 0:
        skins_data = [
            (1, 'Призрачный рыцарь', 'rare', 500, '{"attack_pct":5}', ''),
            (2, 'Эхарис', 'legendary', 2500, '{"attack_pct":10, "defense_pct":10}', ''),
            (3, 'Повелитель вселенных', 'vip', 5000, '{"attack_pct":15, "defense_pct":15, "energy_pct":15}', ''),
            (4, 'Страж пустоты', 'common', 0, '{"defense_pct":1}', ''),
            (5, 'Пламенный клинок', 'rare', 300, '{"attack_pct":3}', '')
        ]
        cursor.executemany('INSERT INTO skins (id, name, rarity, price_stars, stat_bonus, animation_url) VALUES (?,?,?,?,?,?)', skins_data)

    # Установка значения WEBAPP_URL по умолчанию (если не задано)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('webapp_url', ?)", ('https://ваш-проект.amvera.io',))
    conn.commit()
    conn.close()

# Функции для работы с настройками
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

# Остальные CRUD функции (get_user, create_or_update_user и т.д.) остаются без изменений
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
            INSERT INTO users (user_id, username, hero_levels, equipped_skin_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, '[1,1,1,1,1]', 1))
        cursor.execute("INSERT OR IGNORE INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, ?)", (user_id, 4, 0))
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
