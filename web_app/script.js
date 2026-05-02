// ═══════════════════════════════════════════════════════════════════════════
// ЭХАРИС: ДУЭЛЬ ДУШ — ПОЛНЫЙ КЛИЕНТСКИЙ СКРИПТ
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
let profileCache = null;
let allSkinsCache = null;
let currentTab = 'duel';
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
// Загрузка профиля
// ──────────────────────────────────────────────────────────────────────────
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

function updateUI(profile) {
    if (!profile) return;
    
    const topbarName = document.getElementById('topbarName');
    const topbarRank = document.getElementById('topbarRank');
    const topbarShards = document.getElementById('topbarShards');
    const topbarTickets = document.getElementById('topbarTickets');
    const topbarAvatar = document.getElementById('topbarAvatar');
    const myAvatar = document.getElementById('myAvatar');
    const heroAvatarDisplay = document.getElementById('heroAvatarDisplay');
    
    if (topbarName) topbarName.textContent = profile.username || username;
    if (topbarRank) topbarRank.innerHTML = `⚔️ ${profile.rank || 1000}`;
    if (topbarShards) topbarShards.textContent = profile.shards || 0;
    if (topbarTickets) topbarTickets.textContent = profile.daily_tickets || 0;
    if (topbarAvatar) topbarAvatar.textContent = myHeroEmoji;
    if (myAvatar) myAvatar.textContent = myHeroEmoji;
    if (heroAvatarDisplay) heroAvatarDisplay.textContent = myHeroEmoji;
    
    const giftBtn = document.getElementById('giftBtn');
    if (giftBtn) {
        if (profile.gift_available) giftBtn.classList.add('gift-available');
        else giftBtn.classList.remove('gift-available');
    }
}

// ──────────────────────────────────────────────────────────────────────────
// Навигация по вкладкам
// ──────────────────────────────────────────────────────────────────────────
function setActiveTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    const activeTab = document.getElementById(tabId);
    if (activeTab) activeTab.classList.add('active');
    
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    if (tabId === 'hero') loadHeroTab();
    else if (tabId === 'leaderboard') loadLeaderboard();
    else if (tabId === 'shop') loadShop();
    else if (tabId === 'campaign') loadCampaign();
    else if (tabId === 'guild') loadGuild();
}

// ──────────────────────────────────────────────────────────────────────────
// PVP ДУЭЛИ
// ──────────────────────────────────────────────────────────────────────────
async function findDuel() {
    const profile = await loadProfile();
    if (!profile || profile.daily_tickets <= 0) {
        tg.showAlert('🎟️ Нет билетов! Заберите ежедневный подарок 🎁');
        return;
    }
    
    const findBtn = document.getElementById('findDuelBtn');
    const searching = document.getElementById('searchingSpinner');
    if (findBtn) findBtn.style.display = 'none';
    if (searching) searching.style.display = 'flex';
    
    clearBattleLog();
    addBattleLog('🔍 Поиск соперника...', 'info');
    
    const result = await callAPI('find_duel', {});
    
    if (result.status === 'no_tickets') {
        tg.showAlert('🎟️ Нет билетов!');
        resetDuelUI();
        return;
    }
    
    if (result.match_id) {
        startBattle(result.match_id, result.opponent);
        return;
    }
    
    let attempts = 0;
    searchInterval = setInterval(async () => {
        attempts++;
        const check = await callAPI('queue_status', {}, 'GET');
        if (check.status === 'found' && check.match_id) {
            clearInterval(searchInterval);
            startBattle(check.match_id, check.opponent);
        } else if (attempts >= 20) {
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
    
    const myAvatar = document.getElementById('myAvatar');
    const opponentAvatar = document.getElementById('opponentAvatar');
    const myName = document.getElementById('myName');
    const opponentName = document.getElementById('opponentName');
    
    if (myAvatar) myAvatar.textContent = myHeroEmoji;
    if (opponentAvatar) opponentAvatar.textContent = opponent.skin_emoji || '👤';
    if (myName) myName.textContent = username;
    if (opponentName) opponentName.textContent = opponent.username;
    
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
    
    const myHpSpan = document.getElementById('myHp');
    const opponentHpSpan = document.getElementById('opponentHp');
    const myHpFill = document.getElementById('myHpFill');
    const opponentHpFill = document.getElementById('opponentHpFill');
    const energySpan = document.getElementById('energy');
    const energyBar = document.getElementById('energyBar');
    
    if (myHpSpan) myHpSpan.textContent = currentMyHp;
    if (opponentHpSpan) opponentHpSpan.textContent = currentOpponentHp;
    if (myHpFill) myHpFill.style.width = `${currentMyHp}%`;
    if (opponentHpFill) opponentHpFill.style.width = `${currentOpponentHp}%`;
    if (energySpan) energySpan.textContent = currentEnergy;
    if (energyBar) energyBar.style.width = `${(currentEnergy / maxEnergy) * 100}%`;
}

function finishBattle(winnerId) {
    if (battleInterval) clearInterval(battleInterval);
    battleActive = false;
    
    const won = String(winnerId) === String(userId);
    addBattleLog(won ? '🏆 ПОБЕДА!' : '💀 ПОРАЖЕНИЕ...', won ? 'victory' : 'defeat');
    tg.showAlert(won ? '🏆 Победа! +15💎' : '💀 Поражение... +5💎');
    
    setTimeout(() => {
        resetDuelUI();
        loadProfile();
    }, 2000);
}

function resetDuelUI() {
    const findBtn = document.getElementById('findDuelBtn');
    const searching = document.getElementById('searchingSpinner');
    if (findBtn) findBtn.style.display = 'flex';
    if (searching) searching.style.display = 'none';
    if (searchInterval) { clearInterval(searchInterval); searchInterval = null; }
}

function addBattleLog(msg, type = 'info') {
    const logDiv = document.getElementById('battleLog');
    if (!logDiv) return;
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = msg;
    logDiv.appendChild(entry);
    logDiv.scrollTop = logDiv.scrollHeight;
    setTimeout(() => entry.remove(), 8000);
}

function clearBattleLog() {
    const logDiv = document.getElementById('battleLog');
    if (logDiv) logDiv.innerHTML = '';
}

// ──────────────────────────────────────────────────────────────────────────
// PVE КАМПАНИЯ
// ──────────────────────────────────────────────────────────────────────────
async function loadCampaign() {
    const data = await callAPI('campaign_progress', {}, 'GET');
    if (!data) return;
    
    const container = document.getElementById('chaptersContainer');
    if (!container) return;
    container.innerHTML = '';
    
    for (const chapter of data.chapters || []) {
        const chapterDiv = document.createElement('div');
        chapterDiv.className = `chapter-card ${chapter.completed ? 'completed' : ''} ${!chapter.unlocked ? 'locked' : ''}`;
        
        let bossesHtml = '';
        for (const boss of chapter.bosses || []) {
            bossesHtml += `
                <div class="boss-item ${boss.defeated ? 'defeated' : ''} ${boss.available ? 'available' : ''}">
                    <div class="boss-icon">${boss.defeated ? '✅' : boss.available ? '👹' : '🔒'}</div>
                    <div class="boss-info">
                        <div class="boss-name">${escapeHtml(boss.name)}</div>
                        <div class="boss-stats">❤️ ${boss.hp} ⚔️ ${boss.damage}</div>
                        ${boss.mechanics && boss.mechanics.length ? `<div class="boss-mech">⚙️ ${boss.mechanics.join(', ')}</div>` : ''}
                        <div class="boss-reward">💎 ${boss.rewards.shards}${boss.rewards.stars ? ` ⭐${boss.rewards.stars}` : ''}</div>
                    </div>
                    ${boss.available && !boss.defeated ? `<button class="boss-fight-btn" data-id="${boss.boss_id}">⚔️ Бой</button>` : ''}
                </div>
            `;
        }
        
        chapterDiv.innerHTML = `
            <div class="chapter-header">
                <span>${chapter.completed ? '✅' : chapter.unlocked ? '🔓' : '🔒'}</span>
                <span class="chapter-name">Глава ${chapter.chapter}: ${escapeHtml(chapter.name)}</span>
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
    if (modal) modal.style.display = 'flex';
    
    const bossName = document.getElementById('bossName');
    const bossAvatarBig = document.getElementById('bossAvatarBig');
    const claimRewards = document.getElementById('claimPveRewards');
    const pveLog = document.getElementById('pveBattleLog');
    
    if (bossName) bossName.textContent = currentBossState.boss_name;
    if (bossAvatarBig) bossAvatarBig.textContent = '👹';
    if (claimRewards) claimRewards.style.display = 'none';
    if (pveLog) pveLog.innerHTML = '';
    updatePvEUI();
}

function updatePvEUI() {
    if (!currentBossState) return;
    
    const bossHp = document.getElementById('bossHp');
    const bossMaxHp = document.getElementById('bossMaxHp');
    const bossHpFill = document.getElementById('bossHpFill');
    const pveMyHp = document.getElementById('pveMyHp');
    const pveMyHpFill = document.getElementById('pveMyHpFill');
    const pveEnergy = document.getElementById('pveEnergy');
    const pveLog = document.getElementById('pveBattleLog');
    
    if (bossHp) bossHp.textContent = currentBossState.boss_hp;
    if (bossMaxHp) bossMaxHp.textContent = currentBossState.boss_max_hp;
    if (bossHpFill) bossHpFill.style.width = `${(currentBossState.boss_hp / currentBossState.boss_max_hp) * 100}%`;
    if (pveMyHp) pveMyHp.textContent = currentBossState.player_hp;
    if (pveMyHpFill) pveMyHpFill.style.width = `${(currentBossState.player_hp / currentBossState.player_max_hp) * 100}%`;
    if (pveEnergy) pveEnergy.textContent = currentBossState.player_energy;
    
    if (currentBossState.log && pveLog) {
        const entry = document.createElement('div');
        entry.textContent = currentBossState.log;
        pveLog.appendChild(entry);
        pveLog.scrollTop = pveLog.scrollHeight;
    }
    
    if (currentBossState.finished) {
        pveBattleActive = false;
        const claimRewards = document.getElementById('claimPveRewards');
        if (currentBossState.winner === 'player') {
            if (claimRewards) claimRewards.style.display = 'block';
        } else {
            setTimeout(() => {
                tg.showAlert('💀 Поражение! Попробуйте ещё раз');
                const modal = document.getElementById('bossBattleModal');
                if (modal) modal.style.display = 'none';
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
    const modal = document.getElementById('bossBattleModal');
    if (modal) modal.style.display = 'none';
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
    
    const heroAvatarDisplay = document.getElementById('heroAvatarDisplay');
    const heroRank = document.getElementById('heroRank');
    const heroWins = document.getElementById('heroWins');
    const heroLosses = document.getElementById('heroLosses');
    const shardsCount = document.getElementById('shardsCount');
    
    if (heroAvatarDisplay) heroAvatarDisplay.textContent = myHeroEmoji;
    if (heroRank) heroRank.textContent = profile.rank;
    if (heroWins) heroWins.textContent = profile.wins;
    if (heroLosses) heroLosses.textContent = profile.losses;
    if (shardsCount) shardsCount.textContent = profile.shards;
    
    const skillNames = ['Огненная стрела', 'Ледяной щит', 'Духовная связь', 'Цепная молния', 'Зов предков'];
    const skillEmojis = ['🔥', '❄️', '🌿', '⚡', '🌟'];
    const container = document.getElementById('skillsLevels');
    if (container) {
        container.innerHTML = '';
        
        profile.hero_levels.forEach((level, idx) => {
            const cost = 50 * level;
            const row = document.createElement('div');
            row.className = 'skill-row-compact';
            row.innerHTML = `
                <div class="skill-info">
                    <span class="skill-emoji">${skillEmojis[idx]}</span>
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
    }
    
    const skinsContainer = document.getElementById('skinsList');
    if (skinsContainer) {
        skinsContainer.innerHTML = '';
        for (const skin of profile.owned_skins || []) {
            const card = document.createElement('div');
            card.className = `skin-item ${skin.equipped ? 'equipped' : ''}`;
            card.innerHTML = `
                <div class="skin-emoji-hero">${skin.emoji || '🧙'}</div>
                <div class="skin-name-hero">${escapeHtml(skin.name)}</div>
                <div class="skin-rarity-hero ${skin.rarity}">${skin.rarity}</div>
                ${!skin.equipped ? `<button class="equip-skin-btn" data-id="${skin.id}">Надеть</button>` : '<span class="equipped-badge">✅ Надет</span>'}
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
}

// ──────────────────────────────────────────────────────────────────────────
// ЛИДЕРБОРД
// ──────────────────────────────────────────────────────────────────────────
async function loadLeaderboard() {
    const data = await callAPI('leaderboard', {}, 'GET');
    const container = document.getElementById('leaderboardList');
    if (!container) return;
    container.innerHTML = '';
    
    (data || []).forEach((player, idx) => {
        const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `${idx + 1}.`;
        const row = document.createElement('div');
        row.className = `leaderboard-row ${String(player.user_id) === String(userId) ? 'is-me' : ''}`;
        row.innerHTML = `
            <div class="lb-rank">${medal}</div>
            <div class="lb-avatar">${player.skin_emoji || '🧙'}</div>
            <div class="lb-info">
                <div class="lb-name">${escapeHtml(player.username)}${player.is_vip ? '👑' : ''}</div>
                <div class="lb-skin">${escapeHtml(player.skin_name)}</div>
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
    if (!container) return;
    container.innerHTML = '';
    
    for (const skin of allSkinsCache || []) {
        const ownedFlag = owned.has(skin.id);
        const card = document.createElement('div');
        card.className = `shop-item ${ownedFlag ? 'owned' : ''}`;
        card.innerHTML = `
            <div class="shop-skin-emoji">${skin.emoji || '🧙'}</div>
            <div class="shop-skin-name">${escapeHtml(skin.name)}</div>
            <div class="shop-skin-rarity ${skin.rarity}">${skin.rarity}</div>
            <div class="shop-skin-price">${skin.price_stars > 0 ? `⭐ ${skin.price_stars}` : '🆓 Бесплатно'}</div>
            ${!ownedFlag ? `<button class="buy-skin-btn" data-id="${skin.id}" data-price="${skin.price_stars}" data-name="${escapeHtml(skin.name)}">Купить</button>` : '<span class="owned-tag">✅ В коллекции</span>'}
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
        const noGuild = document.getElementById('noGuildSection');
        const guildSection = document.getElementById('guildSection');
        if (noGuild) noGuild.style.display = 'block';
        if (guildSection) guildSection.style.display = 'none';
        loadGuildLeaderboard();
        return;
    }
    
    const noGuild = document.getElementById('noGuildSection');
    const guildSection = document.getElementById('guildSection');
    if (noGuild) noGuild.style.display = 'none';
    if (guildSection) guildSection.style.display = 'block';
    
    const guild = data.guild;
    currentGuildId = guild.guild_id;
    
    const guildEmoji = document.getElementById('guildEmoji');
    const guildName = document.getElementById('guildName');
    const guildLevel = document.getElementById('guildLevel');
    const guildDescription = document.getElementById('guildDescription');
    const guildWarPoints = document.getElementById('guildWarPoints');
    const guildExp = document.getElementById('guildExp');
    const guildExpMax = document.getElementById('guildExpMax');
    const guildMemberCount = document.getElementById('guildMemberCount');
    
    if (guildEmoji) guildEmoji.textContent = guild.emoji;
    if (guildName) guildName.textContent = guild.name;
    if (guildLevel) guildLevel.textContent = `Уровень ${guild.level}`;
    if (guildDescription) guildDescription.textContent = guild.description;
    if (guildWarPoints) guildWarPoints.textContent = guild.war_points;
    if (guildExp) guildExp.textContent = guild.experience;
    if (guildExpMax) guildExpMax.textContent = guild.exp_for_next;
    if (guildMemberCount) guildMemberCount.textContent = guild.members?.length || 0;
    
    const membersContainer = document.getElementById('guildMembersList');
    if (membersContainer) {
        membersContainer.innerHTML = '';
        for (const m of guild.members || []) {
            const roleIcon = m.role === 'leader' ? '👑' : m.role === 'officer' ? '⭐' : '👤';
            const row = document.createElement('div');
            row.className = 'guild-member-row';
            row.innerHTML = `
                <span>${roleIcon} ${escapeHtml(m.username)}</span>
                <span class="member-rank">🏆 ${m.rank}</span>
                <span class="member-contribution">💎 ${m.contribution}</span>
            `;
            membersContainer.appendChild(row);
        }
    }
    
    if (guild.active_raid) {
        const activeRaid = document.getElementById('activeRaid');
        const startRaidBtn = document.getElementById('startRaidBtn');
        const raidBossName = document.getElementById('raidBossName');
        const raidBossCurrentHp = document.getElementById('raidBossCurrentHp');
        const raidBossMaxHp = document.getElementById('raidBossMaxHp');
        const raidBossHpFill = document.getElementById('raidBossHpFill');
        
        if (activeRaid) activeRaid.style.display = 'block';
        if (startRaidBtn) startRaidBtn.style.display = 'none';
        if (raidBossName) raidBossName.textContent = guild.active_raid.boss_name;
        if (raidBossCurrentHp) raidBossCurrentHp.textContent = guild.active_raid.boss_current_hp;
        if (raidBossMaxHp) raidBossMaxHp.textContent = guild.active_raid.boss_max_hp;
        if (raidBossHpFill) {
            const pct = (guild.active_raid.boss_current_hp / guild.active_raid.boss_max_hp) * 100;
            raidBossHpFill.style.width = `${pct}%`;
        }
    } else {
        const activeRaid = document.getElementById('activeRaid');
        const startRaidBtn = document.getElementById('startRaidBtn');
        if (activeRaid) activeRaid.style.display = 'none';
        if (startRaidBtn) startRaidBtn.style.display = guild.user_role === 'leader' ? 'block' : 'none';
    }
    
    loadGuildLeaderboard();
}

async function loadGuildLeaderboard() {
    const guilds = await callAPI('guild_leaderboard', {}, 'GET');
    const container = document.getElementById('guildLeaderboardList');
    if (!container) return;
    container.innerHTML = '';
    (guilds || []).slice(0, 10).forEach((g, i) => {
        const row = document.createElement('div');
        row.className = 'guild-lb-row';
        row.innerHTML = `${i+1}. ${g.emoji} ${escapeHtml(g.name)} | Ур.${g.level} | ⭐${g.war_points}`;
        container.appendChild(row);
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
    if (modal) modal.style.display = 'flex';
    if (rewardsList) rewardsList.innerHTML = '<div class="gift-loading">🎁 Открываем...</div>';
    
    const result = await callAPI('daily_gift', {});
    if (result.success && rewardsList) {
        rewardsList.innerHTML = result.rewards.map(r => `<div class="gift-reward">✨ ${escapeHtml(r)}</div>`).join('');
        if (result.skin_reward) {
            rewardsList.innerHTML += `<div class="gift-reward special">🎁 РЕДКИЙ СКИН: ${escapeHtml(result.skin_reward)}!</div>`;
        }
        loadProfile();
    } else if (rewardsList) {
        rewardsList.innerHTML = `<div class="gift-error">❌ ${result.error || 'Ошибка'}</div>`;
    }
}

// ──────────────────────────────────────────────────────────────────────────
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ──────────────────────────────────────────────────────────────────────────
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ──────────────────────────────────────────────────────────────────────────
// ИНИЦИАЛИЗАЦИЯ
// ──────────────────────────────────────────────────────────────────────────
async function init() {
    console.log('🚀 Echaris инициализация...');
    
    await callAPI('register', { username });
    
    const profile = await loadProfile();
    if (profile) {
        myHeroEmoji = CLASS_AVATARS[profile.hero_class] || '🧙';
        const topbarAvatar = document.getElementById('topbarAvatar');
        const myAvatar = document.getElementById('myAvatar');
        const heroAvatarDisplay = document.getElementById('heroAvatarDisplay');
        if (topbarAvatar) topbarAvatar.textContent = myHeroEmoji;
        if (myAvatar) myAvatar.textContent = myHeroEmoji;
        if (heroAvatarDisplay) heroAvatarDisplay.textContent = myHeroEmoji;
    }
    
    // Обработчики кнопок
    const findDuelBtn = document.getElementById('findDuelBtn');
    const cancelSearchBtn = document.getElementById('cancelSearchBtn');
    const giftBtn = document.getElementById('giftBtn');
    const claimGiftBtn = document.getElementById('claimGiftBtn');
    const claimPveRewards = document.getElementById('claimPveRewards');
    const closeBossBattle = document.getElementById('closeBossBattle');
    const changeAvatarBtn = document.getElementById('changeAvatarBtn');
    const closeAvatarPicker = document.getElementById('closeAvatarPicker');
    const createGuildBtn = document.getElementById('createGuildBtn');
    const closeCreateGuild = document.getElementById('closeCreateGuild');
    const confirmCreateGuild = document.getElementById('confirmCreateGuild');
    const searchGuildsBtn = document.getElementById('searchGuildsBtn');
    const leaveGuildBtn = document.getElementById('leaveGuildBtn');
    const sendGuildMessage = document.getElementById('sendGuildMessage');
    const startRaidBtn = document.getElementById('startRaidBtn');
    const attackRaidBoss = document.getElementById('attackRaidBoss');
    const langBtn = document.getElementById('langBtn');
    
    if (findDuelBtn) findDuelBtn.addEventListener('click', findDuel);
    if (cancelSearchBtn) cancelSearchBtn.addEventListener('click', resetDuelUI);
    if (giftBtn) giftBtn.addEventListener('click', claimDailyGift);
    if (claimGiftBtn) claimGiftBtn.addEventListener('click', () => {
        const modal = document.getElementById('giftModal');
        if (modal) modal.style.display = 'none';
    });
    if (claimPveRewards) claimPveRewards.addEventListener('click', claimPvERewards);
    if (closeBossBattle) closeBossBattle.addEventListener('click', () => {
        const modal = document.getElementById('bossBattleModal');
        if (modal) modal.style.display = 'none';
        pveBattleActive = false;
    });
    if (changeAvatarBtn) changeAvatarBtn.addEventListener('click', () => {
        const modal = document.getElementById('avatarPickerModal');
        if (modal) modal.style.display = 'flex';
    });
    if (closeAvatarPicker) closeAvatarPicker.addEventListener('click', () => {
        const modal = document.getElementById('avatarPickerModal');
        if (modal) modal.style.display = 'none';
    });
    if (createGuildBtn) createGuildBtn.addEventListener('click', () => {
        const modal = document.getElementById('createGuildModal');
        if (modal) modal.style.display = 'flex';
    });
    if (closeCreateGuild) closeCreateGuild.addEventListener('click', () => {
        const modal = document.getElementById('createGuildModal');
        if (modal) modal.style.display = 'none';
    });
    if (confirmCreateGuild) {
        confirmCreateGuild.addEventListener('click', async () => {
            const nameInput = document.getElementById('newGuildName');
            const emojiInput = document.getElementById('newGuildEmoji');
            const descInput = document.getElementById('newGuildDescription');
            const name = nameInput ? nameInput.value.trim() : '';
            const emoji = (emojiInput ? emojiInput.value.trim() : '') || '🏰';
            const desc = descInput ? descInput.value.trim() : '';
            if (!name) { tg.showAlert('Введите название'); return; }
            const res = await callAPI('create_guild', { name, emoji, description: desc });
            if (res.success) {
                const modal = document.getElementById('createGuildModal');
                if (modal) modal.style.display = 'none';
                loadGuild();
            } else tg.showAlert(res.error || 'Ошибка');
        });
    }
    if (searchGuildsBtn) {
        searchGuildsBtn.addEventListener('click', async () => {
            const input = document.getElementById('guildSearchInput');
            const query = input ? input.value : '';
            const guilds = await callAPI('search_guilds', { query }, 'GET');
            const container = document.getElementById('guildSearchResults');
            if (container) {
                container.innerHTML = '';
                for (const g of guilds || []) {
                    const item = document.createElement('div');
                    item.className = 'guild-search-item';
                    item.innerHTML = `
                        <span>${g.emoji} ${escapeHtml(g.name)} | Ур.${g.level} | 👥${g.member_count}</span>
                        <button class="join-guild-btn" data-id="${g.guild_id}">Вступить</button>
                    `;
                    container.appendChild(item);
                }
                document.querySelectorAll('.join-guild-btn').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const res = await callAPI('join_guild', { guild_id: btn.dataset.id });
                        if (res.success) { tg.showAlert('✅ Вы вступили в гильдию!'); loadGuild(); }
                        else tg.showAlert(res.error);
                    });
                });
            }
        });
    }
    if (leaveGuildBtn) {
        leaveGuildBtn.addEventListener('click', async () => {
            if (confirm('Покинуть гильдию?')) {
                const res = await callAPI('leave_guild', {});
                if (res.success) loadGuild();
                else tg.showAlert(res.error);
            }
        });
    }
    if (sendGuildMessage) {
        sendGuildMessage.addEventListener('click', async () => {
            const input = document.getElementById('guildMessageInput');
            const msg = input ? input.value.trim() : '';
            if (!msg || !currentGuildId) return;
            await callAPI('guild_send_message', { guild_id: currentGuildId, username, message: msg });
            if (input) input.value = '';
            setTimeout(() => loadGuild(), 500);
        });
    }
    if (startRaidBtn) {
        startRaidBtn.addEventListener('click', async () => {
            const res = await callAPI('start_guild_raid', { guild_id: currentGuildId, boss_level: 1 });
            if (res.success) loadGuild();
            else tg.showAlert(res.error);
        });
    }
    if (attackRaidBoss) {
        attackRaidBoss.addEventListener('click', async () => {
            const res = await callAPI('attack_raid_boss', { raid_id: currentGuildId, damage: 1000 });
            if (res.success) loadGuild();
            else tg.showAlert(res.error);
        });
    }
    if (langBtn) {
        langBtn.addEventListener('click', () => {
            const newLang = localStorage.getItem('lang') === 'ru' ? 'en' : 'ru';
            localStorage.setItem('lang', newLang);
            langBtn.textContent = newLang === 'ru' ? '🇷🇺' : '🇬🇧';
            callAPI('set_language', { language: newLang });
        });
    }
    
    // Скиллы
    document.querySelectorAll('.skill-card:not(.pve-skill)').forEach(btn => {
        btn.addEventListener('click', () => {
            if (battleActive) useSkill(parseInt(btn.getAttribute('data-skill')));
        });
    });
    
    document.querySelectorAll('.pve-skill').forEach(btn => {
        btn.addEventListener('click', () => {
            if (pveBattleActive) usePvESkill(parseInt(btn.getAttribute('data-skill')));
        });
    });
    
    // Табы
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => setActiveTab(btn.getAttribute('data-tab')));
    });
    
    // Фильтры магазина
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadShop();
        });
    });
    
    // Аватары
    document.querySelectorAll('.avatar-option').forEach(opt => {
        opt.addEventListener('click', async () => {
            const heroClass = opt.getAttribute('data-avatar');
            await callAPI('set_class', { hero_class: heroClass });
            myHeroEmoji = CLASS_AVATARS[heroClass] || '🧙';
            const heroAvatarDisplay = document.getElementById('heroAvatarDisplay');
            const topbarAvatar = document.getElementById('topbarAvatar');
            const myAvatar = document.getElementById('myAvatar');
            if (heroAvatarDisplay) heroAvatarDisplay.textContent = myHeroEmoji;
            if (topbarAvatar) topbarAvatar.textContent = myHeroEmoji;
            if (myAvatar) myAvatar.textContent = myHeroEmoji;
            const modal = document.getElementById('avatarPickerModal');
            if (modal) modal.style.display = 'none';
            loadHeroTab();
        });
    });
    
    // Скрываем сплеш и показываем контент
    setTimeout(() => {
        const splash = document.getElementById('splashScreen');
        const mainContent = document.getElementById('mainContent');
        if (splash) {
            splash.style.opacity = '0';
            setTimeout(() => {
                splash.style.display = 'none';
                if (mainContent) mainContent.style.display = 'block';
            }, 400);
        } else if (mainContent) {
            mainContent.style.display = 'block';
        }
    }, 1500);
}

// Запуск
init();
