import json
import random
import time
import uuid
from database import get_user, update_user_field, get_db_connection

# ----------------------------------------------------------------------
# Базовые параметры скилов
# Индексы: 0 - Огненная стрела, 1 - Ледяной щит, 2 - Духовная связь,
#          3 - Цепная молния, 4 - Зов предков
SKILL_BASE_DAMAGE = [20, 0, 0, 35, 50]      # прямой урон (0 - значит не атакующий скилл)
SKILL_COST = [5, 4, 6, 8, 12]               # стоимость в энергии
SKILL_HEAL = [0, 0, 10, 0, 0]               # лечение (только для индекса 2)
SKILL_SHIELD = [0, 20, 0, 0, 0]             # щит (поглощение урона) – упрощённо
# ----------------------------------------------------------------------

class PvPMatch:
    """
    Управляет одной PvP-битвой (игрок vs игрок или игрок vs AI-бот).
    """

    def __init__(self, match_id, player1_id, player2_id, player1_data, player2_data):
        """
        match_id: уникальный идентификатор матча
        player1_id: Telegram ID первого игрока (или -1 для бота)
        player2_id: Telegram ID второго игрока (или -1)
        player1_data: dict из БД (или искусственный для бота) с полями:
                      username, rank, hero_levels (str JSON), equipped_skin_id
        player2_data: аналогично
        """
        self.match_id = match_id
        self.player1_id = player1_id
        self.player2_id = player2_id

        # Здоровье и энергия
        self.player1_hp = 100
        self.player2_hp = 100
        self.player1_energy = 10
        self.player2_energy = 10
        self.player1_max_energy = 30
        self.player2_max_energy = 30

        # Уровни скилов (списки из 5 целых чисел)
        self.player1_skills = json.loads(player1_data['hero_levels']) if player1_data and player1_data['hero_levels'] else [1,1,1,1,1]
        self.player2_skills = json.loads(player2_data['hero_levels']) if player2_data and player2_data['hero_levels'] else [3,3,3,3,3]

        # Расчёт бонусов от экипированного скина
        self.player1_stats = self._calc_stats(player1_data)
        self.player2_stats = self._calc_stats(player2_data)

        # Лог событий боя (список строк)
        self.log = []

        # Флаги для отслеживания щита (упрощённо – активный щит на одного игрока)
        self.player1_shield = 0
        self.player2_shield = 0

    def _calc_stats(self, user_data):
        """Вычисляет бонусы атаки/защиты/энергии от экипированного скина."""
        if not user_data:
            return {'attack_pct': 0, 'defense_pct': 0, 'energy_pct': 0}
        skin_id = user_data.get('equipped_skin_id')
        if not skin_id:
            return {'attack_pct': 0, 'defense_pct': 0, 'energy_pct': 0}
        conn = get_db_connection()
        skin = conn.execute("SELECT stat_bonus FROM skins WHERE id = ?", (skin_id,)).fetchone()
        conn.close()
        bonus = json.loads(skin['stat_bonus']) if skin and skin['stat_bonus'] else {}
        return {
            'attack_pct': bonus.get('attack_pct', 0),
            'defense_pct': bonus.get('defense_pct', 0),
            'energy_pct': bonus.get('energy_pct', 0)
        }

    def _get_effective_cap(self, energy_bonus_pct):
        """Увеличивает максимум энергии на основе бонуса."""
        bonus = energy_bonus_pct / 100.0
        return int(min(30 + 30 * bonus, 50))   # максимум 50 энергии

    def calculate_damage(self, skill_index, attacker_stats, defender_stats, is_crit=False):
        """
        Рассчитывает урон для атакующего скилла.
        base_damage умножается на (1 + атака_бонус) и делится на (1 + защита_бонус).
        Крит увеличивает урон в 1.5 раза.
        """
        base_damage = SKILL_BASE_DAMAGE[skill_index]
        if base_damage == 0:
            return 0
        attack_bonus = attacker_stats.get('attack_pct', 0) / 100.0
        defense_bonus = defender_stats.get('defense_pct', 0) / 100.0
        damage = base_damage * (1 + attack_bonus) / (1 + defense_bonus)
        if is_crit:
            damage *= 1.5
        return int(max(1, damage))

    def apply_skill(self, user_id, skill_index):
        """
        Применяет скилл от пользователя (user_id) к противнику.
        Возвращает словарь с обновлёнными HP, энергией и сообщением лога.
        """
        # Определяем, кто атакует
        if user_id == self.player1_id:
            energy = self.player1_energy
            cost = SKILL_COST[skill_index]
            if energy < cost:
                return {"error": "Недостаточно энергии"}
            self.player1_energy -= cost
            # Урон/лечение/щит
            damage = self.calculate_damage(skill_index, self.player1_stats, self.player2_stats,
                                           random.random() < 0.1)   # 10% крит
            heal = SKILL_HEAL[skill_index]
            shield = SKILL_SHIELD[skill_index]

            log_msg = ""
            if damage > 0:
                # Учитываем щит противника
                if self.player2_shield > 0:
                    absorbed = min(damage, self.player2_shield)
                    damage -= absorbed
                    self.player2_shield -= absorbed
                    log_msg += f" (щит поглотил {absorbed})"
                self.player2_hp -= damage
                log_msg = f"Вы нанесли {damage} урона" + log_msg
            if heal > 0:
                self.player1_hp = min(100, self.player1_hp + heal)
                log_msg = f"Вы восстановили {heal} HP"
            if shield > 0:
                self.player1_shield = shield
                log_msg = f"Вы поставили щит на {shield} ед."

            # Ограничение HP
            self.player1_hp = max(0, min(100, self.player1_hp))
            self.player2_hp = max(0, min(100, self.player2_hp))

            # Автоматическое восстановление энергии (по 1 в секунду вызывается отдельно)
            return {
                "player_hp": self.player1_hp,
                "opponent_hp": self.player2_hp,
                "player_energy": self.player1_energy,
                "log": log_msg
            }

        else:  # атакует второй игрок или бот
            energy = self.player2_energy
            cost = SKILL_COST[skill_index]
            if energy < cost:
                return {"error": "Недостаточно энергии"}
            self.player2_energy -= cost
            damage = self.calculate_damage(skill_index, self.player2_stats, self.player1_stats,
                                           random.random() < 0.1)
            heal = SKILL_HEAL[skill_index]
            shield = SKILL_SHIELD[skill_index]

            log_msg = ""
            if damage > 0:
                if self.player1_shield > 0:
                    absorbed = min(damage, self.player1_shield)
                    damage -= absorbed
                    self.player1_shield -= absorbed
                    log_msg += f" (щит поглотил {absorbed})"
                self.player1_hp -= damage
                log_msg = f"Противник нанёс {damage} урона" + log_msg
            if heal > 0:
                self.player2_hp = min(100, self.player2_hp + heal)
                log_msg = f"Противник восстановил {heal} HP"
            if shield > 0:
                self.player2_shield = shield
                log_msg = f"Противник поставил щит на {shield} ед."

            self.player1_hp = max(0, min(100, self.player1_hp))
            self.player2_hp = max(0, min(100, self.player2_hp))

            return {
                "player_hp": self.player1_hp,
                "opponent_hp": self.player2_hp,
                "player_energy": self.player2_energy,
                "log": log_msg
            }

    def bot_turn(self):
        """
        Логика AI-бота (если player2_id == -1). Бот выбирает случайный скилл
        из доступных по энергии с вероятностью 0.6.
        """
        if self.player2_id != -1:
            return None
        # Собираем индексы скилов, которые бот может использовать
        available = [i for i in range(5) if SKILL_COST[i] <= self.player2_energy]
        if available and random.random() < 0.6:
            skill = random.choice(available)
            return self.apply_skill(self.player2_id, skill)
        return None

    def regenerate_energy(self):
        """Вызывается раз в секунду для пополнения энергии."""
        # Для первого игрока
        if self.player1_energy < self.player1_max_energy:
            self.player1_energy = min(self.player1_max_energy, self.player1_energy + 1)
        # Для второго
        if self.player2_energy < self.player2_max_energy:
            self.player2_energy = min(self.player2_max_energy, self.player2_energy + 1)

    def is_finished(self):
        """Возвращает True, если бой закончен."""
        return self.player1_hp <= 0 or self.player2_hp <= 0

    def get_winner(self):
        """Возвращает user_id победителя или None, если бой не окончен."""
        if self.player1_hp <= 0:
            return self.player2_id
        if self.player2_hp <= 0:
            return self.player1_id
        return None


# ----------------------------------------------------------------------
# Глобальные структуры для матчмейкинга
active_matches = {}      # match_id -> PvPMatch
pending_queue = {}       # user_id -> timestamp (время добавления в очередь)
# ----------------------------------------------------------------------

def find_match(user_id, user_data):
    """
    Основная функция поиска соперника.
    Если есть другой игрок в очереди с разницей рейтинга <= 200 – создаёт матч.
    Иначе ставит текущего в очередь.
    Возвращает: {"status": "waiting"} или {"match_id": ..., "opponent": {...}}
    """
    global pending_queue

    # Очищаем старые записи (старше 30 секунд)
    now = int(time.time())
    to_delete = [uid for uid, ts in pending_queue.items() if now - ts > 30]
    for uid in to_delete:
        del pending_queue[uid]

    # Ищем подходящего соперника
    for other_id, ts in list(pending_queue.items()):
        if other_id == user_id:
            continue
        other_data = get_user(other_id)
        if not other_data:
            del pending_queue[other_id]
            continue
        if abs(user_data['rank'] - other_data['rank']) <= 200:
            # Нашли соперника – удаляем его из очереди
            del pending_queue[other_id]
            # Создаём матч
            match_id = str(uuid.uuid4())
            match = PvPMatch(match_id, user_id, other_id, user_data, other_data)
            active_matches[match_id] = match

            opponent_info = {
                "username": other_data['username'],
                "rank": other_data['rank'],
                "hero_levels": json.loads(other_data['hero_levels']),
                "skin_name": get_skin_name(other_data['equipped_skin_id'])
            }
            return {"match_id": match_id, "opponent": opponent_info}

    # Соперник не найден – ставим в очередь
    pending_queue[user_id] = now
    return {"status": "waiting"}


def get_skin_name(skin_id):
    conn = get_db_connection()
    skin = conn.execute("SELECT name FROM skins WHERE id = ?", (skin_id,)).fetchone()
    conn.close()
    return skin['name'] if skin else "Базовый"


def check_match_ready(user_id):
    """
    Проверяет, не появился ли готовый матч для пользователя (активный матч),
    или если пользователь стоит в очереди больше 5 секунд – создаёт бой с AI.
    """
    global pending_queue
    # Сначала ищем активный матч, где участвует пользователь
    for mid, match in active_matches.items():
        if match.player1_id == user_id or match.player2_id == user_id:
            # Определяем данные оппонента
            opponent_id = match.player2_id if match.player1_id == user_id else match.player1_id
            if opponent_id == -1:
                opponent_info = {
                    "username": "❄️ Дух пустоты",
                    "rank": 0,
                    "hero_levels": [3,3,3,3,3],
                    "skin_name": "Страж пустоты"
                }
            else:
                opp_data = get_user(opponent_id)
                opponent_info = {
                    "username": opp_data['username'] if opp_data else "Unknown",
                    "rank": opp_data['rank'] if opp_data else 1000,
                    "hero_levels": json.loads(opp_data['hero_levels']) if opp_data else [1,1,1,1,1],
                    "skin_name": get_skin_name(opp_data['equipped_skin_id']) if opp_data else "Базовый"
                }
            return {"match_id": mid, "opponent": opponent_info}

    # Проверяем очередь
    if user_id in pending_queue:
        elapsed = int(time.time()) - pending_queue[user_id]
        if elapsed >= 5:
            # Удаляем из очереди и создаём бой с AI-ботом
            del pending_queue[user_id]
            user_data = get_user(user_id)
            if not user_data:
                return None
            # Искусственные данные для бота
            bot_data = {
                'username': '❄️ Дух пустоты',
                'rank': user_data['rank'] - 50,
                'hero_levels': json.dumps([3,3,3,3,3]),
                'equipped_skin_id': 4
            }
            match_id = str(uuid.uuid4())
            match = PvPMatch(match_id, user_id, -1, user_data, bot_data)
            active_matches[match_id] = match
            opponent_info = {
                "username": "❄️ Дух пустоты",
                "rank": user_data['rank'] - 50,
                "hero_levels": [3,3,3,3,3],
                "skin_name": "Страж пустоты"
            }
            return {"match_id": match_id, "opponent": opponent_info}
    return None


def update_elo(winner_id, loser_id):
    """Обновляет рейтинг по ELO и начисляет осколки."""
    winner = get_user(winner_id)
    loser = get_user(loser_id)
    if not winner or not loser:
        return
    K = 32
    E_winner = 1 / (1 + 10 ** ((loser['rank'] - winner['rank']) / 400))
    E_loser = 1 / (1 + 10 ** ((winner['rank'] - loser['rank']) / 400))
    new_winner_rank = int(winner['rank'] + K * (1 - E_winner))
    new_loser_rank = int(loser['rank'] + K * (0 - E_loser))

    update_user_field(winner_id, 'rank', new_winner_rank)
    update_user_field(loser_id, 'rank', new_loser_rank)
    update_user_field(winner_id, 'wins', winner['wins'] + 1)
    update_user_field(loser_id, 'losses', loser['losses'] + 1)
    update_user_field(winner_id, 'shards', winner['shards'] + 10)
    update_user_field(loser_id, 'shards', loser['shards'] + 3)


def claim_chain_reward(referred_id, referrer_id):
    """
    Активирует цепную награду для referrer_id за то, что referred_id
    зарегистрировался по его ссылке и впервые запустил игру.
    Возвращает "success", "already_claimed" или "error".
    """
    conn = get_db_connection()
    # Проверяем, не выдана ли уже награда
    ref_record = conn.execute(
        "SELECT reward_claimed FROM referrals WHERE referrer_id = ? AND referred_id = ?",
        (referrer_id, referred_id)
    ).fetchone()
    if ref_record and ref_record['reward_claimed'] == 1:
        conn.close()
        return "already_claimed"

    referrer = get_user(referrer_id)
    if not referrer:
        conn.close()
        return "error"

    chain = referrer['chain_counter']
    # Начисляем бонус в зависимости от количества уже приведённых друзей
    if chain == 0:
        bonus_shards = 50
        bonus_stars = 5
        skin_id = None
        skill_up = False
        ticket_bonus = 0
    elif chain == 1:
        bonus_shards = 100
        bonus_stars = 10
        skin_id = 5   # Пламенный клинок
        skill_up = False
        ticket_bonus = 0
    elif chain == 2:
        bonus_shards = 200
        bonus_stars = 0
        skin_id = None
        skill_up = True   # увеличить случайный навык на 1
        ticket_bonus = 0
    else:
        bonus_shards = 20
        bonus_stars = 0
        skin_id = None
        skill_up = False
        ticket_bonus = 1   # +1 билет дуэли

    # Обновляем осколки и звёзды
    new_shards = referrer['shards'] + bonus_shards
    update_user_field(referrer_id, 'shards', new_shards)
    if bonus_stars > 0:
        new_stars_spent = referrer['stars_spent'] + bonus_stars
        update_user_field(referrer_id, 'stars_spent', new_stars_spent)
        # Проверка VIP
        if new_stars_spent >= 5000 and referrer['is_vip'] == 0:
            update_user_field(referrer_id, 'is_vip', 1)
            # Выдать VIP-скин (Повелитель вселенных, id=3)
            conn.execute("INSERT OR IGNORE INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (referrer_id, 3))
            conn.commit()

    if skin_id:
        conn.execute("INSERT OR IGNORE INTO user_skins (user_id, skin_id, equipped) VALUES (?, ?, 0)", (referrer_id, skin_id))
        conn.commit()

    if skill_up:
        levels = json.loads(referrer['hero_levels'])
        idx = random.randint(0, 4)
        levels[idx] = min(20, levels[idx] + 1)
        update_user_field(referrer_id, 'hero_levels', json.dumps(levels))

    if ticket_bonus > 0:
        new_tickets = referrer['daily_tickets'] + ticket_bonus
        update_user_field(referrer_id, 'daily_tickets', new_tickets)

    # Увеличиваем chain_counter
    update_user_field(referrer_id, 'chain_counter', chain + 1)

    # Помечаем награду как выданную
    if ref_record is None:
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id, reward_claimed) VALUES (?, ?, 1)",
            (referrer_id, referred_id)
        )
    else:
        conn.execute(
            "UPDATE referrals SET reward_claimed = 1 WHERE referrer_id = ? AND referred_id = ?",
            (referrer_id, referred_id)
        )
    conn.commit()
    conn.close()
    return "success"
