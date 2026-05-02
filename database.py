import sqlite3, json, os
from config import DB_PATH

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _col(c, t, col, df):
    try: c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {df}")
    except: pass

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT,
        rank INTEGER DEFAULT 1000, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
        shards INTEGER DEFAULT 100, stars_spent INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0, daily_tickets INTEGER DEFAULT 5,
        last_login_date TEXT, last_gift_date TEXT, chain_counter INTEGER DEFAULT 0,
        hero_levels TEXT DEFAULT '[1,1,1,1,1]', equipped_skin_id INTEGER DEFAULT 4,
        hero_class TEXT DEFAULT 'warrior', language TEXT DEFAULT 'ru',
        welcome_bonus_claimed INTEGER DEFAULT 0,
        temp_skin_id INTEGER DEFAULT 0, temp_skin_expires TEXT,
        equipped_pawn_id INTEGER DEFAULT 0
    )''')
    for col,df in [('last_gift_date','TEXT'),('hero_class',"TEXT DEFAULT 'warrior'"),
                   ('language',"TEXT DEFAULT 'ru'"),('welcome_bonus_claimed','INTEGER DEFAULT 0'),
                   ('temp_skin_id','INTEGER DEFAULT 0'),('temp_skin_expires','TEXT'),
                   ('equipped_pawn_id','INTEGER DEFAULT 0')]:
        _col(c,'users',col,df)

    c.execute('''CREATE TABLE IF NOT EXISTS skins (
        id INTEGER PRIMARY KEY, name TEXT, rarity TEXT, price_stars INTEGER,
        stat_bonus TEXT, animation_url TEXT, emoji TEXT DEFAULT '🧙',
        description TEXT DEFAULT '', hero_class TEXT DEFAULT 'all'
    )''')
    for col,df in [('emoji',"TEXT DEFAULT '🧙'"),('description',"TEXT DEFAULT ''"),
                   ('hero_class',"TEXT DEFAULT 'all'")]:
        _col(c,'skins',col,df)

    c.execute('''CREATE TABLE IF NOT EXISTS pawns (
        id INTEGER PRIMARY KEY, name TEXT, rarity TEXT,
        emoji TEXT, description TEXT, stat_bonus TEXT DEFAULT '{}',
        price_shards INTEGER DEFAULT 0, price_stars INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_skins (
        user_id INTEGER, skin_id INTEGER, equipped INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, skin_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_pawns (
        user_id INTEGER, pawn_id INTEGER, equipped INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, pawn_id)
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
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user_id INTEGER, friend_id INTEGER, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, friend_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS friend_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenger_id INTEGER, challenged_id INTEGER,
        mode TEXT DEFAULT 'pvp',
        match_id TEXT, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY, reward_type TEXT NOT NULL,
        reward_value TEXT NOT NULL, max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0, expires_at TEXT,
        created_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
        code TEXT, user_id INTEGER, used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (code, user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS guild_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        quest_type TEXT, target INTEGER, progress INTEGER DEFAULT 0,
        reward TEXT, completed INTEGER DEFAULT 0, expires_at TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT,
        icon TEXT DEFAULT '🎉', event_type TEXT, multiplier REAL DEFAULT 1.5,
        starts_at TEXT, ends_at TEXT, active INTEGER DEFAULT 1, created_by INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaign_progress (
        user_id INTEGER PRIMARY KEY,
        completed_bosses TEXT DEFAULT '[]', completed_chapters TEXT DEFAULT '[]',
        current_boss_id INTEGER DEFAULT 1, current_chapter INTEGER DEFAULT 1
    )''')

    # Skins seed
    c.execute("SELECT COUNT(*) FROM skins")
    if c.fetchone()[0] == 0:
        skins = [
            (1,'Призрачный рыцарь','rare',500,'{"attack_pct":5}','','⚔️','Призрак прошлых сражений','warrior'),
            (2,'Эхарис','legendary',2500,'{"attack_pct":10,"defense_pct":10}','','🌌','Воплощение Эхариса','all'),
            (3,'Повелитель вселенных','vip',5000,'{"attack_pct":15,"defense_pct":15,"energy_pct":15}','','👑','Только для VIP','all'),
            (4,'Страж пустоты','common',0,'{"defense_pct":1}','','🧙','Стартовый страж','all'),
            (5,'Пламенный клинок','rare',300,'{"attack_pct":3}','','🔥','Кован в вулкане','warrior'),
            (6,'Ледяной маг','rare',400,'{"defense_pct":5,"energy_pct":3}','','❄️','Мастер холода','mage'),
            (7,'Громовержец','epic',800,'{"attack_pct":8,"energy_pct":5}','','⚡','Молнии небес','all'),
            (8,'Теневой убийца','epic',900,'{"attack_pct":12}','','🌑','Смерть во тьме','rogue'),
            (9,'Лесной друид','rare',350,'{"defense_pct":3,"energy_pct":5}','','🌿','Защитник леса','druid'),
            (10,'Некромант','epic',1000,'{"attack_pct":7,"defense_pct":7}','','💀','Повелитель мёртвых','necromancer'),
            (11,'Солнечный паладин','legendary',1800,'{"attack_pct":8,"defense_pct":12}','','☀️','Несёт свет','paladin'),
            (12,'Водный призыватель','rare',450,'{"energy_pct":10,"defense_pct":2}','','🌊','Стихия воды','mage'),
            (13,'Звёздный странник','legendary',2000,'{"attack_pct":12,"energy_pct":8}','','✨','Из другой галактики','all'),
            (14,'Кровавый берсерк','epic',1200,'{"attack_pct":15,"defense_pct":-3}','','🩸','Ярость без предела','warrior'),
            (15,'Кристальный голем','epic',1100,'{"defense_pct":15,"energy_pct":-2}','','💎','Кристальная броня','all'),
            (16,'Архангел','legendary',3000,'{"attack_pct":12,"defense_pct":12,"energy_pct":5}','','👼','Посланник небес','paladin'),
            (17,'Демонолог','epic',1500,'{"attack_pct":18,"defense_pct":-5}','','😈','Призыватель демонов','necromancer'),
            (18,'Ветровой монах','rare',500,'{"energy_pct":15}','','🌪️','Скорость ветра','druid'),
            (19,'Пиратский капитан','epic',950,'{"attack_pct":6,"energy_pct":6,"defense_pct":3}','','🏴‍☠️','Гроза морей','rogue'),
            (20,'Хранитель времени','legendary',2200,'{"attack_pct":9,"defense_pct":9,"energy_pct":9}','','⏳','Управляет временем','all'),
        ]
        c.executemany('INSERT INTO skins VALUES(?,?,?,?,?,?,?,?,?)', skins)

    # Pawns seed
    c.execute("SELECT COUNT(*) FROM pawns")
    if c.fetchone()[0] == 0:
        pawns = [
            (1,'Огненный фамильяр','rare','🐉','Маленький дракон — +3% атаки','{"attack_pct":3}',300,0),
            (2,'Ледяная сова','rare','🦉','Зоркая сова — +3% защиты','{"defense_pct":3}',300,0),
            (3,'Громовой феникс','epic','🦅','Феникс из молний — +5% атаки','{"attack_pct":5}',700,0),
            (4,'Теневой волк','epic','🐺','Призрачный волк — +4% атаки, +2% защиты','{"attack_pct":4,"defense_pct":2}',800,0),
            (5,'Звёздный котёнок','legendary','🐱','Котёнок из созвездий — +6% ко всему','{"attack_pct":6,"defense_pct":6,"energy_pct":6}',0,500),
            (6,'Кристальный паук','common','🕷️','Мелкий паук — +1% защиты','{"defense_pct":1}',50,0),
            (7,'Призрачный кролик','rare','🐰','Кролик-призрак — +5% энергии','{"energy_pct":5}',350,0),
            (8,'Древесный дух','uncommon','🌱','Дух дерева — +2% защиты, +2% энергии','{"defense_pct":2,"energy_pct":2}',150,0),
        ]
        c.executemany('INSERT INTO pawns VALUES(?,?,?,?,?,?,?,?)', pawns)

    c.execute("INSERT OR IGNORE INTO settings VALUES('webapp_url','https://ваш-проект.amvera.io')")
    conn.commit(); conn.close()

def get_setting(k):
    c=get_db_connection(); r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone(); c.close()
    return r['value'] if r else None

def set_setting(k,v):
    c=get_db_connection(); c.execute("REPLACE INTO settings VALUES(?,?)",(k,v)); c.commit(); c.close()

def get_user(uid):
    c=get_db_connection(); u=c.execute("SELECT * FROM users WHERE user_id=?",(uid,)).fetchone(); c.close(); return u

def create_or_update_user(uid, uname):
    conn=get_db_connection(); c=conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?",(uid,))
    if not c.fetchone():
        c.execute('INSERT INTO users(user_id,username,hero_levels,equipped_skin_id,daily_tickets,shards) VALUES(?,?,?,?,?,?)',
                  (uid,uname,'[1,1,1,1,1]',4,5,100))
        c.execute("INSERT OR IGNORE INTO user_skins VALUES(?,?,1)",(uid,4))
        conn.commit(); conn.close(); return True
    c.execute("UPDATE users SET username=? WHERE user_id=?",(uname,uid)); conn.commit(); conn.close(); return False

def update_user_field(uid, field, value):
    c=get_db_connection(); c.execute(f"UPDATE users SET {field}=? WHERE user_id=?",(value,uid)); c.commit(); c.close()

def add_skin_to_user(uid, sid):
    c=get_db_connection(); c.execute("INSERT OR IGNORE INTO user_skins VALUES(?,?,0)",(uid,sid)); c.commit(); c.close()
