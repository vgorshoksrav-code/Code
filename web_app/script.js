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

// ---------- Частицы (анимация фона) ----------
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
for (let i = 0; i < 100; i++) {
    particles.push(new Particle());
}
function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let p of particles) {
        p.update();
        p.draw();
    }
    requestAnimationFrame(animateParticles);
}
animateParticles();

// ---------- Парсинг startapp ----------
const urlParams = new URLSearchParams(window.location.search);
const startApp = urlParams.get('startapp');
let initialTab = 'duel';
if (startApp === 'duel') initialTab = 'duel';
else if (startApp === 'hero') initialTab = 'hero';
else if (startApp === 'leaderboard') initialTab = 'leaderboard';
else if (startApp === 'shop') initialTab = 'shop';

function setActiveTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('active');
    if (tabId === 'hero') loadHero();
    if (tabId === 'leaderboard') loadLeaderboard();
    if (tabId === 'shop') loadShop();
}
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-tab');
        setActiveTab(tab);
    });
});
setActiveTab(initialTab);

// API вызовы
async function callAPI(endpoint, data = {}, method = 'POST') {
    let url = `/api/${endpoint}`;
    if (method === 'GET') {
        url += `?user_id=${userId}`;
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
    const profile = await callAPI('profile', {}, 'GET');
    if (!profile) return;
    document.getElementById('attackStat').innerText = profile.equipped_skin?.stat_bonus?.attack_pct || 0;
    document.getElementById('defenseStat').innerText = profile.equipped_skin?.stat_bonus?.defense_pct || 0;
    let energyBonus = profile.equipped_skin?.stat_bonus?.energy_pct || 0;
    document.getElementById('energyStat').innerText = energyBonus;
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
            <button class="upgrade-skill" data-idx="${idx}">⬆️ Улучшить (${50 * level} оск.)</button>
        `;
        levelsDiv.appendChild(div);
    });
    document.querySelectorAll('.upgrade-skill').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const idx = btn.getAttribute('data-idx');
            const res = await callAPI('upgrade_skill', { skill_index: parseInt(idx) });
            if (res.success) {
                loadHero();
            } else {
                tg.showAlert('Не хватает осколков!');
            }
        });
    });

    const skinsDiv = document.getElementById('skinsList');
    skinsDiv.innerHTML = '';
    for (let skin of profile.owned_skins) {
        const card = document.createElement('div');
        card.className = 'skin-card';
        card.innerHTML = `
            <b>${skin.name}</b> (${skin.rarity})<br>
            ${skin.equipped ? '✅ Надет' : `<button class="equip-skin" data-id="${skin.id}">Надеть</button>`}
        `;
        skinsDiv.appendChild(card);
    }
    document.querySelectorAll('.equip-skin').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const skinId = btn.getAttribute('data-id');
            await callAPI('equip_skin', { skin_id: parseInt(skinId) });
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
    const profile = await callAPI('profile', {}, 'GET');
    const ownedIds = profile.owned_skins.map(s => s.id);
    const shopDiv = document.getElementById('shopItems');
    shopDiv.innerHTML = '';
    for (let skin of allSkins) {
        if (!ownedIds.includes(skin.id)) {
            const card = document.createElement('div');
            card.className = 'skin-card';
            card.innerHTML = `
                <b>${skin.name}</b><br>
                ${skin.rarity}<br>
                ${skin.price_stars} ⭐️<br>
                <button class="buy-skin" data-id="${skin.id}">Купить</button>
            `;
            shopDiv.appendChild(card);
        }
    }
    document.querySelectorAll('.buy-skin').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const skinId = btn.getAttribute('data-id');
            const res = await callAPI('buy_skin', { skin_id: parseInt(skinId), confirm: false });
            if (res.need_invoice) {
                tg.showAlert('Оплата через Telegram Stars. В демо-режиме скин будет добавлен бесплатно.');
                await callAPI('buy_skin', { skin_id: parseInt(skinId), confirm: true });
                loadShop();
                loadHero();
            } else if (res.success) {
                tg.showAlert('Скин куплен!');
                loadShop();
                loadHero();
            } else {
                tg.showAlert('Ошибка покупки');
            }
        });
    });
}

// PvP
async function findDuel() {
    const result = await callAPI('find_duel', {});
    if (result.status === 'no_tickets') {
        tg.showAlert('Закончились ежедневные билеты! Завтра будут новые.');
        return;
    }
    if (result.status === 'waiting') {
        tg.showAlert('Поиск соперника...');
        const interval = setInterval(async () => {
            const check = await callAPI('find_duel', {});
            if (check.match_id) {
                clearInterval(interval);
                startBattle(check.match_id, check.opponent);
            } else if (check.status !== 'waiting') {
                clearInterval(interval);
                tg.showAlert('Не удалось найти соперника, попробуйте позже.');
            }
        }, 2000);
        return;
    }
    if (result.match_id) {
        startBattle(result.match_id, result.opponent);
    }
}

function startBattle(matchId, opponent) {
    currentMatchId = matchId;
    battleActive = true;
    document.getElementById('opponentName').innerText = opponent.username;
    document.getElementById('myName').innerText = username;
    document.getElementById('myHp').innerText = '100';
    document.getElementById('opponentHp').innerText = '100';
    document.getElementById('myHpFill').style.width = '100%';
    document.getElementById('opponentHpFill').style.width = '100%';
    document.getElementById('energy').innerText = '10';
    currentEnergy = 10;
    currentMyHp = 100;
    currentOpponentHp = 100;
    document.getElementById('battleLog').innerHTML = '';
    document.getElementById('findDuelBtn').disabled = true;

    if (battleInterval) clearInterval(battleInterval);
    battleInterval = setInterval(async () => {
        if (!battleActive) return;
        const state = await callAPI('duel_action', { match_id: currentMatchId, skill_index: null });
        if (state.battle_end) {
            endBattle(state.winner_id);
        } else {
            currentMyHp = state.player_hp;
            currentOpponentHp = state.opponent_hp;
            currentEnergy = state.player_energy;
            updateUI();
            if (state.log) addLog(state.log);
        }
    }, 1000);
}

async function useSkill(skillIndex) {
    if (!battleActive) return;
    const result = await callAPI('duel_action', { match_id: currentMatchId, skill_index: skillIndex });
    if (result.error) {
        tg.showAlert(result.error);
        return;
    }
    if (result.battle_end) {
        endBattle(result.winner_id);
    } else {
        currentMyHp = result.player_hp;
        currentOpponentHp = result.opponent_hp;
        currentEnergy = result.player_energy;
        updateUI();
        if (result.log) addLog(result.log);
    }
}

function updateUI() {
    document.getElementById('myHp').innerText = currentMyHp;
    document.getElementById('opponentHp').innerText = currentOpponentHp;
    document.getElementById('myHpFill').style.width = `${(currentMyHp / 100) * 100}%`;
    document.getElementById('opponentHpFill').style.width = `${(currentOpponentHp / 100) * 100}%`;
    document.getElementById('energy').innerText = currentEnergy;
}

function addLog(msg) {
    const logDiv = document.getElementById('battleLog');
    const p = document.createElement('div');
    p.innerText = msg;
    logDiv.appendChild(p);
    logDiv.scrollTop = logDiv.scrollHeight;
}

async function endBattle(winnerId) {
    battleActive = false;
    clearInterval(battleInterval);
    await callAPI('end_duel', { match_id: currentMatchId });
    if (winnerId == userId) {
        tg.showAlert('Победа! +10 осколков');
    } else {
        tg.showAlert('Поражение... +3 осколка');
    }
    currentMatchId = null;
    document.getElementById('findDuelBtn').disabled = false;
}

document.getElementById('findDuelBtn').addEventListener('click', findDuel);
document.querySelectorAll('.skill').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!battleActive) return;
        const skillIdx = btn.getAttribute('data-skill');
        useSkill(parseInt(skillIdx));
    });
});

// Реферальная система
if (urlParams.has('ref')) {
    const refId = parseInt(urlParams.get('ref'));
    if (refId && refId !== userId) {
        callAPI('claim_referral_reward', { referred_user_id: userId, user_id: refId });
    }
}
