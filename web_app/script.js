// ---------- Инициализация Telegram ----------
let tg = window.Telegram.WebApp;
tg.expand();
tg.ready();
let user = tg.initDataUnsafe?.user;
let userId = user?.id;
let username = user?.username || `user_${userId}`;

// Глобальные переменные PvP
let currentMatchId = null;
let battleActive = false;
let battleInterval = null;
let currentEnergy = 10;
let currentMyHp = 100;
let currentOpponentHp = 100;

// Глобальные переменные PvE
let pveBattleActive = false;
let currentBossState = null;

// Глобальные переменные гильдии
let currentGuildId = null;
let guildChatInterval = null;

// ---------- Частицы ----------
const canvas = document.getElementById('particlesCanvas');
const ctx = canvas.getContext('2d');
let particles = [];
function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

class Particle {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2 + 1;
        this.speedX = (Math.random() - 0.5) * 0.5;
        this.speedY = (Math.random() - 0.5) * 0.5;
        this.color = `rgba(255, 215, 0, ${Math.random() * 0.3 + 0.1})`;
    }
    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        if (this.x < 0) this.x = canvas.width;
        if (this.x > canvas.width) this.x = 0;
        if (this.y < 0) this.y = canvas.height;
        if (this.y > canvas.height) this.y = 0;
    }
    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
    }
}
for (let i = 0; i < 100; i++) particles.push(new Particle());
function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let p of particles) { p.update(); p.draw(); }
    requestAnimationFrame(animateParticles);
}
animateParticles();

// ---------- Парсинг startapp ----------
const urlParams = new URLSearchParams(window.location.search);
const startApp = urlParams.get('startapp');
let initialTab = 'duel';
if (startApp === 'duel') initialTab = 'duel';
else if (startApp === 'campaign') initialTab = 'campaign';
else if (startApp === 'guild') initialTab = 'guild';
else if (startApp === 'hero') initialTab = 'hero';
else if (startApp === 'leaderboard') initialTab = 'leaderboard';
else if (startApp === 'shop') initialTab = 'shop';

function setActiveTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (targetBtn) targetBtn.classList.add('active');
    
    if (tabId === 'hero') loadHero();
    if (tabId === 'leaderboard') loadLeaderboard();
    if (tabId === 'shop') loadShop();
    if (tabId === 'campaign') loadCampaign();
    if (tabId === 'guild') { loadGuild(); loadGuildLeaderboard(); }
    
    if (tabId !== 'campaign') document.getElementById('bossBattleModal').style.display = 'none';
    if (tabId !== 'guild' && guildChatInterval) { clearInterval(guildChatInterval); guildChatInterval = null; }
}
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => setActiveTab(btn.getAttribute('data-tab')));
});
setActiveTab(initialTab);

// API вызовы
async function callAPI(endpoint, data = {}, method = 'POST') {
    let url = `/api/${endpoint}`;
    if (method === 'GET') {
        const params = new URLSearchParams();
        for (let key in data) params.append(key, data[key]);
        url += `?${params.toString()}`;
        const res = await fetch(url);
        return await res.json();
    } else {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, ...data })
        });
        return await res.json();
    }
}

// Загрузка героя
async function loadHero() {
    const profile = await callAPI('profile', {user_id: userId}, 'GET');
    if (!profile) return;
    document.getElementById('attackStat').innerText = profile.equipped_skin?.stat_bonus?.attack_pct || 0;
    document.getElementById('defenseStat').innerText = profile.equipped_skin?.stat_bonus?.defense_pct || 0;
    document.getElementById('energyStat').innerText = profile.equipped_skin?.stat_bonus?.energy_pct || 0;
    document.getElementById('luckStat').innerText = '10';
    document.getElementById('shardsCount').innerText = profile.shards;

    const skillsNames = ['Огненная стрела', 'Ледяной щит', 'Духовная связь', 'Цепная молния', 'Зов предков'];
    const levelsDiv = document.getElementById('skillsLevels');
    levelsDiv.innerHTML = '';
    profile.hero_levels.forEach((level, idx) => {
        const div = document.createElement('div');
        div.className = 'skill-upgrade-item';
        div.innerHTML = `
            <span>${skillsNames[idx]} : ур. ${level}</span>
            <button class="upgrade-skill" data-idx="${idx}">⬆️ (${50 * level} 💎)</button>
        `;
        levelsDiv.appendChild(div);
    });
    document.querySelectorAll('.upgrade-skill').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const res = await callAPI('upgrade_skill', { skill_index: parseInt(btn.getAttribute('data-idx')) });
            if (res.success) loadHero(); else tg.showAlert('Не хватает осколков!');
        });
    });

    const skinsDiv = document.getElementById('skinsList');
    skinsDiv.innerHTML = '';
    for (let skin of profile.owned_skins) {
        const card = document.createElement('div');
        card.className = 'skin-card';
        card.innerHTML = `<b>${skin.name}</b> (${skin.rarity})<br>${skin.equipped ? '✅ Надет' : `<button class="equip-skin" data-id="${skin.id}">Надеть</button>`}`;
        skinsDiv.appendChild(card);
    }
    document.querySelectorAll('.equip-skin').forEach(btn => {
        btn.addEventListener('click', async () => {
            await callAPI('equip_skin', { skin_id: parseInt(btn.getAttribute('data-id')) });
            loadHero();
        });
    });
}

async function loadLeaderboard() {
    const data = await callAPI('leaderboard', {}, 'GET');
    const tbody = document.querySelector('#leaderboardTable tbody');
    tbody.innerHTML = '';
    data.forEach((p, idx) => {
        const row = tbody.insertRow();
        row.insertCell(0).innerText = idx + 1;
        row.insertCell(1).innerHTML = p.username + (p.user_id == userId ? ' (вы)' : '');
        row.insertCell(2).innerText = p.rank;
        row.insertCell(3).innerText = p.wins;
        row.insertCell(4).innerText = p.skin_name;
        if (p.user_id == userId) row.classList.add('vip-gold');
    });
}

async function loadShop() {
    const skinsRes = await fetch('/api/skins_list?user_id=' + userId);
    const allSkins = await skinsRes.json();
    const profile = await callAPI('profile', {user_id: userId}, 'GET');
    const ownedIds = profile.owned_skins.map(s => s.id);
    const shopDiv = document.getElementById('shopItems');
    shopDiv.innerHTML = '';
    for (let skin of allSkins) {
        if (!ownedIds.includes(skin.id)) {
            const card = document.createElement('div');
            card.className = 'skin-card';
            card.innerHTML = `<b>${skin.name}</b><br>${skin.rarity}<br>${skin.price_stars} ⭐️<br><button class="buy-skin" data-id="${skin.id}">Купить</button>`;
            shopDiv.appendChild(card);
        }
    }
    document.querySelectorAll('.buy-skin').forEach(btn => {
        btn.addEventListener('click', async () => {
            const skinId = btn.getAttribute('data-id');
            const res = await callAPI('buy_skin', { skin_id: parseInt(skinId), confirm: false });
            if (res.need_invoice) {
                tg.showAlert('Демо-режим: скин добавлен бесплатно.');
                await callAPI('buy_skin', { skin_id: parseInt(skinId), confirm: true });
                loadShop(); loadHero();
            } else if (res.success) {
                tg.showAlert('Скин куплен!');
                loadShop(); loadHero();
            } else tg.showAlert('Ошибка покупки');
        });
    });
}

// PvP
async function findDuel() {
    const result = await callAPI('find_duel', {});
    if (result.status === 'no_tickets') { tg.showAlert('Нет билетов!'); return; }
    if (result.status === 'waiting') {
        tg.showAlert('Поиск соперника...');
        const interval = setInterval(async () => {
            const check = await callAPI('find_duel', {});
            if (check.match_id) { clearInterval(interval); startBattle(check.match_id, check.opponent); }
            else if (check.status !== 'waiting') { clearInterval(interval); tg.showAlert('Не удалось найти соперника.'); }
        }, 2000);
        return;
    }
    if (result.match_id) startBattle(result.match_id, result.opponent);
}

function startBattle(matchId, opponent) {
    currentMatchId = matchId; battleActive = true;
    document.getElementById('opponentName').innerText = opponent.username;
    document.getElementById('myName').innerText = username;
    document.getElementById('myHp').innerText = '100';
    document.getElementById('opponentHp').innerText = '100';
    document.getElementById('myHpFill').style.width = '100%';
    document.getElementById('opponentHpFill').style.width = '100%';
    document.getElementById('energy').innerText = '10';
    currentEnergy = 10; currentMyHp = 100; currentOpponentHp = 100;
    document.getElementById('battleLog').innerHTML = '';
    document.getElementById('findDuelBtn').disabled = true;
    if (battleInterval) clearInterval(battleInterval);
    battleInterval = setInterval(async () => {
        if (!battleActive) return;
        const state = await callAPI('duel_action', { match_id: currentMatchId, skill_index: null });
        if (state.battle_end) endBattle(state.winner_id);
        else { currentMyHp = state.player_hp; currentOpponentHp = state.opponent_hp; currentEnergy = state.player_energy; updateUI(); if (state.log) addLog(state.log, 'battleLog'); }
    }, 1000);
}

async function useSkill(skillIndex) {
    if (!battleActive) return;
    const result = await callAPI('duel_action', { match_id: currentMatchId, skill_index: skillIndex });
    if (result.error) { tg.showAlert(result.error); return; }
    if (result.battle_end) endBattle(result.winner_id);
    else { currentMyHp = result.player_hp; currentOpponentHp = result.opponent_hp; currentEnergy = result.player_energy; updateUI(); if (result.log) addLog(result.log, 'battleLog'); }
}

function updateUI() {
    document.getElementById('myHp').innerText = currentMyHp;
    document.getElementById('opponentHp').innerText = currentOpponentHp;
    document.getElementById('myHpFill').style.width = `${(currentMyHp/100)*100}%`;
    document.getElementById('opponentHpFill').style.width = `${(currentOpponentHp/100)*100}%`;
    document.getElementById('energy').innerText = currentEnergy;
}

function addLog(msg, logId = 'battleLog') {
    const logDiv = document.getElementById(logId);
    const p = document.createElement('div'); p.innerText = msg;
    if (logDiv) { logDiv.appendChild(p); logDiv.scrollTop = logDiv.scrollHeight; }
}

async function endBattle(winnerId) {
    battleActive = false; clearInterval(battleInterval);
    await callAPI('end_duel', { match_id: currentMatchId });
    tg.showAlert(winnerId == userId ? 'Победа! +10 💎' : 'Поражение... +3 💎');
    currentMatchId = null;
    document.getElementById('findDuelBtn').disabled = false;
}

// PvE Кампания
async function loadCampaign() {
    const data = await callAPI('campaign_progress', {}, 'GET');
    if (!data) return;
    const container = document.getElementById('chaptersContainer');
    container.innerHTML = '';
    data.chapters.forEach(chapter => {
        const chapterDiv = document.createElement('div');
        chapterDiv.className = 'pve-chapter' + (chapter.completed ? ' completed' : '') + (chapter.unlocked ? ' unlocked' : ' locked');
        let bossesHTML = chapter.bosses.map(boss => `
            <div class="pve-boss ${boss.defeated ? 'defeated' : ''} ${boss.available ? 'available' : 'locked'}">
                <div class="boss-icon">${boss.defeated ? '✅' : '👹'}</div>
                <div class="boss-info">
                    <div class="boss-name">${boss.name}</div>
                    <div class="boss-stats">❤️ ${boss.hp} | ⚔️ ${boss.damage}</div>
                    <div class="boss-mechanics">${boss.mechanics.join(', ')}</div>
                    <div class="boss-rewards">💎 ${boss.rewards.shards} ${boss.rewards.stars > 0 ? '⭐ ' + boss.rewards.stars : ''} ${boss.rewards.skin_id ? '🎁 Скин' : ''}</div>
                    ${boss.available ? '<button class="start-boss-btn" data-boss-id="' + boss.boss_id + '">⚔️ Сразиться</button>' : ''}
                </div>
            </div>
        `).join('');
        chapterDiv.innerHTML = `<h4 class="chapter-title">${chapter.name} ${chapter.completed ? '✅' : chapter.unlocked ? '🔓' : '🔒'}</h4><div class="chapter-bosses">${bossesHTML}</div>`;
        container.appendChild(chapterDiv);
    });
    document.querySelectorAll('.start-boss-btn').forEach(btn => {
        btn.addEventListener('click', async () => startPvEBattle(parseInt(btn.getAttribute('data-boss-id'))));
    });
}

async function startPvEBattle(bossId) {
    const result = await callAPI('pve_start_battle', { boss_id: bossId });
    if (!result.success) { tg.showAlert(result.error); return; }
    pveBattleActive = true; currentBossState = result.state;
    document.getElementById('bossBattleModal').style.display = 'flex';
    document.getElementById('bossName').innerText = currentBossState.boss_name;
    document.getElementById('claimPveRewards').style.display = 'none';
    document.getElementById('pveBattleLog').innerHTML = '';
    updatePvEUI();
    document.getElementById('closeBossBattle').onclick = () => {
        document.getElementById('bossBattleModal').style.display = 'none';
        pveBattleActive = false; loadCampaign();
    };
}

function updatePvEUI() {
    if (!currentBossState) return;
    document.getElementById('bossHp').innerText = currentBossState.boss_hp;
    document.getElementById('bossMaxHp').innerText = currentBossState.boss_max_hp;
    document.getElementById('bossHpFill').style.width = `${(currentBossState.boss_hp/currentBossState.boss_max_hp)*100}%`;
    document.getElementById('pveMyHp').innerText = currentBossState.player_hp;
    document.getElementById('pveMyHpFill').style.width = `${(currentBossState.player_hp/currentBossState.player_max_hp)*100}%`;
    document.getElementById('pveEnergy').innerText = currentBossState.player_energy;
    if (currentBossState.log) addLog(currentBossState.log, 'pveBattleLog');
    if (currentBossState.finished) {
        pveBattleActive = false;
        if (currentBossState.winner === 'player') document.getElementById('claimPveRewards').style.display = 'block';
        else { tg.showAlert('Поражение!'); setTimeout(() => { document.getElementById('bossBattleModal').style.display = 'none'; loadCampaign(); }, 2000); }
    }
}

async function usePvESkill(skillIndex) {
    if (!pveBattleActive) return;
    const result = await callAPI('pve_action', { skill_index: skillIndex });
    if (result.error) { tg.showAlert(result.error); return; }
    currentBossState = result; updatePvEUI();
}

document.getElementById('claimPveRewards').addEventListener('click', async () => {
    const result = await callAPI('pve_claim_rewards', {});
    if (result.success) {
        let msg = 'Награды:\n💎 +' + result.shards_earned + ' осколков\n';
        if (result.stars_earned > 0) msg += '⭐ +' + result.stars_earned + ' звёзд\n';
        if (result.skin_earned) msg += '🎁 Новый скин!\n';
        tg.showAlert(msg);
    }
    document.getElementById('bossBattleModal').style.display = 'none';
    pveBattleActive = false; loadCampaign();
});

// Гильдии
async function loadGuild() {
    const data = await callAPI('my_guild', {}, 'GET');
    if (!data.has_guild) {
        document.getElementById('noGuildSection').style.display = 'block';
        document.getElementById('guildSection').style.display = 'none';
        document.getElementById('createGuildBtn').onclick = () => document.getElementById('createGuildModal').style.display = 'flex';
        document.getElementById('closeCreateGuild').onclick = () => document.getElementById('createGuildModal').style.display = 'none';
        document.getElementById('confirmCreateGuild').onclick = createGuild;
        document.getElementById('searchGuildsBtn').onclick = searchGuilds;
        return;
    }
    
    document.getElementById('noGuildSection').style.display = 'none';
    document.getElementById('guildSection').style.display = 'block';
    
    const guild = data.guild;
    currentGuildId = guild.guild_id;
    
    document.getElementById('guildEmoji').innerText = guild.emoji;
    document.getElementById('guildName').innerText = guild.name;
    document.getElementById('guildLevel').innerText = 'Ур. ' + guild.level;
    document.getElementById('guildDescription').innerText = guild.description;
    document.getElementById('guildWarPoints').innerText = guild.war_points;
    document.getElementById('guildExp').innerText = guild.experience;
    document.getElementById('guildExpMax').innerText = guild.exp_for_next;
    document.getElementById('guildMemberCount').innerText = guild.members.length;
    
    // Здания
    const buildingsDiv = document.getElementById('buildingsList');
    buildingsDiv.innerHTML = '';
    guild.buildings.forEach(b => {
        const div = document.createElement('div');
        div.className = 'building-item';
        div.innerHTML = `<span>${b.bonus.name} (Ур. ${b.level})</span><span>${b.bonus.bonus}</span>${guild.user_role === 'leader' || guild.user_role === 'officer' ? '<button class="upgrade-building-btn" data-type="' + b.type + '">⬆️</button>' : ''}`;
        buildingsDiv.appendChild(div);
    });
    document.querySelectorAll('.upgrade-building-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const res = await callAPI('upgrade_building', { guild_id: currentGuildId, building_type: btn.getAttribute('data-type') });
            if (res.success) loadGuild(); else tg.showAlert(res.error);
        });
    });
    
    // Вклад
    document.querySelectorAll('.contribute-btn').forEach(btn => {
        btn.onclick = async () => {
            const amount = parseInt(btn.getAttribute('data-amount'));
            const res = await callAPI('contribute_guild', { amount: amount });
            if (res.success) { tg.showAlert('Вклад внесён!'); loadGuild(); } else tg.showAlert(res.error);
        };
    });
    
    // Участники
    const membersDiv = document.getElementById('guildMembersList');
    membersDiv.innerHTML = '';
    guild.members.forEach(m => {
        const div = document.createElement('div');
        div.className = 'member-item';
        let roleBadge = m.role === 'leader' ? '👑' : m.role === 'officer' ? '⭐' : m.role === 'veteran' ? '🛡️' : '';
        let promoteBtn = '';
        if (guild.user_role === 'leader' && m.role !== 'leader') {
            promoteBtn = `<button class="promote-btn" data-target="${m.user_id}" data-role="${m.role === 'officer' ? 'veteran' : 'officer'}">${m.role === 'officer' ? '⬇️' : '⬆️'}</button>`;
        }
        div.innerHTML = `${roleBadge} ${m.username} (📊 ${m.rank}) ${promoteBtn}`;
        membersDiv.appendChild(div);
    });
    document.querySelectorAll('.promote-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const res = await callAPI('promote_member', { leader_id: userId, target_id: parseInt(btn.getAttribute('data-target')), new_role: btn.getAttribute('data-role') });
            if (res.success) loadGuild(); else tg.showAlert(res.error);
        });
    });
    
    // Рейд
    loadRaidInfo(guild);
    document.getElementById('startRaidBtn').onclick = async () => {
        const res = await callAPI('start_guild_raid', { guild_id: currentGuildId, boss_level: 1 });
        if (res.success) { loadGuild(); } else tg.showAlert(res.error);
    };
    document.getElementById('attackRaidBoss').onclick = async () => {
        const damage = 1000; // фиксированный урон
        const res = await callAPI('attack_raid_boss', { raid_id: guild.active_raid?.raid_id, damage: damage });
        if (res.success) { tg.showAlert('Урон нанесён!'); loadGuild(); if (res.raid_completed) tg.showAlert('Рейд завершён!'); } else tg.showAlert(res.error);
    };
    
    // Чат
    loadGuildChat();
    if (guildChatInterval) clearInterval(guildChatInterval);
    guildChatInterval = setInterval(loadGuildChat, 3000);
    
    document.getElementById('sendGuildMessage').onclick = sendGuildMessage;
    document.getElementById('guildMessageInput').addEventListener('keypress', (e) => { if (e.key === 'Enter') sendGuildMessage(); });
    
    document.getElementById('leaveGuildBtn').onclick = async () => {
        if (confirm('Выйти из гильдии?')) {
            const res = await callAPI('leave_guild', {});
            if (res.success) { tg.showAlert('Вы покинули гильдию'); loadGuild(); } else tg.showAlert(res.error);
        }
    };
}

async function loadRaidInfo(guild) {
    if (guild.active_raid) {
        document.getElementById('activeRaid').style.display = 'block';
        document.getElementById('startRaidBtn').style.display = 'none';
        document.getElementById('raidBossName').innerText = guild.active_raid.boss_name;
        document.getElementById('raidBossCurrentHp').innerText = guild.active_raid.boss_current_hp;
        document.getElementById('raidBossMaxHp').innerText = guild.active_raid.boss_max_hp;
        document.getElementById('raidBossHpFill').style.width = `${(guild.active_raid.boss_current_hp / guild.active_raid.boss_max_hp) * 100}%`;
    } else {
        document.getElementById('activeRaid').style.display = 'none';
        document.getElementById('startRaidBtn').style.display = 'block';
    }
}

async function loadGuildChat() {
    if (!currentGuildId) return;
    const messages = await callAPI('guild_chat', { guild_id: currentGuildId }, 'GET');
    const chatDiv = document.getElementById('guildChatMessages');
    chatDiv.innerHTML = '';
    messages.forEach(m => {
        const div = document.createElement('div');
        div.className = 'chat-message';
        div.innerHTML = `<b>${m.username}:</b> ${m.message}`;
        chatDiv.appendChild(div);
    });
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

async function sendGuildMessage() {
    const input = document.getElementById('guildMessageInput');
    const message = input.value.trim();
    if (!message || !currentGuildId) return;
    await callAPI('guild_send_message', { guild_id: currentGuildId, username: username, message: message });
    input.value = '';
    loadGuildChat();
}

async function createGuild() {
    const name = document.getElementById('newGuildName').value.trim();
    const emoji = document.getElementById('newGuildEmoji').value.trim() || '🏰';
    const description = document.getElementById('newGuildDescription').value.trim();
    if (!name) { tg.showAlert('Введите название'); return; }
    const res = await callAPI('create_guild', { name: name, emoji: emoji, description: description });
    if (res.success) {
        tg.showAlert('Гильдия создана!');
        document.getElementById('createGuildModal').style.display = 'none';
        loadGuild();
    } else tg.showAlert(res.error);
}

async function searchGuilds() {
    const query = document.getElementById('guildSearchInput').value;
    const guilds = await callAPI('search_guilds', { query: query }, 'GET');
    const resultsDiv = document.getElementById('guildSearchResults');
    resultsDiv.innerHTML = '';
    guilds.forEach(g => {
        const div = document.createElement('div');
        div.className = 'guild-search-item';
        div.innerHTML = `${g.emoji} ${g.name} (Ур.${g.level} | ⭐${g.war_points} | 👥${g.member_count})<button class="join-guild-btn" data-guild-id="${g.guild_id}">Вступить</button>`;
        resultsDiv.appendChild(div);
    });
    document.querySelectorAll('.join-guild-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const res = await callAPI('join_guild', { guild_id: btn.getAttribute('data-guild-id') });
            if (res.success) { tg.showAlert('Вы вступили в гильдию!'); loadGuild(); } else tg.showAlert(res.error);
        });
    });
}

async function loadGuildLeaderboard() {
    const guilds = await callAPI('guild_leaderboard', {}, 'GET');
    const listDiv = document.getElementById('guildLeaderboardList');
    listDiv.innerHTML = '<h5>🏆 Топ-20 гильдий</h5>';
    guilds.forEach((g, idx) => {
        const div = document.createElement('div');
        div.className = 'leaderboard-item';
        div.innerHTML = `${idx + 1}. ${g.emoji} ${g.name} | Ур.${g.level} | ⭐${g.war_points} | 👥${g.member_count}`;
        listDiv.appendChild(div);
    });
}

// Обработчики
document.getElementById('findDuelBtn').addEventListener('click', findDuel);
document.querySelectorAll('.skill').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!battleActive) return;
        useSkill(parseInt(btn.getAttribute('data-skill')));
    });
});
document.querySelectorAll('.pve-skill').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!pveBattleActive) return;
        usePvESkill(parseInt(btn.getAttribute('data-skill')));
    });
});

// Реферальная система
if (urlParams.has('ref')) {
    const refId = parseInt(urlParams.get('ref'));
    if (refId && refId !== userId) {
        callAPI('claim_referral_reward', { referred_user_id: userId, user_id: refId });
    }
}
