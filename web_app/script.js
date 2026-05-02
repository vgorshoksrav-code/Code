/* ═══════════════════════════════════════════
   ECHARIS — script.js  (полная версия)
═══════════════════════════════════════════ */

// ── Telegram Init ──────────────────────────
const tg = window.Telegram?.WebApp || { initDataUnsafe: {}, expand: () => {}, ready: () => {}, showAlert: (m) => alert(m) };
tg.expand();
tg.ready();
const tgUser = tg.initDataUnsafe?.user;
let userId   = tgUser?.id || null;
let username = tgUser?.username || (tgUser?.first_name ? tgUser.first_name : `guest_${Math.floor(Math.random()*9999)}`);

// ── i18n ───────────────────────────────────
const I18N = {
  ru: {
    findBattle:'Найти бой', searching:'Поиск соперника...', noTickets:'У вас закончились билеты!',
    win:'🏆 Победа! +15 💎', lose:'💀 Поражение... +5 💎', battleEnd:'Бой окончен',
    skill0:'Огн. стрела', skill1:'Лед. щит', skill2:'Связь', skill3:'Молния', skill4:'Зов предков',
    campaign:'Кампания', guild:'Гильдии', leaderboard:'Топ-20 игроков', shop:'Магазин скинов',
    notEnoughEnergy:'Недостаточно энергии', giftTitle:'Ежедневный подарок!', giftClaim:'Забрать!',
    tutorial: [
      {icon:'🌌', title:'Добро пожаловать в Эхарис!', text:'Это мир вечных дуэлей душ. Сражайся с игроками и боссами, собирай скины и стань легендой!'},
      {icon:'⚔️', title:'Система боя', text:'Нажимай скиллы во время дуэли. Каждый скилл тратит энергию — следи за шкалой ⚡. Энергия восстанавливается автоматически.'},
      {icon:'💎', title:'Осколки и скины', text:'Побеждая в боях, ты получаешь осколки 💎. Используй их для улучшения скиллов. Скины покупаются за Telegram Stars ⭐.'},
      {icon:'🎁', title:'Ежедневный подарок', text:'Каждые 24 часа нажимай 🎁 вверху экрана и получай бесплатные осколки и билеты. Иногда выпадают редкие скины!'},
    ],
  },
  en: {
    findBattle:'Find Battle', searching:'Searching opponent...', noTickets:'No tickets left!',
    win:'🏆 Victory! +15 💎', lose:'💀 Defeat... +5 💎', battleEnd:'Battle over',
    skill0:'Fire Arrow', skill1:'Ice Shield', skill2:'Bond', skill3:'Lightning', skill4:'Ancestor Call',
    campaign:'Campaign', guild:'Guilds', leaderboard:'Top-20 Players', shop:'Skin Shop',
    notEnoughEnergy:'Not enough energy', giftTitle:'Daily Gift!', giftClaim:'Claim!',
    tutorial: [
      {icon:'🌌', title:'Welcome to Echaris!', text:'A world of eternal soul duels. Fight players and bosses, collect skins, become a legend!'},
      {icon:'⚔️', title:'Battle System', text:'Tap skills during a duel. Each skill costs ⚡ energy — watch the bar. Energy regenerates automatically.'},
      {icon:'💎', title:'Shards & Skins', text:'Win battles to earn shards 💎. Use them to upgrade skills. Skins are bought with Telegram Stars ⭐.'},
      {icon:'🎁', title:'Daily Gift', text:'Every 24 hours tap 🎁 at the top to get free shards and tickets. Rare skins sometimes drop!'},
    ],
  }
};
let lang = 'ru';
function t(key) { return (I18N[lang] && I18N[lang][key]) || (I18N.ru[key]) || key; }
function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    el.textContent = t(k);
  });
}

// ── Hero Avatar Map ────────────────────────
const AVATAR_MAP = {
  warrior:'⚔️', mage:'🧙', archer:'🏹', rogue:'🗡️', paladin:'🛡️', necromancer:'💀'
};
let myHeroAvatar = '🧙';

// ── State ──────────────────────────────────
let currentMatchId  = null;
let battleActive    = false;
let battleInterval  = null;
let searchInterval  = null;
let currentEnergy   = 10;
let maxEnergy       = 30;
let currentMyHp     = 100;
let currentOpponentHp = 100;
let pveBattleActive = false;
let currentBossState = null;
let currentGuildId  = null;
let guildChatInterval = null;
let profileCache    = null;
let allSkinsCache   = null;
let shopRarityFilter = 'all';
let tutorialStep    = 0;

// ── API helper ─────────────────────────────
async function callAPI(endpoint, data = {}, method = 'POST') {
  try {
    const url = `/api/${endpoint}`;
    if (method === 'GET') {
      const p = new URLSearchParams({ ...data });
      const r = await fetch(`${url}?${p}`);
      return await r.json();
    }
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, ...data })
    });
    return await r.json();
  } catch (e) {
    console.error('API error', e);
    return { error: String(e) };
  }
}

// ── Particles ──────────────────────────────
const canvas = document.getElementById('particlesCanvas');
const ctx    = canvas.getContext('2d');
let particles = [];
function resizeCanvas() { canvas.width = innerWidth; canvas.height = innerHeight; }
window.addEventListener('resize', resizeCanvas);
resizeCanvas();
class Particle {
  constructor() { this.reset(); }
  reset() {
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.size = Math.random() * 1.5 + 0.5;
    this.vx = (Math.random() - 0.5) * 0.4;
    this.vy = (Math.random() - 0.5) * 0.4;
    this.alpha = Math.random() * 0.25 + 0.05;
    this.hue = Math.random() < 0.5 ? 50 : 270;
  }
  update() {
    this.x += this.vx; this.y += this.vy;
    if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) this.reset();
  }
  draw() {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI*2);
    ctx.fillStyle = `hsla(${this.hue},100%,70%,${this.alpha})`;
    ctx.fill();
  }
}
for (let i = 0; i < 120; i++) particles.push(new Particle());
(function anim() { ctx.clearRect(0,0,canvas.width,canvas.height); particles.forEach(p => { p.update(); p.draw(); }); requestAnimationFrame(anim); })();

// ── Splash ─────────────────────────────────
function runSplash(cb) {
  const fill = document.getElementById('splashFill');
  let pct = 0;
  const iv = setInterval(() => {
    pct += Math.random() * 15 + 5;
    fill.style.width = Math.min(pct, 100) + '%';
    if (pct >= 100) { clearInterval(iv); setTimeout(cb, 300); }
  }, 100);
}

// ── Tutorial ───────────────────────────────
function showTutorial() {
  const steps = I18N[lang].tutorial;
  const overlay = document.getElementById('tutorialOverlay');
  const dots    = document.getElementById('tutorialDots');
  dots.innerHTML = steps.map((_, i) => `<div class="dot${i===0?' active':''}"></div>`).join('');
  function renderStep(i) {
    const s = steps[i];
    document.getElementById('tutorialTitle').textContent = s.title;
    document.getElementById('tutorialText').textContent  = s.text;
    document.querySelector('.tutorial-icon').textContent = s.icon;
    dots.querySelectorAll('.dot').forEach((d, di) => d.classList.toggle('active', di === i));
    document.getElementById('tutorialNextBtn').textContent = (i < steps.length - 1) ? t('далее') || 'Далее →' : '▶ Играть!';
  }
  tutorialStep = 0;
  renderStep(0);
  overlay.style.display = 'flex';
  document.getElementById('tutorialNextBtn').onclick = () => {
    tutorialStep++;
    if (tutorialStep < steps.length) renderStep(tutorialStep);
    else { overlay.style.display = 'none'; localStorage.setItem('echaris_tutorial_done', '1'); }
  };
}

// ── App Init ────────────────────────────────
async function initApp() {
  const splash = document.getElementById('splashScreen');
  runSplash(async () => {
    splash.style.transition = 'opacity 0.4s';
    splash.style.opacity = '0';
    setTimeout(() => splash.style.display = 'none', 400);

    // register / load profile
    if (userId) {
      await callAPI('register', { username });
      profileCache = await callAPI('profile', { user_id: userId }, 'GET');
      if (profileCache) {
        lang = profileCache.language || 'ru';
        myHeroAvatar = AVATAR_MAP[profileCache.hero_avatar] || '🧙';
        updateTopBar(profileCache);
        applyI18n();
        if (profileCache.gift_available) {
          document.getElementById('giftBtn').classList.add('pulse');
        }
      }
    }

    document.getElementById('mainContent').style.display = 'block';

    // tutorial for new users
    if (!localStorage.getItem('echaris_tutorial_done')) {
      setTimeout(showTutorial, 500);
    }

    // parse startapp
    const params = new URLSearchParams(location.search);
    const startApp = params.get('startapp') || 'duel';
    const refId = params.get('ref');
    if (refId && userId && parseInt(refId) !== userId) {
      callAPI('claim_referral_reward', { referred_user_id: userId, user_id: parseInt(refId) });
    }
    setActiveTab(['duel','campaign','guild','hero','leaderboard','shop'].includes(startApp) ? startApp : 'duel');
  });
}

function updateTopBar(profile) {
  document.getElementById('topbarAvatar').textContent  = myHeroAvatar;
  document.getElementById('topbarName').textContent    = profile.username || username;
  document.getElementById('topbarRank').textContent    = '⚔️ ' + (profile.rank || 1000);
  document.getElementById('topbarShards').textContent  = profile.shards || 0;
  document.getElementById('topbarTickets').textContent = profile.daily_tickets || 0;
}

// ── Tabs ───────────────────────────────────
function setActiveTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  const el = document.getElementById(tabId);
  if (el) el.classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === tabId));
  if (tabId === 'hero')        loadHero();
  if (tabId === 'leaderboard') loadLeaderboard();
  if (tabId === 'shop')        loadShop();
  if (tabId === 'campaign')    loadCampaign();
  if (tabId === 'guild')       { loadGuild(); loadGuildLeaderboard(); }
  if (tabId !== 'campaign')    document.getElementById('bossBattleModal').style.display = 'none';
  if (tabId !== 'guild' && guildChatInterval) { clearInterval(guildChatInterval); guildChatInterval = null; }
}
document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => setActiveTab(btn.getAttribute('data-tab'))));

// ── Daily Gift ──────────────────────────────
document.getElementById('giftBtn').addEventListener('click', async () => {
  if (!userId) return;
  const profile = await callAPI('profile', { user_id: userId }, 'GET');
  if (!profile.gift_available) {
    tg.showAlert('Подарок уже получен сегодня. Приходи завтра! 🌙');
    return;
  }
  // Show gift modal
  const modal = document.getElementById('giftModal');
  const list  = document.getElementById('giftRewardsList');
  list.innerHTML = '<div style="color:var(--muted);font-size:14px">Открываем подарок...</div>';
  modal.style.display = 'flex';
  const result = await callAPI('daily_gift', {});
  if (result.success) {
    list.innerHTML = result.rewards.map(r => `<div class="gift-reward-item">${r}</div>`).join('');
    document.getElementById('giftBtn').classList.remove('pulse');
    // refresh topbar
    profileCache = await callAPI('profile', { user_id: userId }, 'GET');
    if (profileCache) updateTopBar(profileCache);
  } else {
    list.innerHTML = `<div class="gift-reward-item">${result.error || 'Подарок уже получен!'}</div>`;
  }
});
document.getElementById('claimGiftBtn').addEventListener('click', () => {
  document.getElementById('giftModal').style.display = 'none';
});

// ── Language Toggle ─────────────────────────
document.getElementById('langBtn').addEventListener('click', async () => {
  lang = lang === 'ru' ? 'en' : 'ru';
  document.getElementById('langBtn').textContent = lang === 'ru' ? '🇷🇺' : '🇬🇧';
  applyI18n();
  if (userId) await callAPI('set_language', { language: lang });
});

// ── PvP: Find Duel ─────────────────────────
document.getElementById('findDuelBtn').addEventListener('click', findDuel);
document.getElementById('cancelSearchBtn').addEventListener('click', cancelSearch);

async function findDuel() {
  if (!userId) { tg.showAlert('Открой приложение через Telegram!'); return; }
  document.getElementById('findDuelBtn').style.display = 'none';
  document.getElementById('searchingSpinner').style.display = 'flex';
  clearBattleLog();

  // immediate attempt
  let result = await callAPI('find_duel', {});
  if (result.status === 'no_tickets') {
    tg.showAlert(t('noTickets'));
    resetDuelUI();
    return;
  }
  if (result.match_id) { startBattle(result.match_id, result.opponent); return; }

  // poll for match
  let attempts = 0;
  searchInterval = setInterval(async () => {
    attempts++;
    const check = await callAPI('find_duel', {});
    if (check.match_id) {
      clearInterval(searchInterval);
      startBattle(check.match_id, check.opponent);
    } else if (check.status === 'no_tickets') {
      clearInterval(searchInterval);
      tg.showAlert(t('noTickets'));
      resetDuelUI();
    } else if (attempts >= 5) {
      // force AI match after 10 sec
      clearInterval(searchInterval);
      const ai = await callAPI('find_duel', {}); // server will create AI match
      if (ai.match_id) startBattle(ai.match_id, ai.opponent);
      else resetDuelUI();
    }
  }, 2000);
}

function cancelSearch() {
  clearInterval(searchInterval);
  resetDuelUI();
}

function resetDuelUI() {
  document.getElementById('findDuelBtn').style.display = 'flex';
  document.getElementById('searchingSpinner').style.display = 'none';
}

function startBattle(matchId, opponent) {
  currentMatchId      = matchId;
  battleActive        = true;
  currentMyHp         = 100;
  currentOpponentHp   = 100;
  currentEnergy       = 10;

  document.getElementById('findDuelBtn').style.display = 'none';
  document.getElementById('searchingSpinner').style.display = 'none';

  // Set avatars
  document.getElementById('myAvatar').textContent       = myHeroAvatar;
  document.getElementById('opponentAvatar').textContent = (opponent.skin_emoji || '👤');
  document.getElementById('myName').textContent         = username;
  document.getElementById('opponentName').textContent   = opponent.username;

  updateDuelUI(100, 100, 10);
  showBattleTimer(30);
  addLog(`⚔️ Бой начался! Противник: ${opponent.username} [${opponent.rank}]`);

  // Poll loop
  if (battleInterval) clearInterval(battleInterval);
  battleInterval = setInterval(pollBattle, 1000);
}

async function pollBattle() {
  if (!battleActive || !currentMatchId) return;
  const state = await callAPI('duel_action', { match_id: currentMatchId, skill_index: null });
  if (!state) return;
  if (state.battle_end) {
    finishBattle(state.winner_id, state.log);
  } else {
    updateDuelUI(state.player_hp, state.opponent_hp, state.player_energy);
    if (state.log) addLog(state.log);
  }
}

async function useSkill(idx) {
  if (!battleActive || !currentMatchId) return;
  const result = await callAPI('duel_action', { match_id: currentMatchId, skill_index: idx });
  if (!result) return;
  if (result.error) { addLog('❌ ' + result.error); return; }
  if (result.battle_end) {
    finishBattle(result.winner_id, result.log);
  } else {
    updateDuelUI(result.player_hp, result.opponent_hp, result.player_energy);
    if (result.log) {
      addLog(result.log);
      showDmgFloat(result.log);
    }
  }
}

function showDmgFloat(log) {
  const myEl   = document.getElementById('myAvatarWrap');
  const oppEl  = document.getElementById('opponentAvatarWrap');
  const rect   = log.includes('нанёс') ? oppEl.getBoundingClientRect() : myEl.getBoundingClientRect();
  const el     = document.createElement('div');
  el.className = 'dmg-float ' + (log.includes('нанёс') ? 'negative' : 'positive');
  const match  = log.match(/\d+/);
  el.textContent = (log.includes('восстановил') ? '+' : '-') + (match ? match[0] : '?');
  el.style.left  = rect.left + rect.width/2 + 'px';
  el.style.top   = rect.top  + 'px';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 850);
}

function finishBattle(winnerId, log) {
  clearInterval(battleInterval);
  if (hideBattleTimer) hideBattleTimer();
  battleActive = false;
  currentMatchId = null;
  const won = (String(winnerId) === String(userId));
  addLog(won ? '🏆 ВЫ ПОБЕДИЛИ!' : '💀 Поражение...');
  setTimeout(() => {
    tg.showAlert(won ? t('win') : t('lose'));
    // update topbar
    callAPI('profile', { user_id: userId }, 'GET').then(p => { if (p) { profileCache=p; updateTopBar(p); } });
    document.getElementById('findDuelBtn').style.display = 'flex';
    updateDuelUI(currentMyHp, currentOpponentHp, currentEnergy);
  }, 400);
}

function updateDuelUI(myHp, oppHp, energy) {
  currentMyHp        = Math.max(0, myHp);
  currentOpponentHp  = Math.max(0, oppHp);
  currentEnergy      = energy;
  document.getElementById('myHp').textContent          = currentMyHp;
  document.getElementById('opponentHp').textContent    = currentOpponentHp;
  document.getElementById('myHpFill').style.width      = currentMyHp + '%';
  document.getElementById('opponentHpFill').style.width = currentOpponentHp + '%';
  document.getElementById('energy').textContent        = currentEnergy;
  document.getElementById('energyBar').style.width     = (currentEnergy / maxEnergy * 100) + '%';
}

let timerInterval = null;
let hideBattleTimer = null;
function showBattleTimer(seconds) {
  const el = document.getElementById('battleTimer');
  el.style.display = 'block';
  let left = seconds;
  el.textContent = left;
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    left--;
    el.textContent = left;
    if (left <= 0) { clearInterval(timerInterval); el.style.display = 'none'; }
  }, 1000);
  hideBattleTimer = () => { clearInterval(timerInterval); el.style.display = 'none'; };
}

function addLog(msg) {
  const log = document.getElementById('battleLog');
  const d = document.createElement('div');
  d.textContent = msg;
  if (msg.includes('нанёс')) d.classList.add('log-hit');
  if (msg.includes('восстановил')) d.classList.add('log-heal');
  if (msg.includes('щит')) d.classList.add('log-shield');
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
function clearBattleLog() { document.getElementById('battleLog').innerHTML = ''; }

document.querySelectorAll('.skill-card:not(.pve-skill)').forEach(btn => {
  btn.addEventListener('click', () => { if (battleActive) useSkill(parseInt(btn.getAttribute('data-skill'))); });
});

// ── Hero Tab ───────────────────────────────
async function loadHero() {
  const profile = await callAPI('profile', { user_id: userId }, 'GET');
  if (!profile) return;
  profileCache = profile;
  myHeroAvatar = AVATAR_MAP[profile.hero_avatar] || '🧙';
  updateTopBar(profile);

  document.getElementById('heroAvatarDisplay').textContent = myHeroAvatar;
  document.getElementById('attackStat').textContent  = (profile.equipped_skin?.stat_bonus?.attack_pct  || 0) + '%';
  document.getElementById('defenseStat').textContent = (profile.equipped_skin?.stat_bonus?.defense_pct || 0) + '%';
  document.getElementById('energyStat').textContent  = (profile.equipped_skin?.stat_bonus?.energy_pct  || 0) + '%';
  document.getElementById('heroRank').textContent    = profile.rank;
  document.getElementById('heroWins').textContent    = profile.wins;
  document.getElementById('shardsCount').textContent = profile.shards;

  const skillNames = [t('skill0'),t('skill1'),t('skill2'),t('skill3'),t('skill4')];
  const costs = [5,4,6,8,12];
  const container = document.getElementById('skillsLevels');
  container.innerHTML = '';
  profile.hero_levels.forEach((lv, i) => {
    const cost = 50 * lv;
    const row  = document.createElement('div');
    row.className = 'skill-upgrade-row';
    row.innerHTML = `
      <div>
        <div class="sname">${skillNames[i]}</div>
        <div class="slevel">Ур. ${lv} · стоит ${cost} 💎</div>
      </div>
      <button class="upgrade-btn" data-idx="${i}" ${profile.shards < cost ? 'disabled' : ''}>⬆️ Прокачать</button>
    `;
    container.appendChild(row);
  });
  container.querySelectorAll('.upgrade-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const res = await callAPI('upgrade_skill', { skill_index: parseInt(btn.getAttribute('data-idx')) });
      if (res.success) loadHero();
      else tg.showAlert(res.error || 'Не хватает осколков!');
    });
  });

  const skinsDiv = document.getElementById('skinsList');
  skinsDiv.innerHTML = '';
  (profile.owned_skins || []).forEach(skin => {
    const card = document.createElement('div');
    card.className = 'skin-card' + (skin.equipped ? ' equipped-card' : '');
    card.innerHTML = `
      <div class="skin-emoji">${skin.emoji || '🧙'}</div>
      <div class="skin-name">${skin.name}</div>
      <div class="skin-rarity rarity-${skin.rarity}">${skin.rarity}</div>
      ${skin.equipped ? '<div class="equipped-badge">✅ Надет</div>' : `<button class="equip-btn" data-id="${skin.id}">Надеть</button>`}
    `;
    skinsDiv.appendChild(card);
  });
  document.querySelectorAll('.equip-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await callAPI('equip_skin', { skin_id: parseInt(btn.getAttribute('data-id')) });
      loadHero();
    });
  });
}

// Avatar picker
document.getElementById('changeAvatarBtn').addEventListener('click', () => {
  document.getElementById('avatarPickerModal').style.display = 'flex';
});
document.getElementById('closeAvatarPicker').addEventListener('click', () => {
  document.getElementById('avatarPickerModal').style.display = 'none';
});
document.querySelectorAll('.avatar-option').forEach(opt => {
  opt.addEventListener('click', async () => {
    const av = opt.getAttribute('data-avatar');
    await callAPI('set_avatar', { avatar: av });
    myHeroAvatar = AVATAR_MAP[av] || '🧙';
    document.getElementById('heroAvatarDisplay').textContent = myHeroAvatar;
    document.getElementById('topbarAvatar').textContent = myHeroAvatar;
    document.getElementById('myAvatar').textContent = myHeroAvatar;
    document.getElementById('avatarPickerModal').style.display = 'none';
  });
});

// ── Leaderboard ─────────────────────────────
async function loadLeaderboard() {
  const data = await callAPI('leaderboard', {}, 'GET');
  const list = document.getElementById('leaderboardList');
  list.innerHTML = '';
  (data || []).forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'lb-row' + (String(p.user_id) === String(userId) ? ' me' : '');
    const rankClass = i===0?'top1':i===1?'top2':i===2?'top3':'';
    const medal = i===0?'🥇':i===1?'🥈':i===2?'🥉':(i+1);
    row.innerHTML = `
      <div class="lb-rank ${rankClass}">${medal}</div>
      <div class="lb-skin">${p.skin_emoji || '🧙'}</div>
      <div class="lb-info">
        <div class="lb-name">${escHtml(p.username)}${p.is_vip ? '<span class="vip-crown">👑</span>' : ''}</div>
        <div class="lb-meta">${p.skin_name}</div>
      </div>
      <div class="lb-score">
        <div class="lb-elo">${p.rank}</div>
        <div class="lb-wins">⚔️ ${p.wins} побед</div>
      </div>
    `;
    list.appendChild(row);
  });
}

// ── Shop ─────────────────────────────────────
async function loadShop() {
  if (!allSkinsCache) {
    allSkinsCache = await callAPI('skins_list', { user_id: userId }, 'GET');
  }
  const profile = profileCache || await callAPI('profile', { user_id: userId }, 'GET');
  const owned   = new Set((profile?.owned_skins || []).map(s => s.id));
  renderShop(allSkinsCache, owned);
}

function renderShop(skins, owned) {
  const grid = document.getElementById('shopItems');
  grid.innerHTML = '';
  skins.forEach(skin => {
    if (shopRarityFilter !== 'all' && skin.rarity !== shopRarityFilter) return;
    const isOwned = owned.has(skin.id);
    const card = document.createElement('div');
    card.className = 'shop-card' + (isOwned ? ' owned-card' : '');
    const bonus = (() => {
      try {
        const b = JSON.parse(skin.stat_bonus || '{}');
        return Object.entries(b).map(([k,v]) => `${k.replace('_pct','')}: ${v>0?'+':''}${v}%`).join(' · ');
      } catch { return ''; }
    })();
    card.innerHTML = `
      <div class="shop-emoji">${skin.emoji || '🧙'}</div>
      <div class="shop-name">${escHtml(skin.name)}</div>
      <div class="skin-rarity rarity-${skin.rarity}">${skin.rarity}</div>
      <div class="shop-desc">${escHtml(skin.description || '')}</div>
      ${bonus ? `<div class="shop-bonus">${bonus}</div>` : ''}
      ${skin.price_stars > 0 ? `<div class="shop-price">⭐ ${skin.price_stars} Stars</div>` : '<div class="shop-price">🆓 Бесплатно</div>'}
      ${isOwned ? '<div class="owned-tag">✅ Есть в коллекции</div>' : `<button class="buy-btn" data-id="${skin.id}" data-price="${skin.price_stars}" data-name="${escHtml(skin.name)}">Купить</button>`}
    `;
    grid.appendChild(card);
  });
  document.querySelectorAll('.buy-btn').forEach(btn => {
    btn.addEventListener('click', () => buySkin(parseInt(btn.getAttribute('data-id')), parseInt(btn.getAttribute('data-price')), btn.getAttribute('data-name')));
  });
}

async function buySkin(skinId, price, name) {
  if (price === 0) {
    const res = await callAPI('buy_skin', { skin_id: skinId, confirm: true });
    if (res.success) { tg.showAlert(`✅ Скин "${name}" получен!`); allSkinsCache=null; loadShop(); loadHero(); }
    else tg.showAlert(res.error || 'Ошибка');
    return;
  }
  const r1 = await callAPI('buy_skin', { skin_id: skinId, confirm: false });
  if (r1.need_invoice) {
    tg.showAlert(`Для покупки "${name}" нужно ${price} Telegram Stars ⭐.\nФункция оплаты будет доступна в финальной версии.\n\nДля теста скин добавлен бесплатно!`);
    const r2 = await callAPI('buy_skin', { skin_id: skinId, confirm: true });
    if (r2.success) { allSkinsCache=null; loadShop(); loadHero(); }
  } else if (r1.success) {
    allSkinsCache = null; loadShop(); loadHero();
  } else tg.showAlert(r1.error || 'Ошибка покупки');
}

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    shopRarityFilter = btn.getAttribute('data-rarity');
    if (!allSkinsCache) allSkinsCache = await callAPI('skins_list', { user_id: userId }, 'GET');
    const profile = profileCache || await callAPI('profile', { user_id: userId }, 'GET');
    const owned = new Set((profile?.owned_skins || []).map(s => s.id));
    renderShop(allSkinsCache, owned);
  });
});

// ── PvE ───────────────────────────────────────
async function loadCampaign() {
  const data = await callAPI('campaign_progress', { user_id: userId }, 'GET');
  if (!data) return;
  const container = document.getElementById('chaptersContainer');
  container.innerHTML = '';
  data.chapters.forEach(chapter => {
    const div = document.createElement('div');
    div.className = 'pve-chapter' + (chapter.completed?' completed':'') + (!chapter.unlocked?' locked':'');
    let bossesHtml = chapter.bosses.map(boss => {
      const available = boss.available;
      const defeated  = boss.defeated;
      const locked    = !available && !defeated;
      return `
        <div class="pve-boss ${defeated?'defeated':''} ${available?'available':''}">
          <div class="boss-icon-sm">${defeated?'✅':locked?'🔒':'👹'}</div>
          <div class="boss-info-col">
            <div class="boss-title-sm">${escHtml(boss.name)}</div>
            <div class="boss-stats-sm">❤️ ${boss.hp} · ⚔️ ${boss.damage}</div>
            ${boss.mechanics.length ? `<div class="boss-mech">⚡ ${boss.mechanics.join(', ')}</div>` : ''}
            <div class="boss-reward-sm">💎 ${boss.rewards.shards}${boss.rewards.stars>0?' · ⭐ '+boss.rewards.stars:''}${boss.rewards.skin_id?' · 🎁 Скин':''}</div>
            ${available ? `<button class="start-boss-btn" data-boss-id="${boss.boss_id}">⚔️ Сразиться</button>` : ''}
          </div>
        </div>
      `;
    }).join('');
    div.innerHTML = `<div class="chapter-title">Гл. ${chapter.chapter}: ${chapter.name} ${chapter.completed?'✅':chapter.unlocked?'🔓':'🔒'}</div><div class="chapter-bosses">${bossesHtml}</div>`;
    container.appendChild(div);
  });
  container.querySelectorAll('.start-boss-btn').forEach(btn => {
    btn.addEventListener('click', () => startPvEBattle(parseInt(btn.getAttribute('data-boss-id'))));
  });
}

async function startPvEBattle(bossId) {
  const result = await callAPI('pve_start_battle', { boss_id: bossId });
  if (!result.success) { tg.showAlert(result.error || 'Ошибка'); return; }
  pveBattleActive = true;
  currentBossState = result.state;
  document.getElementById('bossBattleModal').style.display = 'flex';
  document.getElementById('bossName').textContent = currentBossState.boss_name;
  document.getElementById('bossAvatarBig').textContent = currentBossState.boss_emoji || '👹';
  document.getElementById('claimPveRewards').style.display = 'none';
  document.getElementById('pveBattleLog').innerHTML = '';
  updatePvEUI();
}

function updatePvEUI() {
  if (!currentBossState) return;
  const bs = currentBossState;
  document.getElementById('bossHp').textContent    = bs.boss_hp;
  document.getElementById('bossMaxHp').textContent = bs.boss_max_hp;
  document.getElementById('bossHpFill').style.width = (bs.boss_hp / bs.boss_max_hp * 100) + '%';
  document.getElementById('pveMyHp').textContent   = bs.player_hp;
  document.getElementById('pveMyHpFill').style.width = (bs.player_hp / bs.player_max_hp * 100) + '%';
  document.getElementById('pveEnergy').textContent = bs.player_energy;
  if (bs.log) {
    const log = document.getElementById('pveBattleLog');
    const d = document.createElement('div');
    d.textContent = bs.log;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  if (bs.finished) {
    pveBattleActive = false;
    if (bs.winner === 'player') document.getElementById('claimPveRewards').style.display = 'block';
    else {
      setTimeout(() => {
        tg.showAlert('💀 Поражение!');
        document.getElementById('bossBattleModal').style.display = 'none';
        loadCampaign();
      }, 1000);
    }
  }
}

async function usePvESkill(idx) {
  if (!pveBattleActive) return;
  const result = await callAPI('pve_action', { skill_index: idx });
  if (result.error) { tg.showAlert(result.error); return; }
  currentBossState = result;
  updatePvEUI();
}

document.querySelectorAll('.pve-skill').forEach(btn => {
  btn.addEventListener('click', () => { if (pveBattleActive) usePvESkill(parseInt(btn.getAttribute('data-skill'))); });
});
document.getElementById('closeBossBattle').addEventListener('click', () => {
  document.getElementById('bossBattleModal').style.display = 'none';
  pveBattleActive = false;
  loadCampaign();
});
document.getElementById('claimPveRewards').addEventListener('click', async () => {
  const result = await callAPI('pve_claim_rewards', {});
  if (result.success) {
    let msg = `🎉 Награды!\n💎 +${result.shards_earned} осколков`;
    if (result.stars_earned > 0) msg += `\n⭐ +${result.stars_earned} звёзд`;
    if (result.skin_reward) msg += `\n🎁 Новый скин!`;
    tg.showAlert(msg);
  }
  document.getElementById('bossBattleModal').style.display = 'none';
  pveBattleActive = false;
  loadCampaign();
  callAPI('profile', { user_id: userId }, 'GET').then(p => { if (p) { profileCache=p; updateTopBar(p); } });
});

// ── Guild ─────────────────────────────────────
async function loadGuild() {
  const data = await callAPI('my_guild', { user_id: userId }, 'GET');
  if (!data.has_guild) {
    document.getElementById('noGuildSection').style.display = 'block';
    document.getElementById('guildSection').style.display = 'none';
    bindNoGuildUI();
    return;
  }
  document.getElementById('noGuildSection').style.display = 'none';
  document.getElementById('guildSection').style.display = 'block';
  const g = data.guild;
  currentGuildId = g.guild_id;
  document.getElementById('guildEmoji').textContent    = g.emoji;
  document.getElementById('guildName').textContent     = g.name;
  document.getElementById('guildLevel').textContent    = 'Ур. ' + g.level;
  document.getElementById('guildDescription').textContent = g.description;
  document.getElementById('guildWarPoints').textContent = g.war_points;
  document.getElementById('guildExp').textContent      = g.experience;
  document.getElementById('guildExpMax').textContent   = g.exp_for_next;
  document.getElementById('guildMemberCount').textContent = (g.members || []).length;

  // Buildings
  const bDiv = document.getElementById('buildingsList');
  bDiv.innerHTML = '';
  (g.buildings || []).forEach(b => {
    const row = document.createElement('div');
    row.className = 'building-row';
    row.innerHTML = `<span>${escHtml(b.bonus.name)} (Ур.${b.level}) — ${escHtml(b.bonus.bonus)}</span>
      ${(g.user_role==='leader'||g.user_role==='officer')?`<button class="small-btn upgrade-building-btn" data-type="${b.type}">⬆️</button>`:''}`;
    bDiv.appendChild(row);
  });
  bDiv.querySelectorAll('.upgrade-building-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const res = await callAPI('upgrade_building', { guild_id: currentGuildId, building_type: btn.getAttribute('data-type') });
      if (res.success) loadGuild(); else tg.showAlert(res.error);
    });
  });

  // Contribute
  document.querySelectorAll('.contribute-btn').forEach(btn => {
    btn.onclick = async () => {
      const res = await callAPI('contribute_guild', { amount: parseInt(btn.getAttribute('data-amount')) });
      if (res.success) { tg.showAlert('✅ Вклад внесён!'); loadGuild(); } else tg.showAlert(res.error);
    };
  });

  // Members
  const mDiv = document.getElementById('guildMembersList');
  mDiv.innerHTML = '';
  (g.members || []).forEach(m => {
    const roleIcons = { leader:'👑', officer:'⭐', veteran:'🛡️', member:'' };
    const row = document.createElement('div');
    row.className = 'member-row';
    const promoteBtn = (g.user_role==='leader' && m.role!=='leader')
      ? `<button class="promote-btn" data-target="${m.user_id}" data-role="${m.role==='officer'?'veteran':'officer'}">${m.role==='officer'?'⬇️':'⬆️'}</button>`
      : '';
    row.innerHTML = `<span>${roleIcons[m.role]||''} ${escHtml(m.username)} · 📊${m.rank}</span>${promoteBtn}`;
    mDiv.appendChild(row);
  });
  mDiv.querySelectorAll('.promote-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const res = await callAPI('promote_member', { leader_id: userId, target_id: parseInt(btn.getAttribute('data-target')), new_role: btn.getAttribute('data-role') });
      if (res.success) loadGuild(); else tg.showAlert(res.error);
    });
  });

  // Raid
  if (g.active_raid) {
    document.getElementById('activeRaid').style.display = 'block';
    document.getElementById('startRaidBtn').style.display = 'none';
    document.getElementById('raidBossName').textContent = g.active_raid.boss_name;
    document.getElementById('raidBossCurrentHp').textContent = g.active_raid.boss_current_hp;
    document.getElementById('raidBossMaxHp').textContent     = g.active_raid.boss_max_hp;
    document.getElementById('raidBossHpFill').style.width    = (g.active_raid.boss_current_hp / g.active_raid.boss_max_hp * 100) + '%';
  } else {
    document.getElementById('activeRaid').style.display = 'none';
    document.getElementById('startRaidBtn').style.display = (g.user_role==='leader'?'flex':'none');
  }
  document.getElementById('startRaidBtn').onclick = async () => {
    const res = await callAPI('start_guild_raid', { guild_id: currentGuildId, boss_level: 1 });
    if (res.success) loadGuild(); else tg.showAlert(res.error);
  };
  document.getElementById('attackRaidBoss').onclick = async () => {
    const res = await callAPI('attack_raid_boss', { raid_id: g.active_raid?.raid_id, damage: 1000 });
    if (res.success) { loadGuild(); if (res.raid_completed) tg.showAlert('🐉 Рейд завершён!'); } else tg.showAlert(res.error);
  };

  // Chat
  loadGuildChat();
  if (guildChatInterval) clearInterval(guildChatInterval);
  guildChatInterval = setInterval(loadGuildChat, 4000);

  document.getElementById('sendGuildMessage').onclick = sendGuildMessage;
  document.getElementById('guildMessageInput').onkeypress = e => { if (e.key==='Enter') sendGuildMessage(); };
  document.getElementById('leaveGuildBtn').onclick = async () => {
    if (confirm('Покинуть гильдию?')) {
      const res = await callAPI('leave_guild', {});
      if (res.success) { tg.showAlert('Вы покинули гильдию'); loadGuild(); } else tg.showAlert(res.error);
    }
  };
}

async function loadGuildChat() {
  if (!currentGuildId) return;
  const msgs = await callAPI('guild_chat', { guild_id: currentGuildId }, 'GET');
  const box  = document.getElementById('guildChatMessages');
  box.innerHTML = '';
  (msgs || []).forEach(m => {
    const d = document.createElement('div');
    d.className = 'chat-msg';
    d.innerHTML = `<b>${escHtml(m.username)}:</b> ${escHtml(m.message)}`;
    box.appendChild(d);
  });
  box.scrollTop = box.scrollHeight;
}

async function sendGuildMessage() {
  const inp = document.getElementById('guildMessageInput');
  const msg = inp.value.trim();
  if (!msg || !currentGuildId) return;
  await callAPI('guild_send_message', { guild_id: currentGuildId, username, message: msg });
  inp.value = '';
  loadGuildChat();
}

function bindNoGuildUI() {
  document.getElementById('createGuildBtn').onclick = () => document.getElementById('createGuildModal').style.display='flex';
  document.getElementById('closeCreateGuild').onclick = () => document.getElementById('createGuildModal').style.display='none';
  document.getElementById('confirmCreateGuild').onclick = createGuild;
  document.getElementById('searchGuildsBtn').onclick = searchGuilds;
}

async function createGuild() {
  const name = document.getElementById('newGuildName').value.trim();
  const emoji = document.getElementById('newGuildEmoji').value.trim() || '🏰';
  const desc  = document.getElementById('newGuildDescription').value.trim();
  if (!name) { tg.showAlert('Введите название'); return; }
  const res = await callAPI('create_guild', { name, emoji, description: desc });
  if (res.success) { document.getElementById('createGuildModal').style.display='none'; loadGuild(); }
  else tg.showAlert(res.error || 'Ошибка создания');
}

async function searchGuilds() {
  const q = document.getElementById('guildSearchInput').value;
  const guilds = await callAPI('search_guilds', { query: q }, 'GET');
  const div = document.getElementById('guildSearchResults');
  div.innerHTML = '';
  (guilds || []).forEach(g => {
    const item = document.createElement('div');
    item.className = 'guild-item';
    item.innerHTML = `<span>${g.emoji} <b>${escHtml(g.name)}</b> Ур.${g.level} · ⭐${g.war_points} · 👥${g.member_count}</span><button class="join-btn" data-id="${g.guild_id}">Вступить</button>`;
    div.appendChild(item);
  });
  div.querySelectorAll('.join-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const res = await callAPI('join_guild', { guild_id: btn.getAttribute('data-id') });
      if (res.success) { tg.showAlert('✅ Вы вступили!'); loadGuild(); } else tg.showAlert(res.error);
    });
  });
}

async function loadGuildLeaderboard() {
  const guilds = await callAPI('guild_leaderboard', {}, 'GET');
  const div = document.getElementById('guildLeaderboardList');
  div.innerHTML = '';
  (guilds || []).forEach((g, i) => {
    const item = document.createElement('div');
    item.className = 'lb-item-guild';
    item.textContent = `${i+1}. ${g.emoji} ${g.name} | Ур.${g.level} | ⭐${g.war_points} | 👥${g.member_count}`;
    div.appendChild(item);
  });
}

// ── Utils ──────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Boot ───────────────────────────────────
initApp();
