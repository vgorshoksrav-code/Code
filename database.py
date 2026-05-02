import sqlite3, json, os
from config import DB_PATH

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _add_col(cursor, table, col, coldef):
    try: cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
    except: pass

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT,
        rank INTEGER DEFAULT 1000, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
        shards INTEGER DEFAULT 100, stars_spent INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0, daily_tickets INTEGER DEFAULT 5,
        last_login_date TEXT, last_gift_date TEXT,
        chain_counter INTEGER DEFAULT 0,
        hero_levels TEXT DEFAULT '[1,1,1,1,1]',
        equipped_skin_id INTEGER DEFAULT 4,
        hero_class TEXT DEFAULT 'warrior',
        language TEXT DEFAULT 'ru',
        welcome_bonus_claimed INTEGER DEFAULT 0,
        temp_skin_id INTEGER DEFAULT 0,
        temp_skin_expires TEXT DEFAULT NULL
    )''')
    for col, df in [
        ('last_gift_date','TEXT'), ('hero_class',"TEXT DEFAULT 'warrior'"),
        ('language',"TEXT DEFAULT 'ru'"), ('welcome_bonus_claimed','INTEGER DEFAULT 0'),
        ('temp_skin_id','INTEGER DEFAULT 0'), ('temp_skin_expires','TEXT DEFAULT NULL'),
    ]:
        _add_col(c, 'users', col, df)

    c.execute('''CREATE TABLE IF NOT EXISTS skins (
        id INTEGER PRIMARY KEY, name TEXT, rarity TEXT,
        price_stars INTEGER, stat_bonus TEXT, animation_url TEXT,
        emoji TEXT DEFAULT '🧙', description TEXT DEFAULT '',
        hero_class TEXT DEFAULT 'all'
    )''')
    for col, df in [('emoji',"TEXT DEFAULT '🧙'"), ('description',"TEXT DEFAULT ''"), ('hero_class',"TEXT DEFAULT 'all'")]:
        _add_col(c, 'skins', col, df)

    c.execute('''CREATE TABLE IF NOT EXISTS user_skins (
        user_id INTEGER, skin_id INTEGER, equipped INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, skin_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY, added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        referrer_id INTEGER, referred_id INTEGER PRIMARY KEY,
        reward_claimed INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id INTEGER, player2_id INTEGER, winner_id INTEGER,
        log TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )''')

    # Promo codes
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        reward_type TEXT NOT NULL,
        reward_value TEXT NOT NULL,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expires_at TEXT DEFAULT NULL,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
        code TEXT, user_id INTEGER,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (code, user_id)
    )''')

    # Guild quests
    c.execute('''CREATE TABLE IF NOT EXISTS guild_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT, quest_type TEXT,
        target INTEGER, progress INTEGER DEFAULT 0,
        reward TEXT, completed INTEGER DEFAULT 0,
        expires_at TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Temporary events
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, description TEXT, icon TEXT DEFAULT '🎉',
        event_type TEXT,
        multiplier REAL DEFAULT 1.5,
        starts_at TEXT, ends_at TEXT,
        active INTEGER DEFAULT 1, created_by INTEGER
    )''')

    # Campaign progress
    c.execute('''CREATE TABLE IF NOT EXISTS campaign_progress (
        user_id INTEGER PRIMARY KEY,
        completed_bosses TEXT DEFAULT '[]',
        completed_chapters TEXT DEFAULT '[]',
        current_boss_id INTEGER DEFAULT 1,
        current_chapter INTEGER DEFAULT 1
    )''')

    # Populate skins
    c.execute("SELECT COUNT(*) FROM skins")
    if c.fetchone()[0] == 0:
        skins = [
            (1,  'Призрачный рыцарь',    'rare',      500,  '{"attack_pct":5}',                                   '','⚔️','Призрак прошлых сражений','warrior'),
            (2,  'Эхарис',               'legendary', 2500, '{"attack_pct":10,"defense_pct":10}',                 '','🌌','Воплощение самого Эхариса','all'),
            (3,  'Повелитель вселенных', 'vip',       5000, '{"attack_pct":15,"defense_pct":15,"energy_pct":15}', '','👑','Только для VIP-избранных','all'),
            (4,  'Страж пустоты',        'common',    0,    '{"defense_pct":1}',                                  '','🧙','Стартовый страж','all'),
            (5,  'Пламенный клинок',     'rare',      300,  '{"attack_pct":3}',                                   '','🔥','Кован в жерле вулкана','warrior'),
            (6,  'Ледяной маг',          'rare',      400,  '{"defense_pct":5,"energy_pct":3}',                   '','❄️','Мастер холода','mage'),
            (7,  'Громовержец',          'epic',      800,  '{"attack_pct":8,"energy_pct":5}',                    '','⚡','Призывает небесные молнии','all'),
            (8,  'Теневой убийца',       'epic',      900,  '{"attack_pct":12}',                                  '','🌑','Смерть приходит во тьме','rogue'),
            (9,  'Лесной друид',         'rare',      350,  '{"defense_pct":3,"energy_pct":5}',                   '','🌿','Защитник древнего леса','druid'),
            (10, 'Некромант',            'epic',      1000, '{"attack_pct":7,"defense_pct":7}',                   '','💀','Повелитель мёртвых','necromancer'),
            (11, 'Солнечный паладин',    'legendary', 1800, '{"attack_pct":8,"defense_pct":12}',                  '','☀️','Несёт свет в темноту','paladin'),
            (12, 'Водный призыватель',   'rare',      450,  '{"energy_pct":10,"defense_pct":2}',                  '','🌊','Командует морской стихией','mage'),
            (13, 'Звёздный странник',    'legendary', 2000, '{"attack_pct":12,"energy_pct":8}',                   '','✨','Пришёл из другой галактики','all'),
            (14, 'Кровавый берсерк',     'epic',      1200, '{"attack_pct":15,"defense_pct":-3}',                 '','🩸','Ярость без предела','warrior'),
            (15, 'Кристальный голем',    'epic',      1100, '{"defense_pct":15,"energy_pct":-2}',                 '','💎','Броня из чистых кристаллов','all'),
            (16, 'Архангел',             'legendary', 3000, '{"attack_pct":12,"defense_pct":12,"energy_pct":5}',  '','👼','Посланник небес','paladin'),
            (17, 'Демонолог',            'epic',      1500, '{"attack_pct":18,"defense_pct":-5}',                 '','😈','Призывает демонов на помощь','necromancer'),
            (18, 'Ветровой монах',       'rare',      500,  '{"energy_pct":15}',                                  '','🌪️','Скорость ветра','druid'),
            (19, 'Пиратский капитан',    'epic',      950,  '{"attack_pct":6,"energy_pct":6,"defense_pct":3}',   '','🏴‍☠️','Гроза морей','rogue'),
            (20, 'Хранитель времени',    'legendary', 2200, '{"attack_pct":9,"defense_pct":9,"energy_pct":9}',   '','⏳','Управляет самим временем','all'),
        ]
        c.executemany('INSERT INTO skins VALUES (?,?,?,?,?,?,?,?,?)', skins)

    c.execute("INSERT OR IGNORE INTO settings VALUES ('webapp_url','https://ваш-проект.amvera.io')")
    conn.commit(); conn.close()

def get_setting(key):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else None

def set_setting(key, value):
    conn = get_db_connection()
    conn.execute("REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit(); conn.close()

def get_user(user_id):
    conn = get_db_connection()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u

def create_or_update_user(user_id, username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute('''INSERT INTO users (user_id,username,hero_levels,equipped_skin_id,daily_tickets,shards)
                     VALUES (?,?,?,?,?,?)''', (user_id, username, '[1,1,1,1,1]', 4, 5, 100))
        c.execute("INSERT OR IGNORE INTO user_skins VALUES (?,?,1)", (user_id, 4))
        conn.commit(); conn.close()
        return True  # new user
    else:
        c.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
        conn.commit(); conn.close()
        return False

def update_user_field(user_id, field, value):
    conn = get_db_connection()
    conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
    conn.commit(); conn.close()

def add_skin_to_user(user_id, skin_id):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO user_skins VALUES (?,?,0)", (user_id, skin_id))
    conn.commit(); conn.close()
