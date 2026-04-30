import json
from database import get_db_connection, add_skin_to_user, update_user_field, get_user, get_setting, set_setting

def is_admin(user_id):
    conn = get_db_connection()
    admin = conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return admin is not None

def add_admin(admin_id, added_by):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (admin_id, added_by))
    conn.commit()
    conn.close()

def remove_admin(admin_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
    conn.commit()
    conn.close()

def get_all_skins():
    conn = get_db_connection()
    skins = conn.execute("SELECT id, name, rarity, price_stars, stat_bonus FROM skins").fetchall()
    conn.close()
    return skins

def give_skin_to_user(user_id, skin_id):
    add_skin_to_user(user_id, skin_id)

def add_stars_to_user(user_id, amount):
    user = get_user(user_id)
    if user:
        new_spent = user['stars_spent'] + amount
        update_user_field(user_id, 'stars_spent', new_spent)
        if new_spent >= 5000 and user['is_vip'] == 0:
            update_user_field(user_id, 'is_vip', 1)
            add_skin_to_user(user_id, 3)

def get_webapp_url():
    """Возвращает текущий URL веб-приложения из БД"""
    url = get_setting('webapp_url')
    if not url:
        url = "https://ваш-проект.amvera.io"  # значение по умолчанию
    return url

def set_webapp_url(url):
    """Обновляет URL веб-приложения (только для суперадминов)"""
    set_setting('webapp_url', url)
