import json
import random
from database import get_user, update_user_field, get_db_connection
from enum import Enum

class BossMechanic(Enum):
    NONE = "none"
    INVISIBILITY = "invisibility"  # шанс промаха 40%
    FREEZE = "freeze"              # пропуск хода с шансом 30%
    BURNING = "burning"            # урон 5% HP 3 хода
    VAMPIRISM = "vampirism"        # восстанавливает 30% нанесённого урона
    PARALYSIS = "paralysis"        # стан на 1 ход с шансом 25%
    INSANITY = "insanity"          # атакует случайную цель (включая себя)
    SLOW = "slow"                  # у игрока -1 энергия в ход
    REFLECTION = "reflection"      # отражает 25% урона
    ALL = "all"                    # комбинация всех механик

class Boss:
    def __init__(self, boss_id, name, chapter, hp, damage, defense, mechanics, skill_levels, rewards):
        self.boss_id = boss_id
        self.name = name
        self.chapter = chapter
        self.max_hp = hp
        self.current_hp = hp
        self.damage = damage
        self.defense = defense
        self.mechanics = mechanics  # список BossMechanic
        self.skill_levels = skill_levels  # [5]
        self.rewards = rewards  # {shards: int, skin_id: int or None, stars: int}
        self.energy = 10
        self.shield = 0
        self.burn_turns = 0
        self.frozen = False

    def take_damage(self, raw_damage):
        actual_damage = max(1, raw_damage - self.defense)
        self.current_hp -= actual_damage
        return actual_damage

    def heal(self, amount):
        self.current_hp = min(self.max_hp, self.current_hp + amount)

    def is_alive(self):
        return self.current_hp > 0

# ------------------------------------------------------------
# База данных боссов
# ------------------------------------------------------------
CAMPAIGN_BOSSES = {
    1: [
        Boss(1, "Страж портала", 1, 80, 15, 2, [BossMechanic.NONE], [2,2,2,2,2], {"shards": 20, "skin_id": None, "stars": 0}),
        Boss(2, "Теневой маг", 1, 90, 18, 3, [BossMechanic.NONE], [2,2,2,2,2], {"shards": 25, "skin_id": None, "stars": 0}),
        Boss(3, "Хранитель врат", 1, 100, 20, 4, [BossMechanic.INVISIBILITY], [3,3,3,3,3], {"shards": 30, "skin_id": None, "stars": 5}),
    ],
    2: [
        Boss(4, "Призрачный воин", 2, 120, 25, 5, [BossMechanic.INVISIBILITY], [3,3,3,3,3], {"shards": 35, "skin_id": None, "stars": 5}),
        Boss(5, "Лорд теней", 2, 140, 28, 6, [BossMechanic.INVISIBILITY], [3,3,3,3,3], {"shards": 40, "skin_id": None, "stars": 10}),
        Boss(6, "Мастер иллюзий", 2, 160, 30, 7, [BossMechanic.INVISIBILITY], [4,4,4,4,4], {"shards": 45, "skin_id": 1, "stars": 10}),
    ],
    3: [
        Boss(7, "Ледяной голем", 3, 180, 32, 8, [BossMechanic.FREEZE], [4,4,4,4,4], {"shards": 50, "skin_id": None, "stars": 15}),
        Boss(8, "Снежная ведьма", 3, 200, 35, 9, [BossMechanic.FREEZE], [4,4,4,4,4], {"shards": 55, "skin_id": None, "stars": 15}),
        Boss(9, "Хранитель льда", 3, 220, 38, 10, [BossMechanic.FREEZE], [5,5,5,5,5], {"shards": 60, "skin_id": None, "stars": 20}),
    ],
    4: [
        Boss(10, "Огненный элементаль", 4, 240, 40, 11, [BossMechanic.BURNING], [5,5,5,5,5], {"shards": 65, "skin_id": None, "stars": 20}),
        Boss(11, "Пламенный рыцарь", 4, 260, 42, 12, [BossMechanic.BURNING], [5,5,5,5,5], {"shards": 70, "skin_id": None, "stars": 25}),
        Boss(12, "Огненный гигант", 4, 280, 45, 13, [BossMechanic.BURNING], [6,6,6,6,6], {"shards": 75, "skin_id": 5, "stars": 25}),
    ],
    5: [
        Boss(13, "Поглотитель душ", 5, 300, 48, 14, [BossMechanic.VAMPIRISM], [6,6,6,6,6], {"shards": 80, "skin_id": None, "stars": 30}),
        Boss(14, "Духовный охотник", 5, 320, 50, 15, [BossMechanic.VAMPIRISM], [6,6,6,6,6], {"shards": 85, "skin_id": None, "stars": 30}),
        Boss(15, "Собиратель душ", 5, 340, 52, 16, [BossMechanic.VAMPIRISM], [7,7,7,7,7], {"shards": 90, "skin_id": None, "stars": 35}),
    ],
    6: [
        Boss(16, "Грозовой дух", 6, 360, 55, 17, [BossMechanic.PARALYSIS], [7,7,7,7,7], {"shards": 95, "skin_id": None, "stars": 35}),
        Boss(17, "Молнийный змей", 6, 380, 58, 18, [BossMechanic.PARALYSIS], [7,7,7,7,7], {"shards": 100, "skin_id": None, "stars": 40}),
        Boss(18, "Повелитель молний", 6, 400, 60, 19, [BossMechanic.PARALYSIS], [8,8,8,8,8], {"shards": 110, "skin_id": None, "stars": 40}),
    ],
    7: [
        Boss(19, "Порождение бездны", 7, 420, 62, 20, [BossMechanic.INSANITY], [8,8,8,8,8], {"shards": 120, "skin_id": None, "stars": 45}),
        Boss(20, "Безумный культист", 7, 440, 65, 21, [BossMechanic.INSANITY], [8,8,8,8,8], {"shards": 130, "skin_id": None, "stars": 45}),
        Boss(21, "Древний ужас", 7, 460, 68, 22, [BossMechanic.INSANITY], [9,9,9,9,9], {"shards": 140, "skin_id": None, "stars": 50}),
    ],
    8: [
        Boss(22, "Временной страж", 8, 480, 70, 23, [BossMechanic.SLOW], [9,9,9,9,9], {"shards": 150, "skin_id": None, "stars": 55}),
        Boss(23, "Песочный маг", 8, 500, 72, 24, [BossMechanic.SLOW], [9,9,9,9,9], {"shards": 160, "skin_id": None, "stars": 60}),
        Boss(24, "Хрономант", 8, 520, 75, 25, [BossMechanic.SLOW], [10,10,10,10,10], {"shards": 180, "skin_id": None, "stars": 65}),
    ],
    9: [
        Boss(25, "Зеркальный рыцарь", 9, 540, 78, 26, [BossMechanic.REFLECTION], [10,10,10,10,10], {"shards": 200, "skin_id": None, "stars": 70}),
        Boss(26, "Призрачная леди", 9, 560, 80, 27, [BossMechanic.REFLECTION], [10,10,10,10,10], {"shards": 220, "skin_id": None, "stars": 75}),
        Boss(27, "Хранительница сада", 9, 580, 82, 28, [BossMechanic.REFLECTION], [11,11,11,11,11], {"shards": 250, "skin_id": None, "stars": 80}),
    ],
    10: [
        Boss(28, "Королевский страж", 10, 600, 85, 29, [BossMechanic.ALL], [11,11,11,11,11], {"shards": 300, "skin_id": None, "stars": 100}),
        Boss(29, "Архимаг короны", 10, 650, 90, 30, [BossMechanic.ALL], [12,12,12,12,12], {"shards": 400, "skin_id": None, "stars": 150}),
        Boss(30, "Король эхарисов", 10, 700, 100, 35, [BossMechanic.ALL], [15,15,15,15,15], {"shards": 500, "skin_id": 2, "stars": 200}),
    ],
}

# Глобальное хранилище активных PvE боёв
active_pve_battles = {}  # user_id -> PvEBattle

class PvEBattle:
    def __init__(self, user_id, boss):
        self.user_id = user_id
        self.boss = boss
        self.player_hp = 100
        self.player_max_hp = 100
        self.player_energy = 10
        self.player_max_energy = 30
        self.player_shield = 0
        self.player_burn_turns = 0
        self.player_frozen = False
        self.turn_count = 0
        self.log = []
        self.finished = False
        self.winner = None

    def player_attack(self, skill_index, skill_damage_base, player_stats, hero_levels):
        """Игрок использует скилл против босса"""
        if self.finished:
            return {"error": "Бой завершён"}

        # Проверка заморозки
        if self.player_frozen:
            self.player_frozen = False
            self.log.append("Вы заморожены и пропускаете ход!")
            self.boss_turn()
            return self.get_state()

        # Проверка энергии
        from game_logic import SKILL_COST, SKILL_HEAL, SKILL_SHIELD
        cost = SKILL_COST[skill_index]
        if self.player_energy < cost:
            return {"error": "Недостаточно энергии"}

        self.player_energy -= cost
        damage = 0
        heal = 0
        shield = 0

        # Расчёт урона
        attack_bonus = player_stats.get('attack_pct', 0) / 100.0
        level_bonus = hero_levels[skill_index] / 10.0  # +10% за уровень скилла
        base_damage = skill_damage_base * (1 + attack_bonus + level_bonus)
        
        # Крит шанс (базовый 10% + 1% за уровень)
        crit_chance = 10 + hero_levels[skill_index]
        is_crit = random.random() < (crit_chance / 100)
        if is_crit:
            base_damage *= 1.5

        damage = max(1, int(base_damage))
        
        # Механика отражения
        if BossMechanic.REFLECTION in self.boss.mechanics:
            reflected = int(damage * 0.25)
            damage -= reflected
            self.player_hp -= reflected
            self.log.append(f"Босс отражает {reflected} урона!")

        # Нанесение урона
        actual_damage = self.boss.take_damage(damage)
        self.log.append(f"Вы наносите {actual_damage} урона")

        # Лечение
        heal = SKILL_HEAL[skill_index] * (1 + hero_levels[skill_index] / 10)
        if heal > 0:
            self.player_hp = min(self.player_max_hp, self.player_hp + int(heal))
            self.log.append(f"Вы восстанавливаете {int(heal)} HP")

        # Щит
        shield = SKILL_SHIELD[skill_index] * (1 + hero_levels[skill_index] / 10)
        if shield > 0:
            self.player_shield = int(shield)
            self.log.append(f"Вы ставите щит на {int(shield)} ед.")

        # Проверка убийства босса
        if not self.boss.is_alive():
            self.finished = True
            self.winner = "player"
            self.log.append(f"🏆 Босс {self.boss.name} повержен!")
            return self.get_state()

        # Ход босса
        self.boss_turn()
        
        # Проверка смерти игрока
        if self.player_hp <= 0:
            self.finished = True
            self.winner = "boss"
            self.log.append("💀 Вы проиграли...")

        return self.get_state()

    def boss_turn(self):
        """AI босса"""
        if self.boss.frozen:
            self.boss.frozen = False
            self.log.append(f"{self.boss.name} заморожен и пропускает ход!")
            return

        # Механика безумия
        if BossMechanic.INSANITY in self.boss.mechanics and random.random() < 0.25:
            # Босс атакует себя
            damage = int(self.boss.damage * 0.8)
            self.boss.current_hp -= damage
            self.log.append(f"{self.boss.name} в безумии ранит себя на {damage} урона!")
            return

        # Босс выбирает скилл
        available_skills = [i for i in range(5) if self.boss.energy >= self._get_skill_cost(i)]
        if not available_skills:
            # Простая атака
            raw_damage = self.boss.damage
        else:
            skill = random.choice(available_skills)
            self.boss.energy -= self._get_skill_cost(skill)
            from game_logic import SKILL_BASE_DAMAGE
            raw_damage = SKILL_BASE_DAMAGE[skill] * (1 + self.boss.skill_levels[skill] / 10)

        # Применение щита игрока
        if self.player_shield > 0:
            absorbed = min(raw_damage, self.player_shield)
            raw_damage -= absorbed
            self.player_shield -= absorbed
            if absorbed > 0:
                self.log.append(f"Ваш щит поглощает {absorbed} урона")

        # Вампиризм
        if BossMechanic.VAMPIRISM in self.boss.mechanics:
            heal_amount = int(raw_damage * 0.3)
            self.boss.heal(heal_amount)
            self.log.append(f"{self.boss.name} высасывает {heal_amount} HP")

        # Нанесение урона игроку
        self.player_hp -= raw_damage
        self.log.append(f"{self.boss.name} наносит {raw_damage} урона")

        # Дополнительные механики
        if BossMechanic.FREEZE in self.boss.mechanics and random.random() < 0.3:
            self.player_frozen = True
            self.log.append("❄️ Вы заморожены!")

        if BossMechanic.PARALYSIS in self.boss.mechanics and random.random() < 0.25:
            self.player_frozen = True
            self.log.append("⚡ Вы парализованы!")

        if BossMechanic.BURNING in self.boss.mechanics:
            burn_damage = int(self.player_max_hp * 0.05)
            self.player_hp -= burn_damage
            self.log.append(f"🔥 Горение наносит {burn_damage} урона")

        if BossMechanic.SLOW in self.boss.mechanics:
            self.player_energy = max(0, self.player_energy - 1)
            self.log.append("⏳ Время замедляется, -1 энергия")

    def _get_skill_cost(self, skill_index):
        from game_logic import SKILL_COST
        return SKILL_COST[skill_index]

    def get_state(self):
        return {
            "player_hp": max(0, self.player_hp),
            "player_max_hp": self.player_max_hp,
            "player_energy": self.player_energy,
            "boss_hp": max(0, self.boss.current_hp),
            "boss_max_hp": self.boss.max_hp,
            "boss_name": self.boss.name,
            "boss_chapter": self.boss.chapter,
            "boss_mechanics": [m.value for m in self.boss.mechanics],
            "log": "\n".join(self.log[-5:]),
            "finished": self.finished,
            "winner": self.winner,
            "rewards": self.boss.rewards if self.winner == "player" else None
        }


def get_campaign_progress(user_id):
    """Возвращает прогресс кампании игрока"""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pve_progress (
            user_id INTEGER PRIMARY KEY,
            completed_chapters TEXT DEFAULT '[]',
            completed_bosses TEXT DEFAULT '[]',
            current_chapter INTEGER DEFAULT 1,
            current_boss_id INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    
    progress = conn.execute("SELECT * FROM pve_progress WHERE user_id = ?", (user_id,)).fetchone()
    if not progress:
        conn.execute("INSERT INTO pve_progress (user_id) VALUES (?)", (user_id,))
        conn.commit()
        progress = conn.execute("SELECT * FROM pve_progress WHERE user_id = ?", (user_id,)).fetchone()
    
    conn.close()
    return {
        "completed_chapters": json.loads(progress['completed_chapters']),
        "completed_bosses": json.loads(progress['completed_bosses']),
        "current_chapter": progress['current_chapter'],
        "current_boss_id": progress['current_boss_id']
    }

def update_campaign_progress(user_id, boss_id, chapter):
    """Обновляет прогресс после победы над боссом"""
    progress = get_campaign_progress(user_id)
    completed_bosses = progress['completed_bosses']
    
    if boss_id not in completed_bosses:
        completed_bosses.append(boss_id)
    
    # Проверяем, все ли боссы главы побеждены
    chapter_bosses = CAMPAIGN_BOSSES[chapter]
    all_defeated = all(b.boss_id in completed_bosses for b in chapter_bosses)
    
    completed_chapters = progress['completed_chapters']
    if all_defeated and chapter not in completed_chapters:
        completed_chapters.append(chapter)
    
    # Определяем следующего босса
    next_chapter = chapter
    next_boss_id = boss_id + 1
    
    if all_defeated:
        if chapter < 10:
            next_chapter = chapter + 1
            next_boss_id = CAMPAIGN_BOSSES[next_chapter][0].boss_id
        else:
            next_boss_id = -1  # Всё пройдено
    
    conn = get_db_connection()
    conn.execute("""
        UPDATE pve_progress 
        SET completed_chapters = ?, completed_bosses = ?, current_chapter = ?, current_boss_id = ?
        WHERE user_id = ?
    """, (json.dumps(completed_chapters), json.dumps(completed_bosses), next_chapter, next_boss_id, user_id))
    conn.commit()
    conn.close()
    
    return {
        "completed_chapters": completed_chapters,
        "completed_bosses": completed_bosses,
        "current_chapter": next_chapter,
        "current_boss_id": next_boss_id
    }

def claim_boss_rewards(user_id, rewards):
    """Выдаёт награды за победу над боссом"""
    user = get_user(user_id)
    if not user:
        return {"success": False, "error": "User not found"}
    
    # Осколки
    new_shards = user['shards'] + rewards['shards']
    update_user_field(user_id, 'shards', new_shards)
    
    # Звёзды
    if rewards['stars'] > 0:
        new_stars = user['stars_spent'] + rewards['stars']
        update_user_field(user_id, 'stars_spent', new_stars)
    
    # Скин (если есть)
    if rewards['skin_id']:
        from database import add_skin_to_user
        add_skin_to_user(user_id, rewards['skin_id'])
    
    return {
        "success": True,
        "shards_earned": rewards['shards'],
        "stars_earned": rewards['stars'],
        "skin_earned": rewards['skin_id']
      }
