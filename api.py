import json, uuid, random
from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import (get_user, update_user_field, get_db_connection,
                      create_or_update_user, add_skin_to_user)
from game_logic import (find_match, check_match_ready, active_matches,
                        update_elo, claim_chain_reward, get_skin_name,
                        pending_queue, PvPMatch, SKILL_BASE_DAMAGE)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── helpers ───────────────────────────────────────────────────────────────
def _skins_for_user(uid):
    conn = get_db_connection()
    rows = conn.execute("SELECT skin_id,equipped FROM user_skins WHERE user_id=?",(uid,)).fetchall()
    owned, equipped = [], None
    for r in rows:
        sk = conn.execute("SELECT id,name,rarity,stat_bonus,emoji,description FROM skins WHERE id=?",(r['skin_id'],)).fetchone()
        if sk:
            d = dict(sk); d['equipped'] = bool(r['equipped'])
            owned.append(d)
            if r['equipped']:
                equipped = {"id":sk['id'],"name":sk['name'],"emoji":sk['emoji'] or '🧙',
                            "stat_bonus":json.loads(sk['stat_bonus'] or '{}')}
    conn.close()
    return owned, equipped or {"id":4,"name":"Страж пустоты","emoji":"🧙","stat_bonus":{"defense_pct":1}}

def _pawns_for_user(uid):
    conn = get_db_connection()
    rows = conn.execute("SELECT pawn_id,equipped FROM user_pawns WHERE user_id=?",(uid,)).fetchall()
    owned = []
    equipped = None
    for r in rows:
        p = conn.execute("SELECT * FROM pawns WHERE id=?",(r['pawn_id'],)).fetchone()
        if p:
            d = dict(p); d['equipped'] = bool(r['equipped'])
            owned.append(d)
            if r['equipped']:
                equipped = d
    conn.close()
    return owned, equipped

def _check_temp_skin(user):
    if user and user['temp_skin_id'] and user['temp_skin_expires']:
        try:
            if datetime.utcnow() > datetime.strptime(user['temp_skin_expires'],'%Y-%m-%d %H:%M:%S'):
                update_user_field(user['user_id'],'temp_skin_id',0)
                update_user_field(user['user_id'],'temp_skin_expires',None)
        except: pass

@app.get("/health")
async def health(): return {"ok":True}

# ── register ──────────────────────────────────────────────────────────────
@app.post("/api/register")
async def register(data:dict):
    uid = data.get('user_id'); uname = data.get('username',f'user_{uid}')
    if not uid: raise HTTPException(400)
    is_new = create_or_update_user(uid,uname)
    user = get_user(uid)
    welcome = None
    if user and not user['welcome_bonus_claimed']:
        chosen = random.choice([7,8,10,11,13])
        expires = (datetime.utcnow()+timedelta(hours=72)).strftime('%Y-%m-%d %H:%M:%S')
        update_user_field(uid,'temp_skin_id',chosen)
        update_user_field(uid,'temp_skin_expires',expires)
        update_user_field(uid,'welcome_bonus_claimed',1)
        conn=get_db_connection()
        sk=conn.execute("SELECT name,emoji FROM skins WHERE id=?",(chosen,)).fetchone()
        conn.close()
        welcome={"skin_id":chosen,"skin_name":sk['name'] if sk else "?","skin_emoji":sk['emoji'] if sk else "🎁","hours":72}
    return {"success":True,"is_new":bool(is_new),"welcome_bonus":welcome}

# ── profile ───────────────────────────────────────────────────────────────
@app.get("/api/profile")
async def profile(user_id:int):
    user = get_user(user_id)
    if not user: raise HTTPException(404)
    _check_temp_skin(user); user = get_user(user_id)
    owned,equipped = _skins_for_user(user_id)
    p_owned,p_equipped = _pawns_for_user(user_id)
    gift_avail = (user['last_gift_date'] != str(date.today())) if user['last_gift_date'] else True
    temp = None
    if user['temp_skin_id']:
        conn=get_db_connection()
        sk=conn.execute("SELECT id,name,emoji FROM skins WHERE id=?",(user['temp_skin_id'],)).fetchone()
        conn.close()
        if sk: temp={"id":sk['id'],"name":sk['name'],"emoji":sk['emoji'],"expires_at":user['temp_skin_expires']}
    from promos import get_active_events
    events = get_active_events()
    return {
        "rank":user['rank'],"wins":user['wins'],"losses":user['losses'],
        "shards":user['shards'],"is_vip":bool(user['is_vip']),
        "daily_tickets":user['daily_tickets'],
        "hero_levels":json.loads(user['hero_levels']),
        "hero_class":user.get('hero_class','warrior'),
        "language":user.get('language','ru'),
        "equipped_skin":equipped,"owned_skins":owned,
        "owned_pawns":p_owned,"equipped_pawn":p_equipped,
        "temp_skin":temp,"gift_available":gift_avail,"username":user['username'],
        "active_events":[{"name":e['name'],"icon":e['icon'],"event_type":e['event_type'],
                           "multiplier":e['multiplier'],"ends_at":e['ends_at']} for e in events],
    }

# ── daily gift ────────────────────────────────────────────────────────────
@app.post("/api/daily_gift")
async def daily_gift(data:dict):
    uid = data.get('user_id')
    if not uid: raise HTTPException(400)
    user = get_user(uid)
    if not user: raise HTTPException(404)
    if user['last_gift_date'] == str(date.today()):
        return {"success":False,"error":"Подарок уже получен сегодня"}
    from promos import get_event_multiplier
    mult = get_event_multiplier('double_shards')
    sr = int(random.randint(30,100)*mult)
    tr = random.randint(1,3)
    update_user_field(uid,'shards',user['shards']+sr)
    update_user_field(uid,'daily_tickets',user['daily_tickets']+tr)
    update_user_field(uid,'last_gift_date',str(date.today()))
    rewards = [f"💎 +{sr} осколков{' (бонус события!)' if mult>1 else ''}",f"🎟️ +{tr} билетов"]
    skin_reward = None
    if random.random() < 0.12:
        sid = random.choice([5,6,9,12,18])
        conn=get_db_connection()
        have=conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?",(uid,sid)).fetchone()
        conn.close()
        if not have:
            add_skin_to_user(uid,sid)
            conn=get_db_connection(); sk=conn.execute("SELECT name FROM skins WHERE id=?",(sid,)).fetchone(); conn.close()
            skin_reward = sk['name'] if sk else "Скин"
            rewards.append(f"🎁 Редкий скин: {skin_reward}!")
    return {"success":True,"rewards":rewards,"shards_earned":sr,"tickets_earned":tr,"skin_reward":skin_reward}

# ── upgrade skill ─────────────────────────────────────────────────────────
@app.post("/api/upgrade_skill")
async def upgrade_skill(data:dict):
    uid=data.get('user_id'); idx=data.get('skill_index')
    if uid is None or idx is None: raise HTTPException(400)
    user=get_user(uid)
    if not user: raise HTTPException(404)
    levels=json.loads(user['hero_levels'])
    if not(0<=idx<5): raise HTTPException(400)
    lv=levels[idx]; cost=50*lv
    if lv>=20: return {"success":False,"error":"Максимальный уровень"}
    if user['shards']<cost: return {"success":False,"error":f"Нужно {cost} 💎"}
    levels[idx]+=1
    update_user_field(uid,'shards',user['shards']-cost)
    update_user_field(uid,'hero_levels',json.dumps(levels))
    return {"success":True,"new_level":levels[idx],"new_shards":user['shards']-cost}

# ── equip skin ────────────────────────────────────────────────────────────
@app.post("/api/equip_skin")
async def equip_skin(data:dict):
    uid=data.get('user_id'); sid=data.get('skin_id')
    if not uid or not sid: raise HTTPException(400)
    conn=get_db_connection()
    owns=conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?",(uid,sid)).fetchone()
    user=get_user(uid)
    if not owns and (not user or user['temp_skin_id']!=sid):
        conn.close(); return {"success":False,"error":"Скин не принадлежит вам"}
    conn.execute("UPDATE user_skins SET equipped=0 WHERE user_id=?",(uid,))
    if owns: conn.execute("UPDATE user_skins SET equipped=1 WHERE user_id=? AND skin_id=?",(uid,sid))
    conn.commit(); conn.close()
    update_user_field(uid,'equipped_skin_id',sid)
    return {"success":True}

# ── equip pawn ────────────────────────────────────────────────────────────
@app.post("/api/equip_pawn")
async def equip_pawn(data:dict):
    uid=data.get('user_id'); pid=data.get('pawn_id')
    if not uid: raise HTTPException(400)
    conn=get_db_connection()
    if pid:
        owns=conn.execute("SELECT 1 FROM user_pawns WHERE user_id=? AND pawn_id=?",(uid,pid)).fetchone()
        if not owns: conn.close(); return {"success":False,"error":"Пешка не принадлежит вам"}
        conn.execute("UPDATE user_pawns SET equipped=0 WHERE user_id=?",(uid,))
        conn.execute("UPDATE user_pawns SET equipped=1 WHERE user_id=? AND pawn_id=?",(uid,pid))
        update_user_field(uid,'equipped_pawn_id',pid)
    else:
        conn.execute("UPDATE user_pawns SET equipped=0 WHERE user_id=?",(uid,))
        update_user_field(uid,'equipped_pawn_id',0)
    conn.commit(); conn.close()
    return {"success":True}

# ── buy pawn ──────────────────────────────────────────────────────────────
@app.post("/api/buy_pawn")
async def buy_pawn(data:dict):
    uid=data.get('user_id'); pid=data.get('pawn_id')
    if not uid or not pid: raise HTTPException(400)
    conn=get_db_connection()
    pawn=conn.execute("SELECT * FROM pawns WHERE id=?",(pid,)).fetchone()
    if not pawn: conn.close(); return {"success":False,"error":"Не найдено"}
    have=conn.execute("SELECT 1 FROM user_pawns WHERE user_id=? AND pawn_id=?",(uid,pid)).fetchone()
    if have: conn.close(); return {"success":False,"error":"Уже есть"}
    user=get_user(uid)
    if pawn['price_shards']>0:
        if not user or user['shards']<pawn['price_shards']:
            conn.close(); return {"success":False,"error":f"Нужно {pawn['price_shards']} 💎"}
        update_user_field(uid,'shards',user['shards']-pawn['price_shards'])
    elif pawn['price_stars']>0:
        conn.close(); return {"success":False,"need_stars_pay":True,"price_stars":pawn['price_stars'],"pawn_name":pawn['name']}
    conn.execute("INSERT INTO user_pawns VALUES(?,?,0)",(uid,pid))
    conn.commit(); conn.close()
    return {"success":True}

@app.get("/api/pawns_list")
async def pawns_list(): 
    conn=get_db_connection(); ps=conn.execute("SELECT * FROM pawns").fetchall(); conn.close()
    return [dict(p) for p in ps]

# ── set class / language ──────────────────────────────────────────────────
@app.post("/api/set_class")
async def set_class(data:dict):
    valid=['warrior','mage','archer','rogue','paladin','necromancer','druid']
    hc=data.get('hero_class','warrior')
    if hc not in valid: return {"success":False}
    update_user_field(data['user_id'],'hero_class',hc); return {"success":True}

@app.post("/api/set_language")
async def set_language(data:dict):
    if data.get('language') not in ['ru','en']: return {"success":False}
    update_user_field(data['user_id'],'language',data['language']); return {"success":True}

# ── FRIENDS ───────────────────────────────────────────────────────────────
@app.get("/api/friends")
async def get_friends(user_id:int):
    conn=get_db_connection()
    # accepted friends
    rows=conn.execute('''SELECT f.friend_id,u.username,u.rank,u.is_vip,s.emoji skin_emoji,f.status
        FROM friends f JOIN users u ON f.friend_id=u.user_id
        LEFT JOIN skins s ON u.equipped_skin_id=s.id
        WHERE f.user_id=?''',(user_id,)).fetchall()
    # incoming requests
    inc=conn.execute('''SELECT f.user_id req_id,u.username,u.rank FROM friends f
        JOIN users u ON f.user_id=u.user_id
        WHERE f.friend_id=? AND f.status='pending' ''',(user_id,)).fetchall()
    conn.close()
    return {"friends":[dict(r) for r in rows],"incoming":[dict(r) for r in inc]}

@app.post("/api/friend_request")
async def friend_request(data:dict):
    uid=data.get('user_id'); fid=data.get('friend_id')
    if not uid or not fid or uid==fid: return {"success":False,"error":"Неверные данные"}
    target=get_user(fid)
    if not target: return {"success":False,"error":"Пользователь не найден"}
    conn=get_db_connection()
    exists=conn.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",(uid,fid)).fetchone()
    if exists: conn.close(); return {"success":False,"error":"Запрос уже отправлен"}
    conn.execute("INSERT OR IGNORE INTO friends(user_id,friend_id,status) VALUES(?,?,'pending')",(uid,fid))
    conn.commit(); conn.close()
    return {"success":True}

@app.post("/api/friend_accept")
async def friend_accept(data:dict):
    uid=data.get('user_id'); rid=data.get('requester_id')
    conn=get_db_connection()
    conn.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?",(rid,uid))
    conn.execute("INSERT OR IGNORE INTO friends(user_id,friend_id,status) VALUES(?,?,'accepted')",(uid,rid))
    conn.commit(); conn.close()
    return {"success":True}

@app.post("/api/friend_decline")
async def friend_decline(data:dict):
    uid=data.get('user_id'); rid=data.get('requester_id')
    conn=get_db_connection()
    conn.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?",(rid,uid))
    conn.commit(); conn.close()
    return {"success":True}

@app.post("/api/friend_remove")
async def friend_remove(data:dict):
    uid=data.get('user_id'); fid=data.get('friend_id')
    conn=get_db_connection()
    conn.execute("DELETE FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",(uid,fid,fid,uid))
    conn.commit(); conn.close()
    return {"success":True}

@app.get("/api/search_user")
async def search_user(query:str, user_id:int=0):
    conn=get_db_connection()
    rows=conn.execute("SELECT user_id,username,rank,is_vip FROM users WHERE username LIKE ? AND user_id!=? LIMIT 10",
                      (f'%{query}%',user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── PRIVATE CHALLENGES ────────────────────────────────────────────────────
@app.post("/api/challenge_friend")
async def challenge_friend(data:dict):
    uid=data.get('user_id'); fid=data.get('friend_id'); mode=data.get('mode','pvp')
    if not uid or not fid: raise HTTPException(400)
    conn=get_db_connection()
    # clean old challenges
    conn.execute("DELETE FROM friend_challenges WHERE challenger_id=? AND status='pending'",(uid,))
    conn.execute("INSERT INTO friend_challenges(challenger_id,challenged_id,mode) VALUES(?,?,?)",(uid,fid,mode))
    conn.commit(); conn.close()
    return {"success":True}

@app.get("/api/check_challenges")
async def check_challenges(user_id:int):
    conn=get_db_connection()
    ch=conn.execute('''SELECT fc.*,u.username challenger_name FROM friend_challenges fc
        JOIN users u ON fc.challenger_id=u.user_id
        WHERE fc.challenged_id=? AND fc.status='pending' ORDER BY fc.created_at DESC LIMIT 5''',(user_id,)).fetchall()
    conn.close()
    return [dict(c) for c in ch]

@app.post("/api/accept_challenge")
async def accept_challenge(data:dict):
    uid=data.get('user_id'); cid=data.get('challenge_id')
    conn=get_db_connection()
    ch=conn.execute("SELECT * FROM friend_challenges WHERE id=? AND challenged_id=? AND status='pending'",(cid,uid)).fetchone()
    if not ch: conn.close(); return {"success":False,"error":"Вызов не найден"}
    user1=get_user(ch['challenger_id']); user2=get_user(uid)
    if not user1 or not user2: conn.close(); return {"success":False,"error":"Игрок не найден"}
    mid=str(uuid.uuid4())
    match=PvPMatch(mid,ch['challenger_id'],uid,user1,user2)
    active_matches[mid]=match
    conn.execute("UPDATE friend_challenges SET status='accepted',match_id=? WHERE id=?",(mid,cid))
    conn.commit(); conn.close()
    opp1={"username":user2['username'],"rank":user2['rank'],"hero_levels":json.loads(user2['hero_levels'] or '[1,1,1,1,1]'),"skin_emoji":_get_skin_emoji(user2['equipped_skin_id'])}
    opp2={"username":user1['username'],"rank":user1['rank'],"hero_levels":json.loads(user1['hero_levels'] or '[1,1,1,1,1]'),"skin_emoji":_get_skin_emoji(user1['equipped_skin_id'])}
    return {"success":True,"match_id":mid,"opp_for_challenger":opp1,"opp_for_challenged":opp2}

@app.post("/api/decline_challenge")
async def decline_challenge(data:dict):
    conn=get_db_connection()
    conn.execute("UPDATE friend_challenges SET status='declined' WHERE id=?",(data.get('challenge_id'),))
    conn.commit(); conn.close()
    return {"success":True}

@app.get("/api/poll_challenge_match")
async def poll_challenge_match(user_id:int):
    """Challenger polls for accepted match."""
    conn=get_db_connection()
    ch=conn.execute("SELECT * FROM friend_challenges WHERE challenger_id=? AND status='accepted' ORDER BY id DESC LIMIT 1",(user_id,)).fetchone()
    conn.close()
    if not ch: return {"status":"waiting"}
    match=active_matches.get(ch['match_id'])
    if not match: return {"status":"waiting"}
    user2=get_user(ch['challenged_id'])
    opp={"username":user2['username'] if user2 else "?","rank":user2['rank'] if user2 else 1000,
         "hero_levels":json.loads(user2['hero_levels'] if user2 else '[1,1,1,1,1]'),
         "skin_emoji":_get_skin_emoji(user2['equipped_skin_id'] if user2 else 4)}
    return {"status":"found","match_id":ch['match_id'],"opponent":opp}

def _get_skin_emoji(sid):
    conn=get_db_connection(); sk=conn.execute("SELECT emoji FROM skins WHERE id=?",(sid,)).fetchone(); conn.close()
    return sk['emoji'] if sk else '🧙'

# ── MATCHMAKING ───────────────────────────────────────────────────────────
@app.post("/api/find_duel")
async def find_duel(data:dict):
    uid=data.get('user_id')
    if not uid: raise HTTPException(400)
    user=get_user(uid)
    if not user: raise HTTPException(404)
    if user['daily_tickets']<=0: return {"status":"no_tickets"}
    ready=check_match_ready(uid)
    if ready and "match_id" in ready:
        update_user_field(uid,'daily_tickets',user['daily_tickets']-1)
        if 'opponent' in ready:
            opp=ready['opponent']
            if 'skin_emoji' not in opp:
                opp['skin_emoji']=_get_skin_emoji(get_user(ready.get('opponent_id',0))['equipped_skin_id'] if get_user(ready.get('opponent_id',0)) else 4)
        return ready
    result=find_match(uid,user)
    if "match_id" in result:
        update_user_field(uid,'daily_tickets',user['daily_tickets']-1)
        opp=result.get('opponent',{})
        # enrich opponent
        match=active_matches.get(result['match_id'])
        if match:
            oid=match.player2_id if match.player1_id==uid else match.player1_id
            if oid!=-1:
                od=get_user(oid)
                if od: opp['skin_emoji']=_get_skin_emoji(od['equipped_skin_id'])
        return result
    return {"status":"waiting"}

@app.get("/api/queue_status")
async def queue_status(user_id:int):
    ready=check_match_ready(user_id)
    if ready and "match_id" in ready:
        user=get_user(user_id)
        if user and user['daily_tickets']>0:
            update_user_field(user_id,'daily_tickets',user['daily_tickets']-1)
        opp=ready.get('opponent',{})
        match=active_matches.get(ready['match_id'])
        if match:
            oid=match.player2_id if match.player1_id==user_id else match.player1_id
            if oid!=-1:
                od=get_user(oid)
                if od: opp['skin_emoji']=_get_skin_emoji(od['equipped_skin_id'])
        return {"status":"found",**ready}
    return {"status":"waiting" if user_id in pending_queue else "idle"}

# ── DUEL ACTION ───────────────────────────────────────────────────────────
@app.post("/api/duel_action")
async def duel_action(data:dict):
    mid=data.get('match_id'); uid=data.get('user_id'); skill=data.get('skill_index')
    if not mid or not uid: raise HTTPException(400)
    match=active_matches.get(mid)
    if not match: return {"error":"Матч не найден","battle_end":True,"winner_id":-1}
    match.regenerate_energy()
    p1=(match.player1_id==uid)
    if skill is None:
        return {"player_hp":match.player1_hp if p1 else match.player2_hp,
                "opponent_hp":match.player2_hp if p1 else match.player1_hp,
                "player_energy":match.player1_energy if p1 else match.player2_energy,"log":""}
    result=match.apply_skill(uid,skill)
    if "error" in result: return result
    if match.player2_id==-1 and match.player2_hp>0:
        br=match.bot_turn()
        if br and "error" not in br: result=br; match.regenerate_energy()
    if match.is_finished():
        return _finish_match(match,mid,result)
    return result

def _finish_match(match, mid, last_result):
    winner=match.get_winner(); loser=match.player1_id if winner==match.player2_id else match.player2_id
    conn=get_db_connection()
    conn.execute("INSERT INTO battles(player1_id,player2_id,winner_id,log) VALUES(?,?,?,?)",
                 (match.player1_id,match.player2_id,winner,json.dumps(match.log)))
    conn.commit(); conn.close()
    from promos import get_event_multiplier
    mult=get_event_multiplier('double_shards')
    if match.player1_id!=-1 and match.player2_id!=-1:
        update_elo(winner,loser)
    else:
        human=match.player1_id if match.player1_id!=-1 else match.player2_id
        hu=get_user(human)
        if hu:
            if human==winner:
                update_user_field(human,'shards',hu['shards']+int(15*mult))
                update_user_field(human,'wins',hu['wins']+1)
            else:
                update_user_field(human,'shards',hu['shards']+int(5*mult))
                update_user_field(human,'losses',hu['losses']+1)
    del active_matches[mid]
    return {"battle_end":True,"winner_id":winner,
            "player_hp":last_result.get("player_hp",0),
            "opponent_hp":last_result.get("opponent_hp",0),
            "log":last_result.get("log","")}

@app.post("/api/end_duel")
async def end_duel(data:dict):
    mid=data.get('match_id'); uid=data.get('user_id')
    if mid and mid in active_matches: del active_matches[mid]
    if uid and uid in pending_queue: del pending_queue[uid]
    return {"success":True}

# ── LEADERBOARD ───────────────────────────────────────────────────────────
@app.get("/api/leaderboard")
async def leaderboard():
    conn=get_db_connection()
    rows=conn.execute('''SELECT u.user_id,u.username,u.rank,u.wins,u.is_vip,
        s.name skin_name,s.emoji skin_emoji FROM users u
        LEFT JOIN skins s ON u.equipped_skin_id=s.id ORDER BY u.rank DESC LIMIT 20''').fetchall()
    conn.close()
    return [{"user_id":r['user_id'],"username":r['username'],"rank":r['rank'],
             "wins":r['wins'],"is_vip":bool(r['is_vip']),
             "skin_name":r['skin_name'] or 'Страж пустоты',
             "skin_emoji":r['skin_emoji'] or '🧙'} for r in rows]

# ── SHOP / BUY SKIN ───────────────────────────────────────────────────────
@app.post("/api/buy_skin")
async def buy_skin(data:dict):
    uid=data.get('user_id'); sid=data.get('skin_id'); confirm=data.get('confirm',False)
    if not uid or not sid: raise HTTPException(400)
    conn=get_db_connection()
    skin=conn.execute("SELECT id,name,price_stars FROM skins WHERE id=?",(sid,)).fetchone()
    if not skin: conn.close(); return {"success":False,"error":"Скин не найден"}
    have=conn.execute("SELECT 1 FROM user_skins WHERE user_id=? AND skin_id=?",(uid,sid)).fetchone()
    if have: conn.close(); return {"success":False,"error":"Уже куплен"}
    if skin['price_stars']==0:
        conn.execute("INSERT OR IGNORE INTO user_skins VALUES(?,?,0)",(uid,sid))
        conn.commit(); conn.close(); return {"success":True}
    if not confirm:
        conn.close()
        return {"success":False,"need_invoice":True,"price_stars":skin['price_stars'],"skin_name":skin['name'],"skin_id":sid}
    user=get_user(uid)
    conn.execute("INSERT OR IGNORE INTO user_skins VALUES(?,?,0)",(uid,sid))
    ns=(user['stars_spent'] if user else 0)+skin['price_stars']
    update_user_field(uid,'stars_spent',ns)
    if ns>=5000 and user and not user['is_vip']:
        update_user_field(uid,'is_vip',1)
        conn.execute("INSERT OR IGNORE INTO user_skins VALUES(?,?,0)",(uid,3))
    conn.commit(); conn.close(); return {"success":True}

@app.get("/api/skins_list")
async def skins_list(user_id:int=0):
    conn=get_db_connection()
    skins=conn.execute("SELECT id,name,rarity,price_stars,stat_bonus,emoji,description,hero_class FROM skins ORDER BY price_stars").fetchall()
    conn.close(); return [dict(s) for s in skins]

# ── PROMO ─────────────────────────────────────────────────────────────────
@app.post("/api/redeem_promo")
async def redeem_promo(data:dict):
    uid=data.get('user_id'); code=data.get('code','').strip()
    if not uid or not code: raise HTTPException(400)
    from promos import redeem_promo as rp; return rp(uid,code)

@app.get("/api/active_events")
async def active_events():
    from promos import get_active_events; return get_active_events()

# ── PvE CAMPAIGN ──────────────────────────────────────────────────────────
@app.get("/api/campaign_progress")
async def campaign_progress(user_id:int):
    from pve_campaign import get_campaign_progress,CAMPAIGN_BOSSES
    prog=get_campaign_progress(user_id)
    chapter_names=["Пробуждение","Теневые тропы","Ледяная цитадель","Огненные пещеры",
                   "Храм душ","Грозовой пик","Бездна","Цитадель времени","Сад эхарисов","Тронный зал"]
    boss_icons={"none":"👹","invisibility":"👻","freeze":"🧊","burning":"🔥",
                "vampirism":"🧛","paralysis":"⚡","insanity":"🌀","slow":"🐌","reflection":"🪞","all":"💀"}
    chapters=[]
    for n in range(1,11):
        bosses=[]
        for b in CAMPAIGN_BOSSES[n]:
            m=b.mechanics[0].value if b.mechanics else "none"
            bosses.append({"boss_id":b.boss_id,"name":b.name,"hp":b.max_hp,"damage":b.damage,
                           "emoji":boss_icons.get(m,"👹"),"mechanics":[x.value for x in b.mechanics],
                           "rewards":b.rewards,"defeated":b.boss_id in prog['completed_bosses'],
                           "available":b.boss_id==prog['current_boss_id']})
        chapters.append({"chapter":n,"name":chapter_names[n-1],
                         "completed":n in prog['completed_chapters'],
                         "unlocked":n<=prog['current_chapter'],"bosses":bosses})
    return {"progress":prog,"chapters":chapters}

@app.post("/api/pve_start_battle")
async def pve_start_battle(data:dict):
    import copy
    uid=data.get('user_id'); bid=data.get('boss_id')
    if not uid or not bid: raise HTTPException(400)
    from pve_campaign import get_campaign_progress,CAMPAIGN_BOSSES,PvEBattle,active_pve_battles
    prog=get_campaign_progress(uid)
    boss=next((b for ch in CAMPAIGN_BOSSES.values() for b in ch if b.boss_id==bid),None)
    if not boss: return {"success":False,"error":"Босс не найден"}
    if bid>prog['current_boss_id']: return {"success":False,"error":"Победите предыдущего босса"}
    battle=PvEBattle(uid,copy.deepcopy(boss))
    active_pve_battles[uid]=battle
    state=battle.get_state()
    state['boss_emoji']={'none':'👹','invisibility':'👻','freeze':'🧊','burning':'🔥',
                          'vampirism':'🧛','paralysis':'⚡','insanity':'🌀','slow':'🐌','reflection':'🪞','all':'💀'}.get(
                              boss.mechanics[0].value if boss.mechanics else 'none','👹')
    return {"success":True,"state":state}

@app.post("/api/pve_action")
async def pve_action(data:dict):
    uid=data.get('user_id'); skill=data.get('skill_index')
    if not uid or skill is None: raise HTTPException(400)
    from pve_campaign import active_pve_battles
    battle=active_pve_battles.get(uid)
    if not battle: raise HTTPException(404)
    user=get_user(uid)
    if not user: raise HTTPException(404)
    conn=get_db_connection()
    sk=conn.execute("SELECT stat_bonus FROM skins WHERE id=?",(user['equipped_skin_id'],)).fetchone()
    conn.close()
    stats=json.loads(sk['stat_bonus'] if sk and sk['stat_bonus'] else '{}')
    return battle.player_attack(skill,SKILL_BASE_DAMAGE[skill],stats,json.loads(user['hero_levels']))

@app.post("/api/pve_claim_rewards")
async def pve_claim_rewards(data:dict):
    uid=data.get('user_id')
    if not uid: raise HTTPException(400)
    from pve_campaign import active_pve_battles,claim_boss_rewards,update_campaign_progress
    battle=active_pve_battles.get(uid)
    if not battle or not battle.finished or battle.winner!="player":
        return {"success":False,"error":"Нет наград"}
    from promos import get_event_multiplier
    rewards=dict(battle.boss.rewards)
    rewards['shards']=int(rewards.get('shards',0)*get_event_multiplier('double_shards'))
    res=claim_boss_rewards(uid,rewards)
    if res['success']:
        update_campaign_progress(uid,battle.boss.boss_id,battle.boss.chapter)
        del active_pve_battles[uid]
    return res

# ── GUILDS ────────────────────────────────────────────────────────────────
@app.post("/api/create_guild")
async def create_guild(data:dict):
    from guilds import create_guild as cg
    return cg(data.get('name'),data.get('emoji','🏰'),data.get('description',''),data.get('user_id'))

@app.get("/api/guild_info")
async def guild_info(guild_id:str,user_id:int):
    from guilds import get_guild_info
    info=get_guild_info(guild_id,user_id)
    if not info: raise HTTPException(404)
    return info

@app.post("/api/join_guild")
async def join_guild(data:dict):
    from guilds import join_guild as jg; return jg(data.get('guild_id'),data.get('user_id'))

@app.post("/api/leave_guild")
async def leave_guild(data:dict):
    from guilds import leave_guild as lg; return lg(data.get('user_id'))

@app.post("/api/promote_member")
async def promote_member(data:dict):
    from guilds import promote_member as pm
    return pm(data.get('leader_id'),data.get('target_id'),data.get('new_role'))

@app.post("/api/contribute_guild")
async def contribute_guild(data:dict):
    from guilds import contribute_to_guild; return contribute_to_guild(data.get('user_id'),data.get('amount',10))

@app.post("/api/upgrade_building")
async def upgrade_building(data:dict):
    from guilds import upgrade_building as ub
    return ub(data.get('guild_id'),data.get('building_type'),data.get('user_id'))

@app.get("/api/guild_chat")
async def guild_chat(guild_id:str):
    from guilds import get_guild_messages; return get_guild_messages(guild_id)

@app.post("/api/guild_send_message")
async def guild_send_msg(data:dict):
    from guilds import send_guild_message as sgm
    return sgm(data.get('guild_id'),data.get('user_id'),data.get('username'),data.get('message'))

@app.get("/api/search_guilds")
async def search_guilds(query:str=""):
    from guilds import search_guilds as sg; return sg(query)

@app.get("/api/guild_leaderboard")
async def guild_leaderboard():
    from guilds import get_guild_leaderboard; return get_guild_leaderboard()

@app.post("/api/start_guild_raid")
async def start_guild_raid(data:dict):
    from guilds import start_guild_raid as sgr; return sgr(data.get('guild_id'),data.get('boss_level',1))

@app.post("/api/attack_raid_boss")
async def attack_raid_boss(data:dict):
    from guilds import attack_raid_boss as arb
    res=arb(data.get('raid_id'),data.get('user_id'),data.get('damage',0))
    if res.get('success'):
        conn=get_db_connection()
        m=conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?",(data.get('user_id'),)).fetchone()
        conn.close()
        if m:
            from promos import update_guild_quest_progress
            update_guild_quest_progress(m['guild_id'],'raid_damage',data.get('damage',0))
    return res

@app.get("/api/my_guild")
async def my_guild(user_id:int):
    conn=get_db_connection()
    m=conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?",(user_id,)).fetchone()
    conn.close()
    if not m: return {"has_guild":False}
    from guilds import get_guild_info; info=get_guild_info(m['guild_id'],user_id)
    from promos import get_guild_quests,generate_guild_quests
    generate_guild_quests(m['guild_id'])
    if info: info['quests']=get_guild_quests(m['guild_id'])
    return {"has_guild":True,"guild":info}

@app.post("/api/claim_guild_quest")
async def claim_guild_quest(data:dict):
    from promos import claim_guild_quest as cq
    uid=data.get('user_id')
    conn=get_db_connection(); m=conn.execute("SELECT guild_id FROM guild_members WHERE user_id=?",(uid,)).fetchone(); conn.close()
    if not m: return {"success":False,"error":"Не в гильдии"}
    return cq(m['guild_id'],data.get('quest_id'),uid)

@app.post("/api/claim_referral_reward")
async def claim_referral(data:dict):
    uid=data.get('user_id'); ruid=data.get('referred_user_id')
    if not uid or not ruid: raise HTTPException(400)
    result=claim_chain_reward(ruid,uid)
    return {"success":result=="success","error":result if result!="success" else None}

@app.post("/api/use_ticket")
async def use_ticket(data:dict):
    uid=data.get('user_id')
    if not uid: raise HTTPException(400)
    user=get_user(uid)
    if not user: raise HTTPException(404)
    if user['daily_tickets']>0:
        update_user_field(uid,'daily_tickets',user['daily_tickets']-1)
        return {"success":True,"remaining":user['daily_tickets']-1}
    return {"success":False,"error":"Нет билетов"}

app.mount("/",StaticFiles(directory="web_app",html=True),name="static")
