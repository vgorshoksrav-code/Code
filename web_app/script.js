/* ═══════════════════════════════════════════════════════════════
   ECHARIS v3 — script.js   Full client logic
   Matches: index.html (scene-based) + api.py + style.css
═══════════════════════════════════════════════════════════════ */
'use strict';

// ── Telegram WebApp ──────────────────────────────────────────────
const tg   = window.Telegram?.WebApp || {initDataUnsafe:{},expand:()=>{},ready:()=>{},showAlert:(m)=>alert(m),HapticFeedback:{impactOccurred:()=>{},notificationOccurred:()=>{}}};
tg.expand(); tg.ready();
const TGU  = tg.initDataUnsafe?.user;
let userId   = TGU?.id   || null;
let username = TGU?.username || TGU?.first_name || `guest_${Math.floor(Math.random()*9999)}`;

// ── Hero classes ─────────────────────────────────────────────────
const CLASSES = {
  warrior:   {emoji:'⚔️', name:'Воин',       skills:['Удар меча','Боевой щит','Рывок','Смерч','Клич ярости']},
  mage:      {emoji:'🧙', name:'Маг',        skills:['Огн. шар','Ледяная стена','Маг. связь','Молния','Метеор']},
  archer:    {emoji:'🏹', name:'Лучник',     skills:['Стрела','Дым. завеса','Ловушка','Залп','Орлиный глаз']},
  rogue:     {emoji:'🗡️', name:'Разбойник', skills:['Удар в спину','Уклон','Яд','Веер ножей','Тень']},
  paladin:   {emoji:'🛡️', name:'Паладин',   skills:['Святой удар','Щит веры','Лечение','Кара','Воскресение']},
  necromancer:{emoji:'💀',name:'Некромант',  skills:['Гнилой шип','Смерть.аура','Кровосос','Армия мёртвых','Коса']},
  druid:     {emoji:'🌿', name:'Друид',      skills:['Шипы','Регенерация','Корни','Призыв бури','Зов природы']},
};
const SKILL_ICONS = ['🔥','❄️','🌿','⚡','🌟'];
const SKILL_COSTS = [5,4,6,8,12];

// ── State ────────────────────────────────────────────────────────
let profile       = null;
let allSkins      = null;
let allPawns      = null;
let currentMatchId= null;
let battleActive  = false;
let bossActive    = false;
let currentGuild  = null;
let shopFilter    = 'all';
let guildChatIv   = null;
let searchIv      = null;
let searchSec     = 0;
let pollIv        = null;
let currentEnergy = 10;
let maxEnergy     = 30;
let myHp=100, oppHp=100;
let lang = localStorage.getItem('echaris_lang') || 'ru';
let tutStep = 0;
const TUT_STEPS = [
  {ico:'🌌',title:'Добро пожаловать в Эхарис!',text:'Мир вечных дуэлей душ. Сражайся с игроками и боссами, собирай скины и стань легендой!'},
  {ico:'⚔️',title:'Как сражаться',text:'Нажимай скиллы во время боя. Каждый тратит ⚡ энергию — она восстанавливается автоматически. Следи за таймером!'},
  {ico:'💎',title:'Осколки и прокачка',text:'Победы дают 💎 осколки. Трать их на улучшение скиллов. Скины покупаются за Telegram Stars ⭐.'},
  {ico:'🐾',title:'Пешки — фамильяры',text:'У каждого героя может быть фамильяр 🐾. Они дают бонусы к характеристикам и отображаются в бою!'},
  {ico:'🎁',title:'Ежедневный подарок',text:'Каждые 24 часа нажимай 🎁 вверху и получай бесплатные осколки, билеты и иногда редкие скины!'},
];

// ── API helper ───────────────────────────────────────────────────
async function api(endpoint, data={}, method='POST') {
  try {
    if (method==='GET') {
      const p = new URLSearchParams({...data});
      const r = await fetch(`/api/${endpoint}?${p}`);
      if (!r.ok) return {error:`HTTP ${r.status}`};
      return r.json();
    }
    const r = await fetch(`/api/${endpoint}`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({user_id:userId,...data})
    });
    if (!r.ok) return {error:`HTTP ${r.status}`};
    return r.json();
  } catch(e) { return {error:String(e)}; }
}

// ── Canvas particles ─────────────────────────────────────────────
const CVS = document.getElementById('bgCanvas');
const CTX = CVS.getContext('2d');
let parts = [];
function resizeCvs(){ CVS.width=innerWidth; CVS.height=innerHeight; }
window.addEventListener('resize', resizeCvs); resizeCvs();
class P { constructor(){this.reset();}
  reset(){this.x=Math.random()*CVS.width;this.y=Math.random()*CVS.height;
    this.s=Math.random()*1.4+.3;this.vx=(Math.random()-.5)*.35;this.vy=(Math.random()-.5)*.35;
    this.a=Math.random()*.2+.04;this.h=Math.random()<.5?50:270;}
  tick(){this.x+=this.vx;this.y+=this.vy;
    if(this.x<0||this.x>CVS.width||this.y<0||this.y>CVS.height)this.reset();}
  draw(){CTX.beginPath();CTX.arc(this.x,this.y,this.s,0,Math.PI*2);
    CTX.fillStyle=`hsla(${this.h},100%,70%,${this.a})`;CTX.fill();}
}
for(let i=0;i<100;i++) parts.push(new P());
(function loop(){CTX.clearRect(0,0,CVS.width,CVS.height);parts.forEach(p=>{p.tick();p.draw();});requestAnimationFrame(loop);})();

// ── Scene manager ────────────────────────────────────────────────
function showScene(id) {
  document.querySelectorAll('.scene').forEach(s=>{
    if(s.id===id){s.style.display='';s.style.opacity='1';}
    else{s.style.opacity='0';setTimeout(()=>{if(s.style.opacity==='0')s.style.display='none';},320);}
  });
}

// ── Splash ───────────────────────────────────────────────────────
function runSplash(cb) {
  const bar  = document.getElementById('splashBar');
  const hint = document.getElementById('splashHint');
  const msgs = ['Инициализация...','Загрузка мира...','Соединение с Эхарисом...','Готово!'];
  let pct=0, mi=0;
  const iv = setInterval(()=>{
    pct += Math.random()*14+4;
    bar.style.width = Math.min(pct,100)+'%';
    if(pct>25&&mi<1){hint.textContent=msgs[1];mi=1;}
    if(pct>55&&mi<2){hint.textContent=msgs[2];mi=2;}
    if(pct>85&&mi<3){hint.textContent=msgs[3];mi=3;}
    if(pct>=100){clearInterval(iv);setTimeout(cb,400);}
  },90);
}

// ── App init ─────────────────────────────────────────────────────
async function initApp() {
  runSplash(async ()=>{
    // Register / load profile
    if(userId){
      const reg = await api('register',{username});
      profile = await api('profile',{user_id:userId},'GET');
      if(profile){
        lang = profile.language||lang;
        updateTopBar();
        // Welcome bonus
        if(reg.welcome_bonus){
          document.getElementById('welcomeSkinLine').textContent =
            `${reg.welcome_bonus.skin_emoji} ${reg.welcome_bonus.skin_name} (${reg.welcome_bonus.hours}ч)`;
          openOv('ovWelcome');
        }
        // Daily gift pulse
        if(profile.gift_available) document.getElementById('btnGift').classList.add('pulse-once');
        // Events banner
        if(profile.active_events?.length){
          const ev = profile.active_events[0];
          const ban = document.getElementById('eventBanner');
          ban.textContent = `${ev.icon} ${ev.name} — x${ev.multiplier} до ${ev.ends_at?.split(' ')[0]}`;
          ban.style.display='block';
          // push pages down
          document.getElementById('pageScroll').style.top = '80px';
        }
      }
    }
    showScene('appScene');
    // Startapp param
    const sp = new URLSearchParams(location.search).get('startapp')||'duel';
    openTab(['duel','campaign','guild','hero','leaderboard','shop'].includes(sp)?sp:'duel');
    // Tutorial
    if(!localStorage.getItem('echaris_tut_done')) setTimeout(showTutorial,600);
    // Check incoming challenges
    pollChallenges();
    setInterval(pollChallenges, 8000);
  });
}

function updateTopBar(){
  if(!profile) return;
  const cls = profile.hero_class||'warrior';
  document.getElementById('tbAvatar').textContent  = CLASSES[cls]?.emoji||'🧙';
  document.getElementById('tbName').textContent    = profile.username||username;
  document.getElementById('tbRank').textContent    = profile.rank||1000;
  document.getElementById('tbShards').textContent  = profile.shards||0;
  document.getElementById('tbTickets').textContent = profile.daily_tickets||0;
}

// ── Tabs ─────────────────────────────────────────────────────────
function openTab(tab){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  const pg = document.getElementById(`pg-${tab}`);
  if(pg) pg.classList.add('active');
  if(tab==='hero')        loadHero();
  if(tab==='leaderboard') loadLeaderboard();
  if(tab==='shop')        loadShop();
  if(tab==='campaign')    loadCampaign();
  if(tab==='guild')       loadGuildTab();
  if(tab!=='guild' && guildChatIv){clearInterval(guildChatIv);guildChatIv=null;}
}
document.querySelectorAll('.nav-btn').forEach(b=>b.addEventListener('click',()=>openTab(b.dataset.tab)));

// ── Overlay helpers ───────────────────────────────────────────────
function openOv(id){ document.getElementById(id).style.display='flex'; }
function closeOv(id){ document.getElementById(id).style.display='none'; }
window.closeOv = closeOv;

// ── Haptic ───────────────────────────────────────────────────────
function haptic(type='light'){
  try{tg.HapticFeedback.impactOccurred(type);}catch(e){}
}
function hapticNotify(type='success'){
  try{tg.HapticFeedback.notificationOccurred(type);}catch(e){}
}

// ── Tutorial ─────────────────────────────────────────────────────
function showTutorial(){
  renderTutStep(0);
  openOv('ovTutorial');
}
function renderTutStep(i){
  tutStep=i;
  const s=TUT_STEPS[i];
  document.getElementById('tutIco').textContent  = s.ico;
  document.getElementById('tutTitle').textContent= s.title;
  document.getElementById('tutText').textContent = s.text;
  const dots=document.getElementById('tutDots');
  dots.innerHTML=TUT_STEPS.map((_,j)=>`<div class="dot${j===i?' on':''}"></div>`).join('');
  document.getElementById('btnTutNext').textContent = i<TUT_STEPS.length-1?'Далее →':'▶ Играть!';
}
document.getElementById('btnTutNext').addEventListener('click',()=>{
  if(tutStep<TUT_STEPS.length-1) renderTutStep(tutStep+1);
  else{ closeOv('ovTutorial'); localStorage.setItem('echaris_tut_done','1'); }
});

// ── Daily gift ────────────────────────────────────────────────────
document.getElementById('btnGift').addEventListener('click', async ()=>{
  if(!userId) return;
  const list = document.getElementById('giftRewardList');
  list.innerHTML='<div class="reward-item">⏳ Открываем...</div>';
  openOv('ovGift');
  const r = await api('daily_gift',{});
  if(r.success){
    list.innerHTML = r.rewards.map(rw=>`<div class="reward-item">${rw}</div>`).join('');
    document.getElementById('btnGift').classList.remove('pulse-once');
    profile = await api('profile',{user_id:userId},'GET');
    updateTopBar(); hapticNotify('success');
  } else {
    list.innerHTML=`<div class="reward-item" style="color:var(--muted)">${r.error||'Уже получен!'}</div>`;
  }
});
document.getElementById('btnGiftClaim').addEventListener('click',()=>closeOv('ovGift'));

// ── Promo code ─────────────────────────────────────────────────────
document.getElementById('btnPromo').addEventListener('click',()=>{ document.getElementById('promoInp').value=''; document.getElementById('promoMsg').textContent=''; document.getElementById('promoMsg').className='promo-msg'; openOv('ovPromo'); });
document.getElementById('btnPromoSubmit').addEventListener('click', async ()=>{
  const code = document.getElementById('promoInp').value.trim();
  if(!code) return;
  const r = await api('redeem_promo',{code});
  const msg = document.getElementById('promoMsg');
  if(r.success){ msg.className='promo-msg promo-ok'; msg.textContent='✅ '+r.message; hapticNotify('success');
    profile=await api('profile',{user_id:userId},'GET'); updateTopBar();
  } else { msg.className='promo-msg promo-err'; msg.textContent='❌ '+(r.error||'Ошибка'); hapticNotify('error'); }
});

// ── Language ───────────────────────────────────────────────────────
document.getElementById('btnLang').addEventListener('click', async ()=>{
  lang = lang==='ru'?'en':'ru';
  localStorage.setItem('echaris_lang',lang);
  document.getElementById('btnLang').textContent = lang==='ru'?'🇷🇺':'🇬🇧';
  if(userId) await api('set_language',{language:lang});
});

// ═══════════════════════════════════════════════════════════════════
//  DUEL LOBBY
// ═══════════════════════════════════════════════════════════════════
function renderLobby(){
  if(!profile) return;
  const cls = profile.hero_class||'warrior';
  document.getElementById('lobbyAvatar').textContent = CLASSES[cls]?.emoji||'🧙';
  document.getElementById('lobbyPawn').textContent   = profile.equipped_pawn?.emoji||'';
  document.getElementById('lobbyName').textContent   = profile.username||username;
  document.getElementById('lobbyRank').textContent   = profile.rank||1000;
  document.getElementById('dStatWins').textContent   = profile.wins||0;
  document.getElementById('dStatLosses').textContent = profile.losses||0;
  document.getElementById('dStatRank').textContent   = profile.rank||1000;
}

document.getElementById('btnFindDuel').addEventListener('click', startSearch);
document.getElementById('btnCancelSearch').addEventListener('click', cancelSearch);
document.getElementById('btnFindFriendDuel').addEventListener('click', ()=>{
  loadFriends(); openOv('ovFriends');
});

async function startSearch(){
  if(!userId){ tg.showAlert('Войдите через Telegram!'); return; }
  profile = await api('profile',{user_id:userId},'GET');
  if(profile && profile.daily_tickets<=0){ tg.showAlert('🎟️ Билеты закончились! Получи ежедневный подарок 🎁'); return; }
  haptic('medium');
  // Hide lobby, show search
  document.getElementById('btnFindDuel').style.display='none';
  document.getElementById('btnFindFriendDuel').style.display='none';
  document.getElementById('searchState').style.display='flex';
  document.getElementById('searchAiWarn').style.display='none';
  searchSec=0;
  updateSearchTimer();

  // initial attempt
  const res = await api('find_duel',{});
  if(res.match_id){ enterBattleScene(res.match_id, res.opponent); return; }
  if(res.status==='no_tickets'){ cancelSearch(); tg.showAlert('🎟️ Нет билетов!'); return; }

  // poll every 2s
  searchIv = setInterval(async ()=>{
    searchSec+=2;
    updateSearchTimer();
    if(searchSec>=20 && searchSec<25) document.getElementById('searchAiWarn').style.display='block';
    if(searchSec>=25){
      document.getElementById('aiCountdown').textContent='0';
    }
    const chk = await api('queue_status',{user_id:userId},'GET');
    if(chk.status==='found' && chk.match_id){
      clearInterval(searchIv); searchIv=null;
      enterBattleScene(chk.match_id, chk.opponent);
    }
  }, 2000);
}

function updateSearchTimer(){
  document.getElementById('searchTimer').textContent = searchSec+'с';
  if(searchSec<25) document.getElementById('aiCountdown').textContent = (25-searchSec)+'';
}

function cancelSearch(){
  if(searchIv){ clearInterval(searchIv); searchIv=null; }
  if(userId) api('end_duel',{match_id:currentMatchId||''});
  document.getElementById('btnFindDuel').style.display='';
  document.getElementById('btnFindFriendDuel').style.display='';
  document.getElementById('searchState').style.display='none';
}

// ═══════════════════════════════════════════════════════════════════
//  BATTLE SCENE — transition + full UI
// ═══════════════════════════════════════════════════════════════════
function enterBattleScene(matchId, opponent){
  cancelSearch(); // cleanup
  currentMatchId  = matchId;
  battleActive    = true;
  myHp=100; oppHp=100; currentEnergy=10;
  haptic('heavy');

  const myClass = profile?.hero_class||'warrior';
  const myEmoji = CLASSES[myClass]?.emoji||'🧙';
  const oppEmoji= opponent?.skin_emoji||opponent?.emoji||'👤';
  const myPawn  = profile?.equipped_pawn?.emoji||'';
  const oppPawn = opponent?.pawn_emoji||'';

  // VS intro
  document.getElementById('vsAvatarL').textContent = myEmoji;
  document.getElementById('vsNameL').textContent   = profile?.username||username;
  document.getElementById('vsAvatarR').textContent = oppEmoji;
  document.getElementById('vsNameR').textContent   = opponent?.username||'???';
  document.getElementById('vsIntro').style.display = 'flex';
  document.getElementById('battleUI').style.display= 'none';
  document.getElementById('battleResult').style.display='none';

  showScene('battleScene');

  // After 2s show battle UI
  setTimeout(()=>{
    document.getElementById('vsIntro').style.display='none';
    document.getElementById('battleUI').style.display='flex';

    // Populate fighters
    document.getElementById('bfAvatarMe').textContent  = myEmoji;
    document.getElementById('bfPawnMe').textContent    = myPawn;
    document.getElementById('bfNameMe').textContent    = profile?.username||username;
    document.getElementById('bfAvatarOpp').textContent = oppEmoji;
    document.getElementById('bfPawnOpp').textContent   = oppPawn;
    document.getElementById('bfNameOpp').textContent   = opponent?.username||'???';

    // Skill names from class
    const skills = CLASSES[myClass]?.skills||['Скилл 1','Скилл 2','Скилл 3','Скилл 4','Скилл 5'];
    document.querySelectorAll('#skillsPanel .skill-btn').forEach((btn,i)=>{
      btn.querySelector('.sb-nm').textContent  = skills[i]||'';
      btn.querySelector('.sb-ico').textContent = SKILL_ICONS[i];
      btn.querySelector('.sb-cost').textContent= SKILL_COSTS[i]+'⚡';
    });

    updateBattleUI(100,100,currentEnergy);
    startBattleTimer(30);
    clearBattleLog();
    addBattleLog(`⚔️ Бой начался! vs ${opponent?.username||'???'}`, '');

    // start poll
    if(pollIv) clearInterval(pollIv);
    pollIv = setInterval(pollBattle, 1200);
  }, 2000);
}

async function pollBattle(){
  if(!battleActive||!currentMatchId) return;
  const s = await api('duel_action',{match_id:currentMatchId,skill_index:null});
  if(!s) return;
  if(s.battle_end){ handleBattleEnd(s.winner_id, s.log); return; }
  if(s.player_hp!==undefined){
    updateBattleUI(s.player_hp, s.opponent_hp, s.player_energy);
    if(s.log) addBattleLog(s.log);
  }
}

async function useSkill(idx){
  if(!battleActive||!currentMatchId) return;
  haptic('light');
  // Visual feedback: disable all briefly
  document.querySelectorAll('#skillsPanel .skill-btn').forEach(b=>b.disabled=true);
  setTimeout(()=>document.querySelectorAll('#skillsPanel .skill-btn').forEach(b=>b.disabled=false), 700);

  const r = await api('duel_action',{match_id:currentMatchId,skill_index:idx});
  if(!r||r.error){ addBattleLog('❌ '+(r?.error||'Ошибка')); return; }
  if(r.battle_end){ handleBattleEnd(r.winner_id,r.log); return; }
  updateBattleUI(r.player_hp, r.opponent_hp, r.player_energy);
  if(r.log){
    addBattleLog(r.log);
    playHitAnimation(r.log);
  }
}

document.querySelectorAll('#skillsPanel .skill-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    if(battleActive) useSkill(parseInt(btn.dataset.si));
  });
});

function updateBattleUI(mhp, ohp, energy){
  myHp=Math.max(0,mhp); oppHp=Math.max(0,ohp); currentEnergy=energy;
  document.getElementById('bfHpMe').style.width   = myHp+'%';
  document.getElementById('bfHpOppVal').textContent= ohp;
  document.getElementById('bfHpMeVal').textContent = mhp;
  document.getElementById('bfHpOpp').style.width  = oppHp+'%';
  document.getElementById('enrgVal').textContent  = energy;
  document.getElementById('enrgFill').style.width = (energy/maxEnergy*100)+'%';
}

let bfTimerIv=null;
function startBattleTimer(sec){
  const el=document.getElementById('bfTimer');
  let left=sec; el.textContent=left; el.classList.remove('warning');
  if(bfTimerIv) clearInterval(bfTimerIv);
  bfTimerIv=setInterval(()=>{
    left--;
    el.textContent=left;
    if(left<=10) el.classList.add('warning');
    if(left<=0){ clearInterval(bfTimerIv); }
  },1000);
}

function handleBattleEnd(winnerId, log){
  if(!battleActive) return;
  battleActive=false;
  if(pollIv){clearInterval(pollIv);pollIv=null;}
  if(bfTimerIv){clearInterval(bfTimerIv);bfTimerIv=null;}

  const won = String(winnerId)===String(userId);
  hapticNotify(won?'success':'error');

  if(log) addBattleLog(log);

  // Short delay then show result
  setTimeout(async ()=>{
    document.getElementById('resultIcon').textContent  = won?'🏆':'💀';
    document.getElementById('resultTitle').textContent = won?'Победа!':'Поражение...';
    document.getElementById('resultRewards').innerHTML = won
      ? '<div>+15 💎 осколков</div><div>📈 Рейтинг повышен</div>'
      : '<div>+5 💎 осколков</div><div>📉 Рейтинг снижен</div>';
    document.getElementById('battleResult').style.display='flex';
    // Update profile
    profile = await api('profile',{user_id:userId},'GET');
    updateTopBar(); renderLobby();
  }, 600);
}

document.getElementById('resultCloseBtn').addEventListener('click',()=>{
  document.getElementById('battleResult').style.display='none';
  showScene('appScene');
  openTab('duel');
  currentMatchId=null;
});

// ── Battle animations ────────────────────────────────────────────
function playHitAnimation(log){
  const hitAnim = document.getElementById('bfHitAnim');
  const isHeal  = log.includes('восстановил')||log.includes('shield')||log.includes('щит');
  const isCrit  = log.includes('крит')||log.includes('crit');
  const isDmg   = log.includes('нанёс')||log.includes('урон');

  if(isDmg){
    // Shake enemy
    const oppEl = document.getElementById('bfAvatarOpp');
    oppEl.classList.remove('shake'); void oppEl.offsetWidth; oppEl.classList.add('shake');
    hitAnim.textContent = isCrit?'💥КРИТ!':'⚡';
    spawnDmgFloat(oppEl, extractNum(log), isCrit?'crit':'neg');
    // Flash bg
    flashBattleBg('#e74c3c');
  } else if(isHeal){
    const myEl = document.getElementById('bfAvatarMe');
    hitAnim.textContent = '💚+'+extractNum(log);
    spawnDmgFloat(myEl, '+'+extractNum(log), 'pos');
    flashBattleBg('#27ae60');
  } else {
    hitAnim.textContent = '🛡️';
  }
  setTimeout(()=>hitAnim.textContent='', 800);
}

function extractNum(str){ const m=str.match(/\d+/); return m?m[0]:'?'; }

function spawnDmgFloat(el, val, cls){
  const rect = el.getBoundingClientRect();
  const d = document.createElement('div');
  d.className = `dmg-float ${cls}`;
  d.textContent = cls==='neg'?'-'+val:val;
  d.style.left  = (rect.left+rect.width/2)+'px';
  d.style.top   = rect.top+'px';
  document.body.appendChild(d);
  setTimeout(()=>d.remove(), 800);
}

function flashBattleBg(color){
  const sc = document.getElementById('battleScene');
  sc.style.transition='background .1s';
  sc.style.background=color+'22';
  setTimeout(()=>{ sc.style.background=''; }, 200);
}

function addBattleLog(msg, cls=''){
  const log=document.getElementById('battleLog');
  const d=document.createElement('div');
  d.textContent=msg;
  if(msg.includes('нанёс')) d.classList.add('l-hit');
  else if(msg.includes('восстановил')) d.classList.add('l-heal');
  else if(msg.includes('щит')||msg.includes('shield')) d.classList.add('l-shield');
  else if(msg.includes('крит')) d.classList.add('l-crit');
  log.appendChild(d); log.scrollTop=log.scrollHeight;
}
function clearBattleLog(){ document.getElementById('battleLog').innerHTML=''; }

// ═══════════════════════════════════════════════════════════════════
//  BOSS BATTLE SCENE
// ═══════════════════════════════════════════════════════════════════
function enterBossScene(state){
  bossActive=true;
  document.getElementById('bossBigEmoji').textContent = state.boss_emoji||'👹';
  document.getElementById('bossTitle').textContent    = state.boss_name||'Босс';
  document.getElementById('bossHpMax').textContent    = state.boss_max_hp;
  document.getElementById('bossMyAvatar').textContent = CLASSES[profile?.hero_class||'warrior']?.emoji||'🧙';
  // skill names from class
  const skills = CLASSES[profile?.hero_class||'warrior']?.skills||[];
  document.querySelectorAll('#bossSkillsPanel .skill-btn').forEach((b,i)=>{
    b.querySelector('.sb-ico').textContent  = SKILL_ICONS[i];
    b.querySelector('.sb-cost').textContent = SKILL_COSTS[i]+'⚡';
  });
  document.getElementById('bossClaimBtn').style.display='none';
  document.getElementById('bossLog').innerHTML='';
  updateBossUI(state);
  showScene('bossScene');
}

function updateBossUI(state){
  const bpct=(state.boss_hp/state.boss_max_hp*100);
  const mpct=(state.player_hp/state.player_max_hp*100);
  document.getElementById('bossHpFill').style.width = bpct+'%';
  document.getElementById('bossHpCur').textContent  = state.boss_hp;
  document.getElementById('bossMyHpFill').style.width= mpct+'%';
  document.getElementById('bossMyHp').textContent   = state.player_hp;
  document.getElementById('bossMyEnrg').textContent = state.player_energy;
  if(state.log){
    const log=document.getElementById('bossLog');
    const d=document.createElement('div'); d.textContent=state.log;
    if(state.log.includes('нанёс')) d.classList.add('l-hit');
    else if(state.log.includes('восстановил')) d.classList.add('l-heal');
    else if(state.log.includes('крит')) d.classList.add('l-crit');
    log.appendChild(d); log.scrollTop=log.scrollHeight;
    // animate boss if player hit it
    if(state.log.includes('нанёс')){
      const be=document.getElementById('bossBigEmoji');
      be.style.animation='none'; void be.offsetWidth;
      be.style.animation='bossHit .25s ease'; setTimeout(()=>be.style.animation='bossBob 1.8s ease-in-out infinite',300);
      spawnBossDmgFloat('-'+extractNum(state.log),'neg');
    }
  }
  if(state.finished){
    bossActive=false;
    document.getElementById('bossClaimBtn').style.display = state.winner==='player'?'block':'none';
    if(state.winner!=='player'){
      setTimeout(()=>{ tg.showAlert('💀 Поражение! Попробуй снова.'); showScene('appScene'); openTab('campaign'); },1000);
    }
  }
}

function spawnBossDmgFloat(val,cls){
  const el=document.getElementById('bossBigEmoji');
  const rect=el.getBoundingClientRect();
  const d=document.createElement('div');
  d.className=`dmg-float ${cls}`; d.textContent=val;
  d.style.left=(rect.left+rect.width/2)+'px'; d.style.top=rect.top+'px';
  document.body.appendChild(d); setTimeout(()=>d.remove(),800);
}

document.querySelectorAll('#bossSkillsPanel .skill-btn').forEach(btn=>{
  btn.addEventListener('click',async()=>{
    if(!bossActive) return; haptic('light');
    document.querySelectorAll('#bossSkillsPanel .skill-btn').forEach(b=>b.disabled=true);
    setTimeout(()=>document.querySelectorAll('#bossSkillsPanel .skill-btn').forEach(b=>b.disabled=false),700);
    const r=await api('pve_action',{skill_index:parseInt(btn.dataset.bsi)});
    if(r&&!r.error) updateBossUI(r);
  });
});

document.getElementById('bossBackBtn').addEventListener('click',()=>{
  if(bossActive){ bossActive=false; api('end_duel',{}); }
  showScene('appScene'); openTab('campaign');
});

document.getElementById('bossClaimBtn').addEventListener('click',async()=>{
  const r=await api('pve_claim_rewards',{});
  if(r.success){
    hapticNotify('success');
    tg.showAlert(`🎉 Награды!\n💎 +${r.shards_earned} осколков${r.skin_reward?'\n🎁 Скин: '+r.skin_reward:''}`);
  }
  showScene('appScene'); openTab('campaign');
  profile=await api('profile',{user_id:userId},'GET'); updateTopBar();
});

// ═══════════════════════════════════════════════════════════════════
//  CAMPAIGN
// ═══════════════════════════════════════════════════════════════════
async function loadCampaign(){
  const data=await api('campaign_progress',{user_id:userId},'GET');
  if(!data||data.error) return;
  const wrap=document.getElementById('chaptersContainer'); wrap.innerHTML='';
  data.chapters.forEach(ch=>{
    const card=document.createElement('div');
    card.className='chapter-card'+(ch.completed?' done':'')+(!ch.unlocked?' locked':'');
    let bossesHtml=ch.bosses.map(b=>{
      const avail=b.available, done=b.defeated, locked=!avail&&!done;
      return `<div class="boss-item${done?' done':avail?' avail':''}">
        <div class="boss-ico">${done?'✅':locked?'🔒':b.emoji||'👹'}</div>
        <div class="boss-info">
          <div class="boss-nm">${esc(b.name)}</div>
          <div class="boss-st">❤️${b.hp} · ⚔️${b.damage}</div>
          ${b.mechanics?.length?`<div class="boss-mech">⚡ ${b.mechanics.join(', ')}</div>`:''}
          <div class="boss-rw">💎${b.rewards.shards}${b.rewards.stars>0?' · ⭐'+b.rewards.stars:''}${b.rewards.skin_id?' · 🎁Скин':''}</div>
          ${avail?`<button class="btn-start-boss" data-bid="${b.boss_id}">⚔️ Сразиться</button>`:''}
        </div>
      </div>`;
    }).join('');
    card.innerHTML=`<div class="ch-title">Гл.${ch.chapter}: ${esc(ch.name)} ${ch.completed?'✅':ch.unlocked?'🔓':'🔒'}</div>
      <div class="boss-list">${bossesHtml}</div>`;
    wrap.appendChild(card);
  });
  wrap.querySelectorAll('.btn-start-boss').forEach(b=>{
    b.addEventListener('click',async()=>{
      const bid=parseInt(b.dataset.bid);
      const r=await api('pve_start_battle',{boss_id:bid});
      if(r.success) enterBossScene(r.state);
      else tg.showAlert(r.error||'Ошибка');
    });
  });
}

// ═══════════════════════════════════════════════════════════════════
//  HERO PAGE
// ═══════════════════════════════════════════════════════════════════
async function loadHero(){
  profile=await api('profile',{user_id:userId},'GET');
  if(!profile||profile.error) return;
  const cls=profile.hero_class||'warrior';
  const clsInfo=CLASSES[cls]||{emoji:'🧙'};
  document.getElementById('heroAvatarBig').textContent  = clsInfo.emoji;
  document.getElementById('heroPawnDisplay').textContent= profile.equipped_pawn?.emoji||'';
  document.getElementById('hAtk').textContent = (profile.equipped_skin?.stat_bonus?.attack_pct||0)+'%';
  document.getElementById('hDef').textContent = (profile.equipped_skin?.stat_bonus?.defense_pct||0)+'%';
  document.getElementById('hNrg').textContent = (profile.equipped_skin?.stat_bonus?.energy_pct||0)+'%';
  document.getElementById('hRank').textContent= profile.rank;
  document.getElementById('hW').textContent   = profile.wins;
  document.getElementById('hL').textContent   = profile.losses;
  document.getElementById('hShards').textContent = profile.shards;
  updateTopBar();

  // Temp skin badge
  const tsb=document.getElementById('heroTempBadge');
  if(profile.temp_skin){ tsb.style.display='block'; tsb.textContent=`⏳ ${profile.temp_skin.name} до ${profile.temp_skin.expires_at?.split(' ')[0]}`; }
  else tsb.style.display='none';

  // Skill upgrades
  const skillNames=clsInfo.skills||['Скилл 1','Скилл 2','Скилл 3','Скилл 4','Скилл 5'];
  const div=document.getElementById('skillUpgDiv'); div.innerHTML='';
  profile.hero_levels.forEach((lv,i)=>{
    const cost=50*lv;
    const row=document.createElement('div'); row.className='skill-upg-row';
    row.innerHTML=`<div class="su-info">
      <div class="su-nm">${SKILL_ICONS[i]} ${esc(skillNames[i])}</div>
      <div class="su-sub">Уровень ${lv} · стоит ${cost} 💎</div>
    </div>
    <button class="btn-upg" data-idx="${i}" ${profile.shards<cost?'disabled':''}>⬆️</button>`;
    div.appendChild(row);
  });
  div.querySelectorAll('.btn-upg').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('upgrade_skill',{skill_index:parseInt(btn.dataset.idx)});
      if(r.success){ hapticNotify('success'); loadHero(); }
      else tg.showAlert(r.error||'Нет осколков');
    });
  });

  // Owned skins
  const sg=document.getElementById('mySkinsGrid'); sg.innerHTML='';
  (profile.owned_skins||[]).forEach(sk=>{
    const tile=document.createElement('div');
    tile.className='skin-tile'+(sk.equipped?' equipped-tile':'');
    tile.innerHTML=`<div class="st-emoji">${sk.emoji||'🧙'}</div>
      <div class="st-name">${esc(sk.name)}</div>
      <div class="st-rarity r-${sk.rarity}">${sk.rarity}</div>
      ${sk.equipped?'<div class="badge-eq">✅ Надет</div>':
        `<button class="btn-equip" data-sid="${sk.id}">Надеть</button>`}`;
    sg.appendChild(tile);
  });
  // temp skin tile
  if(profile.temp_skin){
    const tile=document.createElement('div');
    const eq=(profile.equipped_skin?.id===profile.temp_skin.id);
    tile.className='skin-tile'+(eq?' equipped-tile':'');
    tile.innerHTML=`<div class="st-emoji">${profile.temp_skin.emoji}</div>
      <div class="st-name">${esc(profile.temp_skin.name)}</div>
      <div class="st-rarity r-legendary">⏳ Временный</div>
      ${eq?'<div class="badge-eq">✅ Надет</div>':
        `<button class="btn-equip" data-sid="${profile.temp_skin.id}">Надеть</button>`}`;
    sg.appendChild(tile);
  }
  sg.querySelectorAll('.btn-equip').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      await api('equip_skin',{skin_id:parseInt(btn.dataset.sid)});
      haptic('light'); loadHero();
    });
  });

  // Owned pawns
  const pg=document.getElementById('myPawnsGrid'); pg.innerHTML='';
  (profile.owned_pawns||[]).forEach(pw=>{
    const tile=document.createElement('div');
    tile.className='skin-tile'+(pw.equipped?' equipped-tile':'');
    const bonus=parseBonusStr(pw.stat_bonus||'{}');
    tile.innerHTML=`<div class="st-emoji">${pw.emoji||'🐾'}</div>
      <div class="st-name">${esc(pw.name)}</div>
      <div class="st-rarity r-${pw.rarity}">${pw.rarity}</div>
      <div class="st-rarity" style="color:rgba(255,215,0,.6)">${bonus}</div>
      ${pw.equipped?'<div class="badge-eq">✅ Активен</div>':
        `<button class="btn-equip" data-pid="${pw.id}">Надеть</button>`}`;
    pg.appendChild(tile);
  });
  pg.querySelectorAll('.btn-equip').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      await api('equip_pawn',{pawn_id:parseInt(btn.dataset.pid)});
      haptic('light'); loadHero();
    });
  });
  // Unequip pawn button
  if((profile.owned_pawns||[]).some(p=>p.equipped)){
    const uBtn=document.createElement('button');
    uBtn.className='btn-ghost'; uBtn.textContent='🚫 Снять фамильяра'; uBtn.style.marginTop='8px';
    uBtn.addEventListener('click',async()=>{ await api('equip_pawn',{pawn_id:null}); loadHero(); });
    pg.appendChild(uBtn);
  }
}

document.getElementById('btnChangeClass').addEventListener('click',()=>{
  const grid=document.getElementById('classGrid'); grid.innerHTML='';
  Object.entries(CLASSES).forEach(([key,info])=>{
    const opt=document.createElement('div');
    opt.className='class-opt'+(profile?.hero_class===key?' sel':'');
    opt.dataset.cls=key;
    opt.innerHTML=`${info.emoji}<small>${info.name}</small>`;
    opt.addEventListener('click',async()=>{
      await api('set_class',{hero_class:key});
      haptic('medium'); closeOv('ovClassPick'); loadHero(); updateTopBar();
    });
    grid.appendChild(opt);
  });
  openOv('ovClassPick');
});

document.getElementById('btnBuyPawns').addEventListener('click', async ()=>{
  if(!allPawns) allPawns=await api('pawns_list',{},'GET');
  const grid=document.getElementById('pawnShopGrid'); grid.innerHTML='';
  const owned=new Set((profile?.owned_pawns||[]).map(p=>p.id));
  (allPawns||[]).forEach(pw=>{
    const tile=document.createElement('div');
    tile.className='skin-tile'+(owned.has(pw.id)?' equipped-tile':'');
    const bonus=parseBonusStr(pw.stat_bonus||'{}');
    tile.innerHTML=`<div class="st-emoji">${pw.emoji||'🐾'}</div>
      <div class="st-name">${esc(pw.name)}</div>
      <div class="st-rarity r-${pw.rarity}">${pw.rarity}</div>
      <div class="st-rarity" style="color:rgba(255,215,0,.6)">${bonus}</div>
      ${owned.has(pw.id)?'<div class="badge-eq">✅ Есть</div>':
        pw.price_shards>0?`<div style="font-size:12px;color:var(--gold)">💎 ${pw.price_shards}</div><button class="btn-equip" data-pid="${pw.id}" data-type="shards">Купить</button>`
        :`<div style="font-size:12px;color:var(--gold)">⭐ ${pw.price_stars}</div><button class="btn-equip" data-pid="${pw.id}" data-type="stars">Купить</button>`}`;
    grid.appendChild(tile);
  });
  grid.querySelectorAll('.btn-equip').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('buy_pawn',{pawn_id:parseInt(btn.dataset.pid)});
      if(r.success){ hapticNotify('success'); closeOv('ovPawnShop'); allPawns=null; loadHero(); }
      else tg.showAlert(r.error||'Ошибка');
    });
  });
  openOv('ovPawnShop');
});

function parseBonusStr(json){
  try{
    const b=JSON.parse(json);
    return Object.entries(b).map(([k,v])=>
      (k.replace('_pct',''))+':'+(v>0?'+':'')+v+'%').join(' · ');
  }catch{return '';}
}

// ═══════════════════════════════════════════════════════════════════
//  LEADERBOARD
// ═══════════════════════════════════════════════════════════════════
async function loadLeaderboard(){
  const data=await api('leaderboard',{},'GET');
  const list=document.getElementById('lbList'); list.innerHTML='';
  (data||[]).forEach((p,i)=>{
    const row=document.createElement('div');
    row.className='lb-row'+(String(p.user_id)===String(userId)?' me':'');
    const rc=i===0?'r1':i===1?'r2':i===2?'r3':'';
    const med=i===0?'🥇':i===1?'🥈':i===2?'🥉':(i+1);
    row.innerHTML=`<div class="lb-rank ${rc}">${med}</div>
      <div class="lb-emoji">${p.skin_emoji||'🧙'}</div>
      <div class="lb-info">
        <div class="lb-uname">${esc(p.username)}${p.is_vip?' 👑':''}</div>
        <div class="lb-meta">${esc(p.skin_name)}</div>
      </div>
      <div class="lb-score">
        <div class="lb-elo">${p.rank}</div>
        <div class="lb-w">⚔️ ${p.wins}</div>
      </div>`;
    list.appendChild(row);
  });
}

// ═══════════════════════════════════════════════════════════════════
//  SHOP
// ═══════════════════════════════════════════════════════════════════
async function loadShop(){
  if(!allSkins) allSkins=await api('skins_list',{user_id:userId},'GET');
  if(!profile)  profile=await api('profile',{user_id:userId},'GET');
  const owned=new Set((profile?.owned_skins||[]).map(s=>s.id));
  renderShopGrid(owned);
}
function renderShopGrid(owned){
  const grid=document.getElementById('shopGrid'); grid.innerHTML='';
  (allSkins||[]).forEach(sk=>{
    if(shopFilter!=='all'&&sk.rarity!==shopFilter) return;
    const isOwned=owned?.has(sk.id);
    const bonus=parseBonusStr(sk.stat_bonus||'{}');
    const tile=document.createElement('div');
    tile.className='shop-tile'+(isOwned?' owned':'');
    tile.innerHTML=`<div class="st-big-emoji">${sk.emoji||'🧙'}</div>
      <div class="st-name">${esc(sk.name)}</div>
      <div class="st-rarity r-${sk.rarity}">${sk.rarity}</div>
      <div class="st-desc">${esc(sk.description||'')}</div>
      ${bonus?`<div class="st-bonus">${bonus}</div>`:''}
      <div class="st-price">${sk.price_stars>0?'⭐ '+sk.price_stars+' Stars':'🆓 Бесплатно'}</div>
      ${isOwned?'<div class="owned-tag">✅ В коллекции</div>':
        `<button class="btn-buy" data-sid="${sk.id}" data-price="${sk.price_stars}" data-name="${esc(sk.name)}">Купить</button>`}`;
    grid.appendChild(tile);
  });
  grid.querySelectorAll('.btn-buy').forEach(btn=>{
    btn.addEventListener('click',()=>buySkin(parseInt(btn.dataset.sid),parseInt(btn.dataset.price),btn.dataset.name));
  });
}

document.querySelectorAll('.ftab').forEach(btn=>{
  btn.addEventListener('click',async()=>{
    document.querySelectorAll('.ftab').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    shopFilter=btn.dataset.r;
    if(!allSkins) allSkins=await api('skins_list',{user_id:userId},'GET');
    if(!profile) profile=await api('profile',{user_id:userId},'GET');
    renderShopGrid(new Set((profile?.owned_skins||[]).map(s=>s.id)));
  });
});

async function buySkin(sid,price,name){
  if(price===0){
    const r=await api('buy_skin',{skin_id:sid,confirm:true});
    if(r.success){ hapticNotify('success'); tg.showAlert(`✅ Скин "${name}" получен!`); allSkins=null; profile=null; loadShop(); }
    else tg.showAlert(r.error||'Ошибка'); return;
  }
  const r=await api('buy_skin',{skin_id:sid,confirm:false});
  if(r.need_invoice){
    tg.showAlert(`Для покупки "${name}" нужно ${price} ⭐ Telegram Stars.\n\nДля тестирования скин добавлен бесплатно!`);
    // Dev mode: confirm without payment
    const r2=await api('buy_skin',{skin_id:sid,confirm:true});
    if(r2.success){ allSkins=null; profile=null; loadShop(); }
  } else if(r.success){ allSkins=null; profile=null; loadShop(); }
  else tg.showAlert(r.error||'Ошибка');
}

// ═══════════════════════════════════════════════════════════════════
//  FRIENDS
// ═══════════════════════════════════════════════════════════════════
document.getElementById('btnFriends').addEventListener('click',()=>{ loadFriends(); openOv('ovFriends'); });

async function loadFriends(){
  if(!userId) return;
  const data=await api('friends',{user_id:userId},'GET');
  renderFriendsList(data?.friends||[], data?.incoming||[]);
}

function renderFriendsList(friends, incoming){
  // Incoming
  const inDiv=document.getElementById('friendIncoming');
  inDiv.innerHTML=incoming.length===0?'<div class="muted-text" style="padding:8px">Нет запросов</div>':'';
  incoming.forEach(req=>{
    const item=document.createElement('div'); item.className='friend-item';
    item.innerHTML=`<div class="fi-info">
      <div class="fi-name">${esc(req.username)}</div>
      <div class="fi-meta">⚔️ ${req.rank}</div>
    </div>
    <div class="fi-btns">
      <button class="btn-buy" data-rid="${req.req_id}" data-action="accept">✅</button>
      <button class="btn-ghost" data-rid="${req.req_id}" data-action="decline">❌</button>
    </div>`;
    inDiv.appendChild(item);
  });
  inDiv.querySelectorAll('[data-action]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      if(btn.dataset.action==='accept')
        await api('friend_accept',{requester_id:parseInt(btn.dataset.rid)});
      else
        await api('friend_decline',{requester_id:parseInt(btn.dataset.rid)});
      loadFriends();
    });
  });

  // Friends list
  const fDiv=document.getElementById('friendsList');
  fDiv.innerHTML=friends.length===0?'<div class="muted-text" style="padding:8px">Друзей пока нет</div>':'';
  friends.filter(f=>f.status==='accepted').forEach(f=>{
    const item=document.createElement('div'); item.className='friend-item';
    item.innerHTML=`<div class="fi-info">
      <div class="fi-name">${f.skin_emoji||'🧙'} ${esc(f.username)}</div>
      <div class="fi-meta">⚔️ ${f.rank}${f.is_vip?' 👑':''}</div>
    </div>
    <div class="fi-btns">
      <button class="chip-btn" data-fid="${f.friend_id}" data-action="pvp" title="Вызвать на дуэль">⚔️</button>
      <button class="chip-btn" data-fid="${f.friend_id}" data-action="pve" title="PvE вместе">🏰</button>
      <button class="btn-ghost" data-fid="${f.friend_id}" data-action="remove" title="Удалить">🗑️</button>
    </div>`;
    fDiv.appendChild(item);
  });
  fDiv.querySelectorAll('[data-action]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const fid=parseInt(btn.dataset.fid);
      if(btn.dataset.action==='remove'){
        await api('friend_remove',{friend_id:fid}); loadFriends();
      } else {
        // Challenge friend
        const r=await api('challenge_friend',{friend_id:fid,mode:btn.dataset.action});
        if(r.success){ tg.showAlert('✅ Вызов отправлен! Ожидайте принятия.'); closeOv('ovFriends'); startPollChallengeMatch(); }
        else tg.showAlert(r.error||'Ошибка');
      }
    });
  });
}

// User search
document.getElementById('btnFriendSearch').addEventListener('click', searchUsers);
document.getElementById('friendSearchInp').addEventListener('keydown',e=>{ if(e.key==='Enter') searchUsers(); });

async function searchUsers(){
  const q=document.getElementById('friendSearchInp').value.trim();
  if(!q) return;
  const rows=await api('search_user',{query:q,user_id:userId},'GET');
  const div=document.getElementById('friendSearchRes'); div.innerHTML='';
  (rows||[]).forEach(u=>{
    const item=document.createElement('div'); item.className='friend-item';
    item.innerHTML=`<div class="fi-info">
      <div class="fi-name">${esc(u.username)}</div>
      <div class="fi-meta">⚔️ ${u.rank}${u.is_vip?' 👑':''}</div>
    </div>
    <button class="chip-btn" data-uid="${u.user_id}">➕ Добавить</button>`;
    div.appendChild(item);
  });
  div.querySelectorAll('[data-uid]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('friend_request',{friend_id:parseInt(btn.dataset.uid)});
      if(r.success){ btn.textContent='✅ Отправлено'; btn.disabled=true; hapticNotify('success'); }
      else tg.showAlert(r.error||'Ошибка');
    });
  });
}

// Poll for incoming challenges
async function pollChallenges(){
  if(!userId) return;
  const challenges=await api('check_challenges',{user_id:userId},'GET');
  if(!challenges?.length){ document.getElementById('challengesList').style.display='none'; return; }
  document.getElementById('challengesList').style.display='block';
  const div=document.getElementById('challengesItems'); div.innerHTML='';
  challenges.forEach(ch=>{
    const item=document.createElement('div'); item.className='challenge-item';
    item.innerHTML=`<span>${esc(ch.challenger_name)} хочет ${ch.mode==='pve'?'PvE':'дуэль'}</span>
    <div class="chal-btns">
      <button class="btn-buy" data-cid="${ch.id}" data-action="accept">✅</button>
      <button class="btn-ghost" data-cid="${ch.id}" data-action="decline">❌</button>
    </div>`;
    div.appendChild(item);
  });
  div.querySelectorAll('[data-action]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      if(btn.dataset.action==='accept'){
        const r=await api('accept_challenge',{challenge_id:parseInt(btn.dataset.cid)});
        if(r.success){
          haptic('heavy');
          document.getElementById('challengesList').style.display='none';
          enterBattleScene(r.match_id, r.opp_for_challenged);
        }
      } else {
        await api('decline_challenge',{challenge_id:parseInt(btn.dataset.cid)});
        document.getElementById('challengesList').style.display='none';
      }
    });
  });
}

// Challenger polls for accepted match
let challengePollIv=null;
function startPollChallengeMatch(){
  if(challengePollIv) clearInterval(challengePollIv);
  let tries=0;
  challengePollIv=setInterval(async()=>{
    tries++;
    const r=await api('poll_challenge_match',{user_id:userId},'GET');
    if(r.status==='found'&&r.match_id){
      clearInterval(challengePollIv); challengePollIv=null;
      enterBattleScene(r.match_id,r.opponent);
    }
    if(tries>30){ clearInterval(challengePollIv); challengePollIv=null; tg.showAlert('Друг не принял вызов.'); }
  },2000);
}

// ═══════════════════════════════════════════════════════════════════
//  GUILD
// ═══════════════════════════════════════════════════════════════════
async function loadGuildTab(){
  const data=await api('my_guild',{user_id:userId},'GET');
  loadGuildLeaderboard();
  if(!data.has_guild){
    document.getElementById('guildNoMember').style.display='block';
    document.getElementById('guildMember').style.display='none';
    bindNoGuild();
    return;
  }
  document.getElementById('guildNoMember').style.display='none';
  document.getElementById('guildMember').style.display='block';
  const g=data.guild; currentGuild=g;
  document.getElementById('gEmoji').textContent = g.emoji||'🏰';
  document.getElementById('gName').textContent  = g.name;
  document.getElementById('gLvlBadge').textContent='Ур.'+g.level;
  document.getElementById('gDesc').textContent  = g.description||'';
  document.getElementById('gWarPts').textContent= g.war_points;
  document.getElementById('gExp').textContent   = g.experience;
  document.getElementById('gExpMax').textContent= g.exp_for_next||1000;
  document.getElementById('gMems').textContent  = (g.members||[]).length;

  // Quests
  renderGuildQuests(g.quests||[], g.guild_id);

  // Buildings
  const bd=document.getElementById('gBuildingsDiv'); bd.innerHTML='';
  (g.buildings||[]).forEach(b=>{
    const row=document.createElement('div'); row.className='building-row';
    const canUpg=g.user_role==='leader'||g.user_role==='officer';
    row.innerHTML=`<span>${esc(b.bonus?.name||b.type)} (Ур.${b.level}) — ${esc(b.bonus?.bonus||'')}</span>
      ${canUpg?`<button class="prm-btn upg-bld" data-type="${b.type}">⬆️</button>`:''}`;
    bd.appendChild(row);
  });
  bd.querySelectorAll('.upg-bld').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('upgrade_building',{guild_id:g.guild_id,building_type:btn.dataset.type});
      if(r.success) loadGuildTab(); else tg.showAlert(r.error);
    });
  });

  // Contribute
  document.querySelectorAll('.contrib').forEach(btn=>{
    btn.onclick=async()=>{
      const r=await api('contribute_guild',{amount:parseInt(btn.dataset.amount)});
      if(r.success){ tg.showAlert('✅ Вклад внесён!'); loadGuildTab(); } else tg.showAlert(r.error);
    };
  });

  // Members
  const md=document.getElementById('gMembersDiv'); md.innerHTML='';
  (g.members||[]).forEach(m=>{
    const icons={leader:'👑',officer:'⭐',veteran:'🛡️',member:''};
    const row=document.createElement('div'); row.className='member-row';
    const isLeader=g.user_role==='leader';
    row.innerHTML=`<span>${icons[m.role]||''} ${esc(m.username)} · ⚔️${m.rank||0}</span>
      ${isLeader&&m.role!=='leader'?`<button class="prm-btn" data-tid="${m.user_id}" data-role="${m.role==='officer'?'veteran':'officer'}">${m.role==='officer'?'⬇️':'⬆️'}</button>`:''}`;
    md.appendChild(row);
  });
  md.querySelectorAll('[data-tid]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      await api('promote_member',{leader_id:userId,target_id:parseInt(btn.dataset.tid),new_role:btn.dataset.role});
      loadGuildTab();
    });
  });

  // Raid
  if(g.active_raid){
    document.getElementById('gRaidActive').style.display='block';
    document.getElementById('raidStartBtn').style.display='none';
    document.getElementById('raidName').textContent  = g.active_raid.boss_name;
    document.getElementById('raidHpCur').textContent = g.active_raid.boss_current_hp;
    document.getElementById('raidHpMax').textContent = g.active_raid.boss_max_hp;
    document.getElementById('raidHpFill').style.width=(g.active_raid.boss_current_hp/g.active_raid.boss_max_hp*100)+'%';
  } else {
    document.getElementById('gRaidActive').style.display='none';
    document.getElementById('raidStartBtn').style.display=g.user_role==='leader'?'block':'none';
  }
  document.getElementById('raidStartBtn').onclick=async()=>{
    const r=await api('start_guild_raid',{guild_id:g.guild_id,boss_level:1});
    if(r.success) loadGuildTab(); else tg.showAlert(r.error);
  };
  document.getElementById('raidAttackBtn').onclick=async()=>{
    const r=await api('attack_raid_boss',{raid_id:g.active_raid?.raid_id,damage:1000});
    if(r.success){ haptic('medium'); loadGuildTab(); if(r.raid_completed) tg.showAlert('🐉 Рейд победили! Награды распределены.'); }
  };

  // Chat
  loadGuildChat(g.guild_id);
  if(guildChatIv) clearInterval(guildChatIv);
  guildChatIv=setInterval(()=>loadGuildChat(g.guild_id),4000);
  document.getElementById('gChatSend').onclick=()=>sendGuildMsg(g.guild_id);
  document.getElementById('gChatInp').onkeydown=e=>{ if(e.key==='Enter') sendGuildMsg(g.guild_id); };
  document.getElementById('gLeaveBtn').onclick=async()=>{
    const r=await api('leave_guild',{});
    if(r.success){ tg.showAlert('Вы покинули гильдию'); loadGuildTab(); } else tg.showAlert(r.error);
  };
}

function renderGuildQuests(quests, guildId){
  const div=document.getElementById('gQuestsDiv'); div.innerHTML='';
  const typeNames={win_battles:'Победить в боях',defeat_bosses:'Победить боссов',
                   spend_shards:'Потратить осколки',guild_members:'Участники гильдии',raid_damage:'Урон в рейде'};
  if(!quests.length){ div.innerHTML='<div class="muted-text" style="padding:8px">Квесты загружаются...</div>'; return; }
  quests.forEach(q=>{
    const row=document.createElement('div'); row.className='quest-row';
    const rw=JSON.parse(q.reward||'{}');
    const completed=q.completed;
    row.innerHTML=`<div class="quest-left">
      <div class="quest-nm">${typeNames[q.quest_type]||q.quest_type}</div>
      <div class="quest-sub">${q.progress}/${q.target} · 💎${rw.shards||0}</div>
    </div>
    ${completed?`<button class="btn-claim-q" data-qid="${q.id}">Забрать!</button>`:''}`;
    div.appendChild(row);
  });
  div.querySelectorAll('.btn-claim-q').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('claim_guild_quest',{quest_id:parseInt(btn.dataset.qid)});
      if(r.success){ tg.showAlert(`🏆 Награда получена! 💎 ${r.reward?.shards||0} осколков для всех!`); loadGuildTab(); }
    });
  });
}

async function loadGuildChat(guildId){
  const msgs=await api('guild_chat',{guild_id:guildId},'GET');
  const box=document.getElementById('gChatBox');
  box.innerHTML='';
  (msgs||[]).forEach(m=>{
    const d=document.createElement('div'); d.className='chat-msg';
    d.innerHTML=`<b>${esc(m.username)}:</b> ${esc(m.message)}`;
    box.appendChild(d);
  });
  box.scrollTop=box.scrollHeight;
}

async function sendGuildMsg(guildId){
  const inp=document.getElementById('gChatInp');
  const msg=inp.value.trim();
  if(!msg||!guildId) return;
  await api('guild_send_message',{guild_id:guildId,username,message:msg});
  inp.value='';
  loadGuildChat(guildId);
}

function bindNoGuild(){
  document.getElementById('gCreateBtn').onclick=()=>openOv('ovGuildCreate');
  document.getElementById('gSearchBtn').onclick=searchGuilds;
  document.getElementById('gSearchInp').onkeydown=e=>{ if(e.key==='Enter') searchGuilds(); };
  document.getElementById('btnGcConfirm').onclick=createGuild;
}

async function searchGuilds(){
  const q=document.getElementById('gSearchInp').value;
  const guilds=await api('search_guilds',{query:q},'GET');
  const div=document.getElementById('gSearchResults'); div.innerHTML='';
  (guilds||[]).forEach(g=>{
    const item=document.createElement('div');
    item.style.cssText='background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center';
    item.innerHTML=`<span>${g.emoji||'🏰'} <b>${esc(g.name)}</b> Ур.${g.level} · 👥${g.member_count}</span>
      <button class="btn-buy" data-gid="${g.guild_id}">Вступить</button>`;
    div.appendChild(item);
  });
  div.querySelectorAll('[data-gid]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const r=await api('join_guild',{guild_id:btn.dataset.gid});
      if(r.success){ tg.showAlert('✅ Вы вступили в гильдию!'); loadGuildTab(); } else tg.showAlert(r.error);
    });
  });
}

async function createGuild(){
  const name=document.getElementById('gcName').value.trim();
  const emoji=document.getElementById('gcEmoji').value.trim()||'🏰';
  const desc=document.getElementById('gcDesc').value.trim();
  if(!name){ tg.showAlert('Введите название'); return; }
  const r=await api('create_guild',{name,emoji,description:desc});
  if(r.success){ closeOv('ovGuildCreate'); loadGuildTab(); }
  else tg.showAlert(r.error||'Ошибка');
}

async function loadGuildLeaderboard(){
  const guilds=await api('guild_leaderboard',{},'GET');
  const div=document.getElementById('gLbDiv'); div.innerHTML='';
  (guilds||[]).forEach((g,i)=>{
    const row=document.createElement('div'); row.className='lb-guild-row';
    row.textContent=`${i+1}. ${g.emoji||'🏰'} ${g.name} | Ур.${g.level} | ⭐${g.war_points} | 👥${g.member_count}`;
    div.appendChild(row);
  });
}

// ═══════════════════════════════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════════════════════════════
function esc(str){ if(!str) return ''; return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ═══════════════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded',()=>{
  // Load profile for lobby render after page load
  if(userId){
    api('profile',{user_id:userId},'GET').then(p=>{
      if(p&&!p.error){ profile=p; updateTopBar(); renderLobby(); }
    });
  }
  initApp();
});
