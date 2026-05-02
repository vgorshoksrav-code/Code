// ═══════════════════════════════════════════════════════════════════════════
// ЭХАРИС: ДУЭЛЬ ДУШ — ПОЛНЫЙ КЛИЕНТСКИЙ СКРИПТ (РАБОЧАЯ ВЕРСИЯ)
// ═══════════════════════════════════════════════════════════════════════════

// ──────────────────────────────────────────────────────────────────────────
// Telegram WebApp инициализация
// ──────────────────────────────────────────────────────────────────────────
const tg = window.Telegram?.WebApp || { 
    initDataUnsafe: {}, 
    expand: () => {}, 
    ready: () => {}, 
    showAlert: (m) => alert(m),
    showConfirm: (m, cb) => cb(confirm(m)),
    close: () => {}
};
tg.expand();
tg.ready();
tg.enableClosingConfirmation();

const tgUser = tg.initDataUnsafe?.user;
let userId = tgUser?.id || null;
let username = tgUser?.username || tgUser?.first_name || `hero_${Math.floor(Math.random() * 9999)}`;

// ──────────────────────────────────────────────────────────────────────────
// Глобальное состояние
// ──────────────────────────────────────────────────────────────────────────
let currentMatchId = null;
let battleActive = false;
let battleInterval = null;
let searchInterval = null;
let currentEnergy = 10;
let maxEnergy = 30;
let currentMyHp = 100;
let currentOpponentHp = 100;
let pveBattleActive = false;
let currentBossState = null;
let currentGuildId = null;
let guildChatInterval = null;
let profileCache = null;
let allSkinsCache = null;
let shopRarityFilter = 'all';
let currentTab = 'duel';
let tutorialStep = 0;
let myHeroEmoji = '🧙';
let skipTutorial = localStorage.getItem('echaris_tutorial_done') === '1';

// Аватары классов
const CLASS_AVATARS = {
    warrior: '⚔️',
    mage: '🧙',
    archer: '🏹',
    rogue: '🗡️',
    paladin: '🛡️',
    necromancer: '💀',
    druid: '🌿'
};

// ──────────────────────────────────────────────────────────────────────────
// API вызовы
// ──────────────────────────────────────────────────────────────────────────
async function callAPI(endpoint, data = {}, method = 'POST') {
    try {
        let url = `/api/${endpoint}`;
        if (method === 'GET') {
            const params = new URLSearchParams({ user_id: userId, ...data });
            url = `${url}?${params}`;
            const res = await fetch(url);
            return await res.json();
        }
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, ...data })
        });
        return await res.json();
    } catch (err) {
        console.error(`API Error [${endpoint}]:`, err);
        return { success: false, error: err.message };
    }
}

// ──────────────────────────────────────────────────────────────────────────
// Локализация
// ──────────────────────────────────────────────────────────────────────────
const LOCALE = {
    ru: {
        find_battle: '⚔️ Найти бой',
        searching: '🔍 Поиск соперника...',
        cancel: 'Отмена',
        no_tickets: '🎟️ Нет билетов! Заберите ежедневный подарок 🎁',
        victory: '🏆 ПОБЕДА!',
        defeat: '💀 ПОРАЖЕНИЕ...',
        not_enough_energy: '⚡ Недостаточно энергии!',
        skill_0: 'Огненная стрела',
        skill_1: 'Ледяной щит',
        skill_2: 'Духовная связь',
        skill_3: 'Цепная молния',
        skill_4: 'Зов предков',
        campaign: '🏰 Кампания',
        guild: '🏛️ Гильдия',
        hero: '👤 Герой',
        leaderboard: '📊 Топ игроков',
        shop: '✨ Лавка',
        daily_gift: 'Ежедневный подарок',
        claim: 'Забрать',
        upgrade: 'Прокачать',
        equip: 'Надеть',
        buy: 'Купить',
        shards: '💎 Осколки',
        tickets: '🎟️ Билеты',
        rank: '🏆 Рейтинг',
        wins: '✅ Побед',
        losses: '❌ Поражений'
    },
    en: {
        find_battle: '⚔️ Find Battle',
        searching: '🔍 Searching...',
        cancel: 'Cancel',
        no_tickets: '🎟️ No tickets! Claim daily gift 🎁',
        victory: '🏆 VICTORY!',
        defeat: '💀 DEFEAT...',
        not_enough_energy: '⚡ Not enough energy!',
        skill_0: 'Fire Arrow',
        skill_1: 'Ice Shield',
        skill_2: 'Spirit Bond',
        skill_3: 'Chain Lightning',
        skill_4: 'Ancestor Call',
        campaign: '🏰 Campaign',
        guild: '🏛️ Guild',
        hero: '👤 Hero',
        leaderboard: '📊 Leaderboard',
        shop: '✨ Shop',
        daily_gift: 'Daily Gift',
        claim: 'Claim',
        upgrade: 'Upgrade',
        equip: 'Equip',
        buy: 'Buy',
        shards: '💎 Shards',
        tickets: '🎟️ Tickets',
        rank: '🏆 Rank',
        wins: '✅ Wins',
        losses: '❌ Losses'
    }
};

let lang = 'ru';
function t(key) { return LOCALE[lang][key] || LOCALE.ru[key] || key; }

// ──────────────────────────────────────────────────────────────────────────
// UI Обновления
// ──────────────────────────────────────────────────────────────────────────
function updateUI(profile) {
    if (!profile) return;
    profileCache = profile;
    
    document.getElementById('topbarName').textContent = profile.username || username;
    document.getElementById('topbarRank').innerHTML = `⚔️ ${profile.rank || 1000}`;
    document.getElementById('topbarShards').textContent = profile.shards || 0;
    document.getElementById('topbarTickets').textContent = profile.daily_tickets || 0;
    
    // Показываем кнопку подарка если доступен
    if (profile.gift_available) {
        document.getElementById('giftBtn').classList.add('gift-available');
    } else {
        document.getElementById('giftBtn').classList.remove('gift-available');
    }
}

function setActiveTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    
    // Загружаем данные для выбранной вкладки
    if (tabId === 'hero') loadHeroTab();
    else if (tabId === 'leaderboard') loadLeaderboard();
    else if (tabId === 'shop') loadShop();
    else if (tabId === 'campaign') loadCampaign();
    else if (tabId === 'guild') loadGuild();
}

function addBattleLog(msg, type = 'info') {
    const logDiv = document.getElementById('battleLog');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = msg;
    logDiv.appendChild(entry);
    logDiv.scrollTop = logDiv.scrollHeight;
    setTimeout(() => entry.remove(), 8000);
}

function clearBattleLog() {
    document.getElementById('battleLog').innerHTML = '';
}

function resetDuelUI() {
    document.getElementById('findDuelBtn').style.display = 'flex';
    document.getElementById('searchingSpinner').style.display = 'none';
    if (searchInterval) { clearInterval(searchInterval); searchInterval = null; }
}

// ──────────────────────────────────────────────────────────────────────────
// PVP ДУЭЛИ
// ──────────────────────────────────────────────────────────────────────────
async function findDuel() {
    const profile = await loadProfile();
    if (!profile || profile.daily_tickets <= 0) {
        tg.showAlert(t('no_tickets'));
        return;
    }
    
    document.getElementById('findDuelBtn').style.display = 'none';
    document.getElementById('searchingSpinner').style.display = 'flex';
    clearBattleLog();
    addBattleLog('🔍 Поиск соперника...', 'info');
    
    const result = await callAPI('find_duel', {});
    
    if (result.status === 'no_tickets') {
        tg.showAlert(t('no_tickets'));
        resetDuelUI();
        return;
    }
    
    if (result.match_id) {
        startBattle(result.match_id, result.opponent);
        return;
    }
    
    // Опрос очереди
    let attempts = 0;
    searchInterval = setInterval(async () => {
        attempts++;
        const check = await callAPI('queue_status', {}, 'GET');
        if (check.status === 'found' && check.match_id) {
            clearInterval(searchInterval);
            startBattle(check.match_id, check.opponent);
        } else if (attempts >= 15) {
            clearInterval(searchInterval);
            addBattleLog('⏰ Долгий поиск, попробуйте ещё раз', 'error');
            resetDuelUI();
        }
    }, 2000);
}

function startBattle(matchId, opponent) {
    currentMatchId = matchId;
    battleActive = true;
    currentMyHp = 100;
    currentOpponentHp = 100;
    currentEnergy = 10;
    
    document.getElementById('myAvatar').textContent = myHeroEmoji;
    document.getElementById('opponentAvatar').textContent = opponent.skin_emoji || '👤';
    document.getElementById('myName').textContent = username;
    document.getElementById('opponentName').textContent = opponent.username;
    
    updateBattleUI(100, 100, 10);
    addBattleLog(`⚔️ Бой начался! Противник: ${opponent.username} (${opponent.rank})`, 'battle');
    
    if (battleInterval) clearInterval(battleInterval);
    battleInterval = setInterval(pollBattle, 1500);
}

async function pollBattle() {
    if (!battleActive || !currentMatchId) return;
    const state = await callAPI('duel_action', { match_id: currentMatchId, skill_index: null });
    if (!state) return;
    
    if (state.battle_end) {
        finishBattle(state.winner_id);
    } else {
        updateBattleUI(state.player_hp, state.opponent_hp, state.player_energy);
    }
}

async function useSkill(skillIndex) {
    if (!battleActive || !currentMatchId) return;
    
    const result = await callAPI('duel_action', { match_id: currentMatchId, skill_index: skillIndex });
    if (!result) return;
    
    if (result.error) {
        addBattleLog(`❌ ${result.error}`, 'error');
        return;
    }
    
    if (result.battle_end) {
        finishBattle(result.winner_id);
    } else {
        updateBattleUI(result.player_hp, result.opponent_hp, result.player_energy);
        if (result.log) addBattleLog(result.log, result.log.includes('нанесли') ? 'damage' : 'heal');
    }
}

function updateBattleUI(myHp, oppHp, energy) {
    currentMyHp = Math.max(0, myHp);
    currentOpponentHp = Math.max(0, oppHp);
    currentEnergy = energy;
    
    document.getElementById('myHp').textContent = currentMyHp;
    document.getElementById('opponentHp').textContent = currentOpponentHp;
    document.getElementById('myHpFill').style.width = `${currentMyHp}%`;
    document.getElementById('opponentHpFill').style.width = `${currentOpponentHp}%`;
    document.getElementById('energy').textContent = currentEnergy;
    document.getElementById('energyBar').style.width = `${(currentEnergy / maxEnergy) * 100}%`;
}

function finishBattle(winnerId) {
    clearInterval(battleInterval);
    battleActive = false;
    
    const won = String(winnerId) === String(userId);
    addBattleLog(won ? t('victory') : t('defeat'), won ? 'victory' : 'defeat');
    tg.showAlert(won ? t('victory') + ' +15💎' : t('defeat') + ' +5💎');
    
    setTimeout(() => {
        resetDuelUI();
        loadProfile();
    }, 2000);
}

// ──────────────────────────────────────────────────────────────────────────
// PVE КАМПАНИЯ
// ──────────────────────────────────────────────────────────────────────────
async function loadCampaign() {
    const data = await callAPI('campaign_progress', {}, 'GET');
    if (!data) return;
    
    const container = document.getElementById('chaptersContainer');
    container.innerHTML = '';
    
    for (const chapter of data.chapters) {
        const chapterDiv = document.createElement('div');
        chapterDiv.className = `chapter-card ${chapter.completed ? 'completed' : ''} ${!chapter.unlocked ? 'locked' : ''}`;
        
        let bossesHtml = '';
        for (const boss of chapter.bosses) {
            bossesHtml += `
                <div class="boss-item ${boss.defeated ? 'defeated' : ''} ${boss.available ? 'available' : ''}">
                    <div class="boss-icon">${boss.defeated ? '✅' : boss.available ? '👹' : '🔒'}</div>
                    <div class="boss-info">
                        <div class="boss-name">${boss.name}</div>
                        <div class="boss-stats">❤️ ${boss.hp} ⚔️ ${boss.damage}</div>
                        ${boss.mechanics.length ? `<div class="boss-mech">⚙️ ${boss.mechanics.join(', ')}</div>` : ''}
                        <div class="boss-reward">💎 ${boss.rewards.shards}${boss.rewards.stars ? ` ⭐${boss.rewards.stars}` : ''}</div>
                    </div>
                    ${boss.available && !boss.defeated ? `<button class="boss-fight-btn" data-id="${boss.boss_id}">⚔️ Бой</button>` : ''}
                </div>
            `;
        }
        
        chapterDiv.innerHTML = `
            <div class="chapter-header">
                <span>${chapter.completed ? '✅' : chapter.unlocked ? '🔓' : '🔒'}</span>
                <span class="chapter-name">Глава ${chapter.chapter}: ${chapter.name}</span>
            </div>
            <div class="boss-list">${bossesHtml}</div>
        `;
        container.appendChild(chapterDiv);
    }
    
    document.querySelectorAll('.boss-fight-btn').forEach(btn => {
        btn.addEventListener('click', () => startPvEBattle(parseInt(btn.dataset.id)));
    });
}

async function startPvEBattle(bossId) {
    const result = await callAPI('pve_start_battle', { boss_id: bossId });
    if (!result.success) {
        tg.showAlert(result.error || 'Ошибка начала боя');
        return;
    }
    
    pveBattleActive = true;
    currentBossState = result.state;
    
    const modal = document.getElementById('bossBattleModal');
    modal.style.display = 'flex';
    document.getElementById('bossName').textContent = currentBossState.boss_name;
    document.getElementById('bossAvatarBig').textContent = '👹';
    document.getElementById('claimPveRewards').style.display = 'none';
    document.getElementById('pveBattleLog').innerHTML = '';
    updatePvEUI();
}

function updatePvEUI() {
    if (!currentBossState) return;
    
    document.getElementById('bossHp').textContent = currentBossState.boss_hp;
    document.getElementById('bossMaxHp').textContent = currentBossState.boss_max_hp;
    document.getElementById('bossHpFill').style.width = `${(currentBossState.boss_hp / currentBossState.boss_max_hp) * 100}%`;
    document.getElementById('pveMyHp').textContent = currentBossState.player_hp;
    document.getElementById('pveMyHpFill').style.width = `${(currentBossState.player_hp / currentBossState.player_max_hp) * 100}%`;
    document.getElementById('pveEnergy').textContent = currentBossState.player_energy;
    
    if (currentBossState.log) {
        const logDiv = document.getElementById('pveBattleLog');
        const entry = document.createElement('div');
        entry.textContent = currentBossState.log;
        logDiv.appendChild(entry);
        logDiv.scrollTop = logDiv.scrollHeight;
    }
    
    if (currentBossState.finished) {
        pveBattleActive = false;
        if (currentBossState.winner === 'player') {
            document.getElementById('claimPveRewards').style.display = 'block';
        } else {
            setTimeout(() => {
                tg.showAlert('💀 Поражение! Попробуйте ещё раз');
                document.getElementById('bossBattleModal').style.display = 'none';
                loadCampaign();
            }, 1500);
        }
    }
}

async function usePvESkill(skillIndex) {
    if (!pveBattleActive) return;
    const result = await callAPI('pve_action', { skill_index: skillIndex });
    if (result.error) {
        tg.showAlert(result.error);
        return;
    }
    currentBossState = result;
    updatePvEUI();
}

async function claimPvERewards() {
    const result = await callAPI('pve_claim_rewards', {});
    if (result.success) {
        let msg = `🎉 Награда: 💎 +${result.shards_earned}`;
        if (result.stars_earned) msg += `, ⭐ +${result.stars_earned}`;
        if (result.skin_earned) msg += `, 🎁 Новый скин!`;
        tg.showAlert(msg);
    }
    document.getElementById('bossBattleModal').style.display = 'none';
    loadCampaign();
    loadProfile();
}

// ──────────────────────────────────────────────────────────────────────────
// ГЕРОЙ И СКИЛЛЫ
// ──────────────────────────────────────────────────────────────────────────
async function loadHeroTab() {
    const profile = await loadProfile();
    if (!profile) return;
    
    myHeroEmoji = CLASS_AVATARS[profile.hero_class] || '🧙';
    document.getElementById('heroAvatarDisplay').textContent = myHeroEmoji;
    document.getElementById('heroRank').textContent = profile.rank;
    document.getElementById('heroWins').textContent = profile.wins;
    document.getElementById('heroLosses').textContent = profile.losses;
    document.getElementById('shardsCount').textContent = profile.shards;
    
    const skillNames = [t('skill_0'), t('skill_1'), t('skill_2'), t('skill_3'), t('skill_4')];
    const container = document.getElementById('skillsLevels');
    container.innerHTML = '';
    
    profile.hero_levels.forEach((level, idx) => {
        const cost = 50 * level;
        const row = document.createElement('div');
        row.className = 'skill-row-compact';
        row.innerHTML = `
            <div class="skill-info">
                <span class="skill-emoji">${['🔥','❄️','🌿','⚡','🌟'][idx]}</span>
                <span class="skill-name-hero">${skillNames[idx]} Ур.${level}</span>
            </div>
            <button class="upgrade-skill-btn" data-idx="${idx}" ${profile.shards < cost ? 'disabled' : ''}>
                ⬆️ ${cost}💎
            </button>
        `;
        container.appendChild(row);
    });
    
    document.querySelectorAll('.upgrade-skill-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const res = await callAPI('upgrade_skill', { skill_index: parseInt(btn.dataset.idx) });
            if (res.success) loadHeroTab();
            else tg.showAlert(res.error || 'Ошибка');
        });
    });
    
    // Скины
    const skinsContainer = document.getElementById('skinsList');
    skinsContainer.innerHTML = '';
    for (const skin of profile.owned_skins || []) {
        const card = document.createElement('div');
        card.className = `skin-item ${skin.equipped ? 'equipped' : ''}`;
        card.innerHTML = `
            <div class="skin-emoji-hero">${skin.emoji || '🧙'}</div>
            <div class="skin-name-hero">${skin.name}</div>
            <div class="skin-rarity-hero ${skin.rarity}">${skin.rarity}</div>
            ${!skin.equipped ? `<button class="equip-skin-btn" data-id="${skin.id}">${t('equip')}</button>` : '<span class="equipped-badge">✅ Надет</span>'}
        `;
        skinsContainer.appendChild(card);
    }
    
    document.querySelectorAll('.equip-skin-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            await callAPI('equip_skin', { skin_id: parseInt(btn.dataset.id) });
            loadHeroTab();
        });
    });
}

// ──────────────────────────────────────────────────────────────────────────
// ЛИДЕРБОРД
// ──────────────────────────────────────────────────────────────────────────
async function loadLeaderboard() {
    const data = await callAPI('leaderboard', {}, 'GET');
    const container = document.getElementById('leaderboardList');
    container.innerHTML = '';
    
    (data || []).forEach((player, idx) => {
        const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `${idx + 1}.`;
        const row = document.createElement('div');
        row.className = `leaderboard-row ${String(player.user_id) === String(userId) ? 'is-me' : ''}`;
        row.innerHTML = `
            <div class="lb-rank">${medal}</div>
            <div class="lb-avatar">${player.skin_emoji || '🧙'}</div>
            <div class="lb-info">
                <div class="lb-name">${player.username}${player.is_vip ? '👑' : ''}</div>
                <div class="lb-skin">${player.skin_name}</div>
            </div>
            <div class="lb-stats">
                <div class="lb-rating">🏆 ${player.rank}</div>
                <div class="lb-wins">⚔️ ${player.wins} побед</div>
            </div>
        `;
        container.appendChild(row);
    });
}

// ──────────────────────────────────────────────────────────────────────────
// МАГАЗИН
// ──────────────────────────────────────────────────────────────────────────
async function loadShop() {
    if (!allSkinsCache) allSkinsCache = await callAPI('skins_list', {}, 'GET');
    const profile = await loadProfile();
    const owned = new Set((profile?.owned_skins || []).map(s => s.id));
    
    const container = document.getElementById('shopItems');
    container.innerHTML = '';
    
    for (const skin of allSkinsCache) {
        if (shopRarityFilter !== 'all' && skin.rarity !== shopRarityFilter) continue;
        const ownedFlag = owned.has(skin.id);
        const card = document.createElement('div');
        card.className = `shop-item ${ownedFlag ? 'owned' : ''}`;
        card.innerHTML = `
            <div class="shop-skin-emoji">${skin.emoji || '🧙'}</div>
            <div class="shop-skin-name">${skin.name}</div>
            <div class="shop-skin-rarity ${skin.rarity}">${skin.rarity}</div>
            <div class="shop-skin-price">${skin.price_stars > 0 ? `⭐ ${skin.price_stars}` : '🆓 Бесплатно'}</div>
            ${!ownedFlag ? `<button class="buy-skin-btn" data-id="${skin.id}" data-price="${skin.price_stars}" data-name="${skin.name}">${t('buy')}</button>` : '<span class="owned-tag">✅ В коллекции</span>'}
        `;
        container.appendChild(card);
    }
    
    document.querySelectorAll('.buy-skin-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const skinId = parseInt(btn.dataset.id);
            const price = parseInt(btn.dataset.price);
            const name = btn.dataset.name;
            
            if (price === 0) {
                const res = await callAPI('buy_skin', { skin_id: skinId, confirm: true });
                if (res.success) {
                    tg.showAlert(`✅ Скин "${name}" получен!`);
                    allSkinsCache = null;
                    loadShop();
                    loadHeroTab();
                }
            } else {
                tg.showAlert(`⭐ Скин "${name}" стоит ${price} Telegram Stars.\nОплата через Telegram Stars будет доступна в следующем обновлении.`);
            }
        });
    });
}

// ──────────────────────────────────────────────────────────────────────────
// ГИЛЬДИЯ
// ──────────────────────────────────────────────────────────────────────────
async function loadGuild() {
    const data = await callAPI('my_guild', {}, 'GET');
    if (!data.has_guild) {
        document.getElementById('noGuildSection').style.display = 'block';
        document.getElementById('guildSection').style.display = 'none';
        loadGuildLeaderboard();
        return;
    }
    
    document.getElementById('noGuildSection').style.display = 'none';
    document.getElementById('guildSection').style.display = 'block';
    
    const guild = data.guild;
    currentGuildId = guild.guild_id;
    
    document.getElementById('guildEmoji').textContent = guild.emoji;
    document.getElementById('guildName').textContent = guild.name;
    document.getElementById('guildLevel').textContent = `Уровень ${guild.level}`;
    document.getElementById('guildDescription').textContent = guild.description;
    document.getElementById('guildWarPoints').textContent = guild.war_points;
    document.getElementById('guildExp').textContent = guild.experience;
    document.getElementById('guildExpMax').textContent = guild.exp_for_next;
    document.getElementById('guildMemberCount').textContent = guild.members?.length || 0;
    
    // Участники
    const membersContainer = document.getElementById('guildMembersList');
    membersContainer.innerHTML = '';
    for (const m of guild.members || []) {
        const roleIcon = m.role === 'leader' ? '👑' : m.role === 'officer' ? '⭐' : '👤';
        membersContainer.innerHTML += `
            <div class="guild-member-row">
                <span>${roleIcon} ${m.username}</span>
                <span class="member-rank">🏆 ${m.rank}</span>
                <span class="member-contribution">💎 ${m.contribution}</span>
            </div>
        `;
    }
    
    // Рейд
    if (guild.active_raid) {
        document.getElementById('activeRaid').style.display = 'block';
        document.getElementById('startRaidBtn').style.display = 'none';
        document.getElementById('raidBossName').textContent = guild.active_raid.boss_name;
        document.getElementById('raidBossCurrentHp').textContent = guild.active_raid.boss_current_hp;
        document.getElementById('raidBossMaxHp').textContent = guild.active_raid.boss_max_hp;
        const pct = (guild.active_raid.boss_current_hp / guild.active_raid.boss_max_hp) * 100;
        document.getElementById('raidBossHpFill').style.width = `${pct}%`;
    } else {
        document.getElementById('activeRaid').style.display = 'none';
        document.getElementById('startRaidBtn').style.display = guild.user_role === 'leader' ? 'block' : 'none';
    }
    
    loadGuildLeaderboard();
}

async function loadGuildLeaderboard() {
    const guilds = await callAPI('guild_leaderboard', {}, 'GET');
    const container = document.getElementById('guildLeaderboardList');
    container.innerHTML = '';
    (guilds || []).slice(0, 10).forEach((g, i) => {
        container.innerHTML += `<div class="guild-lb-row">${i+1}. ${g.emoji} ${g.name} | Ур.${g.level} | ⭐${g.war_points}</div>`;
    });
}

// ──────────────────────────────────────────────────────────────────────────
// ЕЖЕДНЕВНЫЙ ПОДАРОК
// ──────────────────────────────────────────────────────────────────────────
async function claimDailyGift() {
    const profile = await loadProfile();
    if (!profile || !profile.gift_available) {
        tg.showAlert('🎁 Подарок уже получен сегодня! Приходите завтра.');
        return;
    }
    
    const modal = document.getElementById('giftModal');
    const rewardsList = document.getElementById('giftRewardsList');
    rewardsList.innerHTML = '<div class="gift-loading">🎁 Открываем...</div>';
    modal.style.display = 'flex';
    
    const result = await callAPI('daily_gift', {});
    if (result.success) {
        rewardsList.innerHTML = result.rewards.map(r => `<div class="gift-reward">✨ ${r}</div>`).join('');
        if (result.skin_reward) {
            rewardsList.innerHTML += `<div class="gift-reward special">🎁 РЕДКИЙ СКИН: ${result.skin_reward}!</div>`;
        }
        loadProfile();
    } else {
        rewardsList.innerHTML = `<div class="gift-error">❌ ${result.error || 'Ошибка'}</div>`;
    }
}

// ──────────────────────────────────────────────────────────────────────────
// ИНИЦИАЛИЗАЦИЯ
// ──────────────────────────────────────────────────────────────────────────
async function init() {
    console.log('🚀 Echaris инициализация...');
    
    // Регистрация пользователя
    await callAPI('register', { username });
    
    // Загрузка профиля
    const profile = await loadProfile();
    if (profile) {
        lang = profile.language || 'ru';
        myHeroEmoji = CLASS_AVATARS[profile.hero_class] || '🧙';
        document.getElementById('topbarAvatar').textContent = myHeroEmoji;
        document.getElementById('myAvatar').textContent = myHeroEmoji;
        document.getElementById('heroAvatarDisplay').textContent = myHeroEmoji;
    }
    
    // Навешиваем обработчики
    document.getElementById('findDuelBtn')?.addEventListener('click', findDuel);
    document.getElementById('cancelSearchBtn')?.addEventListener('click', resetDuelUI);
    document.getElementById('giftBtn')?.addEventListener('click', claimDailyGift);
    document.getElementById('claimGiftBtn')?.addEventListener('click', () => {
        document.getElementById('giftModal').style.display = 'none';
    });
    document.getElementById('claimPveRewards')?.addEventListener('click', claimPvERewards);
    document.getElementById('closeBossBattle')?.addEventListener('click', () => {
        document.getElementById('bossBattleModal').style.display = 'none';
        pveBattleActive = false;
    });
    
    document.querySelectorAll('.skill-card:not(.pve-skill)').forEach(btn => {
        btn.addEventListener('click', () => {
            if (battleActive) useSkill(parseInt(btn.dataset.skill));
        });
    });
    
    document.querySelectorAll('.pve-skill').forEach(btn => {
        btn.addEventListener('click', () => {
            if (pveBattleActive) usePvESkill(parseInt(btn.dataset.skill));
        });
    });
    
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
    });
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            shopRarityFilter = btn.dataset.rarity;
            loadShop();
        });
    });
    
    document.getElementById('createGuildBtn')?.addEventListener('click', () => {
        document.getElementById('createGuildModal').style.display = 'flex';
    });
    document.getElementById('closeCreateGuild')?.addEventListener('click', () => {
        document.getElementById('createGuildModal').style.display = 'none';
    });
    document.getElementById('confirmCreateGuild')?.addEventListener('click', async () => {
        const name = document.getElementById('newGuildName').value.trim();
        const emoji = document.getElementById('newGuildEmoji').value.trim() || '🏰';
        const desc = document.getElementById('newGuildDescription').value.trim();
        if (!name) { tg.showAlert('Введите название'); return; }
        const res = await callAPI('create_guild', { name, emoji, description: desc });
        if (res.success) {
            document.getElementById('createGuildModal').style.display = 'none';
            loadGuild();
        } else tg.showAlert(res.error || 'Ошибка');
    });
    document.getElementById('searchGuildsBtn')?.addEventListener('click', async () => {
        const query = document.getElementById('guildSearchInput').value;
        const guilds = await callAPI('search_guilds', { query }, 'GET');
        const container = document.getElementById('guildSearchResults');
        container.innerHTML = '';
        for (const g of guilds || []) {
            container.innerHTML += `
                <div class="guild-search-item">
                    <span>${g.emoji} ${g.name} | Ур.${g.level} | 👥${g.member_count}</span>
                    <button class="join-guild-btn" data-id="${g.guild_id}">Вступить</button>
                </div>
            `;
        }
        document.querySelectorAll('.join-guild-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const res = await callAPI('join_guild', { guild_id: btn.dataset.id });
                if (res.success) { tg.showAlert('✅ Вы вступили в гильдию!'); loadGuild(); }
                else tg.showAlert(res.error);
            });
        });
    });
    document.getElementById('leaveGuildBtn')?.addEventListener('click', async () => {
        if (confirm('Покинуть гильдию?')) {
            const res = await callAPI('leave_guild', {});
            if (res.success) loadGuild();
            else tg.showAlert(res.error);
        }
    });
    document.getElementById('sendGuildMessage')?.addEventListener('click', async () => {
        const msg = document.getElementById('guildMessageInput').value.trim();
        if (!msg || !currentGuildId) return;
        await callAPI('guild_send_message', { guild_id: currentGuildId, username, message: msg });
        document.getElementById('guildMessageInput').value = '';
        setTimeout(() => loadGuild(), 500);
    });
    document.getElementById('startRaidBtn')?.addEventListener('click', async () => {
        const res = await callAPI('start_guild_raid', { guild_id: currentGuildId, boss_level: 1 });
        if (res.success) loadGuild();
        else tg.showAlert(res.error);
    });
    document.getElementById('attackRaidBoss')?.addEventListener('click', async () => {
        const res = await callAPI('attack_raid_boss', { raid_id: currentGuildId, damage: 1000 });
        if (res.success) loadGuild();
        else tg.showAlert(res.error);
    });
    document.getElementById('changeAvatarBtn')?.addEventListener('click', () => {
        document.getElementById('avatarPickerModal').style.display = 'flex';
    });
    document.getElementById('closeAvatarPicker')?.addEventListener('click', () => {
        document.getElementById('avatarPickerModal').style.display = 'none';
    });
    document.querySelectorAll('.avatar-option').forEach(opt => {
        opt.addEventListener('click', async () => {
            const heroClass = opt.dataset.avatar;
            await callAPI('set_class', { hero_class: heroClass });
            myHeroEmoji = CLASS_AVATARS[heroClass] || '🧙';
            document.getElementById('heroAvatarDisplay').textContent = myHeroEmoji;
            document.getElementById('topbarAvatar').textContent = myHeroEmoji;
            document.getElementById('myAvatar').textContent = myHeroEmoji;
            document.getElementById('avatarPickerModal').style.display = 'none';
            loadHeroTab();
        });
    });
    document.getElementById('langBtn')?.addEventListener('click', () => {
        lang = lang === 'ru' ? 'en' : 'ru';
        document.getElementById('langBtn').textContent = lang === 'ru' ? '🇷🇺' : '🇬🇧';
        callAPI('set_language', { language: lang });
        loadHeroTab();
        loadShop();
        loadLeaderboard();
    });
    
    // Скрываем сплеш и показываем главный контент
    setTimeout(() => {
        const splash = document.getElementById('splashScreen');
        if (splash) {
            splash.style.opacity = '0';
            setTimeout(() => {
                splash.style.display = 'none';
                document.getElementById('mainContent').style.display = 'block';
                
                if (!skipTutorial) {
                    setTimeout(() => startTutorial(), 500);
                }
            }, 400);
        }
    }, 1500);
}

function startTutorial() {
    const steps = [
        { icon: '🌌', title: 'Добро пожаловать в Эхарис!', text: 'Сражайся с игроками и боссами, собирай скины, улучшай навыки и стань легендой!' },
        { icon: '⚔️', title: 'Система боя', text: 'Используй скиллы во время дуэли. Каждый скилл тратит энергию ⚡. Энергия восстанавливается автоматически.' },
        { icon: '💎', title: 'Осколки и скины', text: 'Побеждая, получай осколки 💎 для улучшения скиллов. Скины покупаются за Telegram Stars ⭐.' },
        { icon: '🎁', title: 'Ежедневный подарок', text: 'Каждые 24 часа нажимай 🎁 и получай бонусы. Иногда выпадают редкие скины!' }
    ];
    
    let step = 0;
    const overlay = document.getElementById('tutorialOverlay');
    const titleEl = document.getElementById('tutorialTitle');
    const textEl = document.getElementById('tutorialText');
    const iconEl = document.querySelector('.tutorial-icon');
    const nextBtn = document.getElementById('tutorialNextBtn');
    const dots = document.getElementById('tutorialDots');
    
    function renderStep() {
        titleEl.textContent = steps[step].title;
        textEl.textContent = steps[step].text;
        iconEl.textContent = steps[step].icon;
        dots.innerHTML = steps.map((_, i) => `<div class="dot ${i === step ? 'active' : ''}"></div>`).join('');
        nextBtn.textContent = step === steps.length - 1 ? '▶ Играть!' : 'Далее →';
    }
    
    renderStep();
    overlay.style.display = 'flex';
    
    nextBtn.onclick = () => {
        step++;
        if (step < steps.length) {
            renderStep();
        } else {
            overlay.style.display = 'none';
            localStorage.setItem('echaris_tutorial_done', '1');
        }
    };
}

async function loadProfile() {
    try {
        const profile = await callAPI('profile', {}, 'GET');
        if (profile && !profile.error) {
            profileCache = profile;
            updateUI(profile);
            return profile;
        }
        return null;
    } catch (e) {
        console.error('Profile load error:', e);
        return null;
    }
}

// Запуск
init();
