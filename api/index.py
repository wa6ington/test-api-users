import os, uuid, json as _json
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext

try:
    import psycopg2, psycopg2.extras
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-for-testing-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
POSTGRES_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")

app = FastAPI(title="QA Practice API", version="3.0.0",
    description="REST API для практики QA. Токен живёт 30 дней. Тестовые аккаунты: admin/admin123, tester/tester123")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def hash_password(p): return pwd_context.hash(p)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
def new_id(): return str(uuid.uuid4())
def now(): return datetime.utcnow().isoformat()
def create_token(data):
    d = data.copy(); d["exp"] = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode(d, SECRET_KEY, algorithm=ALGORITHM)

# ── DB ─────────────────────────────────────────────────────────────────────────
def get_conn():
    if not DB_AVAILABLE or not POSTGRES_URL: return None
    try: return psycopg2.connect(POSTGRES_URL, sslmode="require")
    except: return None

def use_pg():
    c = get_conn()
    if c: c.close(); return True
    return False

def db_q(sql, params=(), one=False):
    c = get_conn()
    if not c: return None if one else []
    try:
        cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        r = cur.fetchone() if one else cur.fetchall()
        c.close()
        return dict(r) if (one and r) else ([dict(x) for x in r] if r else (None if one else []))
    except Exception as e: c.close(); print(e); return None if one else []

def db_x(sql, params=()):
    c = get_conn()
    if not c: return False
    try:
        cur = c.cursor(); cur.execute(sql, params); c.commit(); c.close(); return True
    except Exception as e: c.rollback(); c.close(); print(e); return False

# ── Memory fallback ────────────────────────────────────────────────────────────
_u={}; _p={}; _po={}; _co={}; _t={}; _pay={}; _seeded=False

def seed():
    global _seeded
    if _seeded: return
    _seeded=True
    aid,uid=new_id(),new_id()
    _u[aid]={"id":aid,"username":"admin","email":"admin@test.com","password_hash":hash_password("admin123"),"role":"admin","created_at":now()}
    _u[uid]={"id":uid,"username":"tester","email":"tester@test.com","password_hash":hash_password("tester123"),"role":"user","created_at":now()}
    for n,c,pr,s in [("iPhone 15","Electronics",999.99,50),("Samsung TV","Electronics",599.99,20),("Nike Air Max","Shoes",149.99,100),("Python Book","Books",39.99,200)]:
        i=new_id(); _p[i]={"id":i,"name":n,"category":c,"price":pr,"stock":s,"description":f"Test: {n}","created_by":aid,"created_at":now()}
    for ti,bo in [("How to test REST API","REST API testing is essential..."),("Postman tips","Useful Postman features...")]:
        i=new_id(); _po[i]={"id":i,"title":ti,"body":bo,"author_id":aid,"tags":["qa","testing"],"created_at":now(),"updated_at":now()}
        ci=new_id(); _co[ci]={"id":ci,"post_id":i,"body":"Great post!","author_id":uid,"created_at":now()}
    for ti,pr,st in [("Write test cases","high","in_progress"),("Test endpoints","high","todo"),("Performance testing","low","todo")]:
        i=new_id(); _t[i]={"id":i,"title":ti,"description":f"Task: {ti}","priority":pr,"status":st,"assigned_to":uid,"created_by":aid,"created_at":now(),"due_date":"2026-12-31"}
    for amt,desc in [(100.0,"Course payment"),(50.0,"Book purchase")]:
        i=new_id(); _pay[i]={"id":i,"from_user_id":uid,"to_user_id":aid,"amount":amt,"currency":"USD","status":"completed","description":desc,"created_at":now()}

def init_pg():
    c = get_conn()
    if not c: seed(); return
    try:
        cur=c.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT DEFAULT 'user',created_at TEXT);
        CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT,price REAL,stock INT DEFAULT 0,description TEXT,created_by TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT,author_id TEXT,tags TEXT DEFAULT '[]',created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,post_id TEXT,body TEXT,author_id TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT,priority TEXT DEFAULT 'medium',status TEXT DEFAULT 'todo',assigned_to TEXT,created_by TEXT,created_at TEXT,due_date TEXT);
        CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,from_user_id TEXT,to_user_id TEXT,amount REAL,currency TEXT DEFAULT 'USD',status TEXT DEFAULT 'completed',description TEXT,created_at TEXT);
        """)
        cur.execute("SELECT COUNT(*) FROM users"); count=cur.fetchone()[0]
        if count==0:
            aid,uid=new_id(),new_id()
            cur.execute("INSERT INTO users VALUES(%s,%s,%s,%s,%s,%s)",(aid,"admin","admin@test.com",hash_password("admin123"),"admin",now()))
            cur.execute("INSERT INTO users VALUES(%s,%s,%s,%s,%s,%s)",(uid,"tester","tester@test.com",hash_password("tester123"),"user",now()))
            for n,cat,pr,st in [("iPhone 15","Electronics",999.99,50),("Samsung TV","Electronics",599.99,20),("Nike Air Max","Shoes",149.99,100),("Python Book","Books",39.99,200),("Coffee Maker","Kitchen",79.99,35)]:
                cur.execute("INSERT INTO products VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(new_id(),n,cat,pr,st,f"Test: {n}",aid,now()))
            for ti,bo in [("How to test REST API","REST API testing is essential for QA engineers..."),("Postman tips","Here are useful Postman features..."),("JWT explained","JSON Web Tokens are widely used...")]:
                pid=new_id()
                cur.execute("INSERT INTO posts VALUES(%s,%s,%s,%s,%s,%s,%s)",(pid,ti,bo,aid,'["qa","testing"]',now(),now()))
                cur.execute("INSERT INTO comments VALUES(%s,%s,%s,%s,%s)",(new_id(),pid,"Great post!",uid,now()))
            for ti,pr,st in [("Write test cases","high","in_progress"),("Test endpoints","high","todo"),("Performance testing","low","todo")]:
                cur.execute("INSERT INTO tasks VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(new_id(),ti,f"Task: {ti}",pr,st,uid,aid,now(),"2026-12-31"))
            for amt,desc in [(100.0,"Course payment"),(50.0,"Book purchase")]:
                cur.execute("INSERT INTO payments VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(new_id(),uid,aid,amt,"USD","completed",desc,now()))
        c.commit()
    except Exception as e: c.rollback(); print(f"init_pg error: {e}")
    finally: c.close()

init_pg()

# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_user(u): return {"id":u["id"],"username":u["username"],"email":u["email"],"role":u["role"],"created_at":u["created_at"]}
def parse_tags(t):
    if isinstance(t,list): return t
    try: return _json.loads(t)
    except: return []

def get_current_user(token: str=Depends(oauth2_scheme)):
    exc=HTTPException(401,"Invalid or expired token",headers={"WWW-Authenticate":"Bearer"})
    try:
        pl=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM]); uid=pl.get("sub")
        if not uid: raise exc
    except JWTError: raise exc
    u=db_q("SELECT * FROM users WHERE id=%s",(uid,),one=True) if use_pg() else (seed() or _u.get(uid))
    if not u: raise exc
    return u

# ── Schemas ────────────────────────────────────────────────────────────────────
class RegReq(BaseModel): username:str; email:str; password:str; role:Optional[str]="user"
class UpdUser(BaseModel): username:Optional[str]=None; email:Optional[str]=None; role:Optional[str]=None
class ProdCreate(BaseModel): name:str; category:str; price:float; stock:int=0; description:Optional[str]=None
class ProdUpdate(BaseModel): name:Optional[str]=None; category:Optional[str]=None; price:Optional[float]=None; stock:Optional[int]=None; description:Optional[str]=None
class PostCreate(BaseModel): title:str; body:str; tags:Optional[List[str]]=[]
class PostUpdate(BaseModel): title:Optional[str]=None; body:Optional[str]=None; tags:Optional[List[str]]=None
class CommentCreate(BaseModel): body:str
class CommentUpdate(BaseModel): body:str
class TaskCreate(BaseModel): title:str; description:Optional[str]=None; priority:Optional[str]="medium"; status:Optional[str]="todo"; assigned_to:Optional[str]=None; due_date:Optional[str]=None
class TaskUpdate(BaseModel): title:Optional[str]=None; description:Optional[str]=None; priority:Optional[str]=None; status:Optional[str]=None; assigned_to:Optional[str]=None; due_date:Optional[str]=None
class PayCreate(BaseModel): to_user_id:str; amount:float; currency:Optional[str]="USD"; description:Optional[str]=None

# ══ HEALTH ════════════════════════════════════════════════════════════════════
@app.get("/",tags=["Health"])
def root(): return {"status":"ok","message":"QA Practice API v3.0","db":"postgres" if use_pg() else "memory","token_lifetime":"30 days","docs":"/docs"}

@app.get("/health",tags=["Health"])
def health():
    pg=use_pg()
    if pg:
        counts={k:(db_q(f"SELECT COUNT(*) as c FROM {k}",one=True) or {}).get("c",0) for k in ["users","products","posts","comments","tasks","payments"]}
    else:
        seed(); counts={"users":len(_u),"products":len(_p),"posts":len(_po),"comments":len(_co),"tasks":len(_t),"payments":len(_pay)}
    return {"status":"ok","db":"postgres" if pg else "memory","counts":counts}

# ══ AUTH ══════════════════════════════════════════════════════════════════════
@app.post("/auth/register",status_code=201,tags=["Auth"])
def register(b:RegReq):
    if use_pg():
        if db_q("SELECT id FROM users WHERE email=%s",(b.email,),one=True): raise HTTPException(400,"Email already registered")
        if db_q("SELECT id FROM users WHERE username=%s",(b.username,),one=True): raise HTTPException(400,"Username already taken")
        uid=new_id(); db_x("INSERT INTO users VALUES(%s,%s,%s,%s,%s,%s)",(uid,b.username,b.email,hash_password(b.password),b.role or "user",now()))
        return fmt_user(db_q("SELECT * FROM users WHERE id=%s",(uid,),one=True))
    else:
        seed()
        for u in _u.values():
            if u["email"]==b.email: raise HTTPException(400,"Email already registered")
            if u["username"]==b.username: raise HTTPException(400,"Username already taken")
        uid=new_id(); user={"id":uid,"username":b.username,"email":b.email,"password_hash":hash_password(b.password),"role":b.role or "user","created_at":now()}
        _u[uid]=user; return fmt_user(user)

@app.post("/auth/login",tags=["Auth"])
def login(form:OAuth2PasswordRequestForm=Depends()):
    u=db_q("SELECT * FROM users WHERE username=%s",(form.username,),one=True) if use_pg() else next((x for x in (seed() or _u).values() if x["username"]==form.username),None)
    if not u or not verify_password(form.password,u["password_hash"]): raise HTTPException(401,"Invalid username or password")
    return {"access_token":create_token({"sub":u["id"]}),"token_type":"bearer","user":fmt_user(u)}

# ══ USERS ═════════════════════════════════════════════════════════════════════
@app.get("/users/me",tags=["Users"])
def get_me(cu=Depends(get_current_user)): return fmt_user(cu)

@app.get("/users/",tags=["Users"])
def list_users(cu=Depends(get_current_user)):
    return [fmt_user(u) for u in (db_q("SELECT * FROM users ORDER BY created_at") if use_pg() else (seed() or _u).values())]

@app.get("/users/{uid}",tags=["Users"])
def get_user(uid:str,cu=Depends(get_current_user)):
    u=db_q("SELECT * FROM users WHERE id=%s",(uid,),one=True) if use_pg() else _u.get(uid)
    if not u: raise HTTPException(404,"User not found")
    return fmt_user(u)

@app.put("/users/{uid}",tags=["Users"])
def update_user(uid:str,b:UpdUser,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM users WHERE id=%s",(uid,),one=True): raise HTTPException(404,"User not found")
        if b.username: db_x("UPDATE users SET username=%s WHERE id=%s",(b.username,uid))
        if b.email: db_x("UPDATE users SET email=%s WHERE id=%s",(b.email,uid))
        if b.role: db_x("UPDATE users SET role=%s WHERE id=%s",(b.role,uid))
        return fmt_user(db_q("SELECT * FROM users WHERE id=%s",(uid,),one=True))
    else:
        seed(); u=_u.get(uid)
        if not u: raise HTTPException(404,"User not found")
        if b.username: u["username"]=b.username
        if b.email: u["email"]=b.email
        if b.role: u["role"]=b.role
        return fmt_user(u)

@app.delete("/users/{uid}",tags=["Users"])
def delete_user(uid:str,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM users WHERE id=%s",(uid,),one=True): raise HTTPException(404,"User not found")
        db_x("DELETE FROM users WHERE id=%s",(uid,))
    else:
        seed()
        if uid not in _u: raise HTTPException(404,"User not found")
        del _u[uid]
    return {"message":f"User {uid} deleted"}

# ══ PRODUCTS ══════════════════════════════════════════════════════════════════
@app.get("/products/categories/all",tags=["Products"])
def get_cats():
    if use_pg(): return {"categories":[r["category"] for r in db_q("SELECT DISTINCT category FROM products ORDER BY category")]}
    seed(); return {"categories":sorted(set(p["category"] for p in _p.values()))}

@app.get("/products/",tags=["Products"])
def list_products(category:Optional[str]=Query(None),min_price:Optional[float]=Query(None),max_price:Optional[float]=Query(None)):
    if use_pg():
        sql="SELECT * FROM products WHERE 1=1"; params=[]
        if category: sql+=" AND LOWER(category)=LOWER(%s)"; params.append(category)
        if min_price is not None: sql+=" AND price>=%s"; params.append(min_price)
        if max_price is not None: sql+=" AND price<=%s"; params.append(max_price)
        items=db_q(sql,params)
    else:
        seed(); items=list(_p.values())
        if category: items=[x for x in items if x["category"].lower()==category.lower()]
        if min_price is not None: items=[x for x in items if x["price"]>=min_price]
        if max_price is not None: items=[x for x in items if x["price"]<=max_price]
    return {"count":len(items),"items":items}

@app.post("/products/",status_code=201,tags=["Products"])
def create_product(b:ProdCreate,cu=Depends(get_current_user)):
    pid=new_id()
    if use_pg():
        db_x("INSERT INTO products VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(pid,b.name,b.category,b.price,b.stock,b.description,cu["id"],now()))
        return db_q("SELECT * FROM products WHERE id=%s",(pid,),one=True)
    else:
        seed(); p={"id":pid,**b.model_dump(),"created_by":cu["id"],"created_at":now()}; _p[pid]=p; return p

@app.get("/products/{pid}",tags=["Products"])
def get_product(pid:str):
    p=db_q("SELECT * FROM products WHERE id=%s",(pid,),one=True) if use_pg() else _p.get(pid)
    if not p: raise HTTPException(404,"Product not found")
    return p

@app.put("/products/{pid}",tags=["Products"])
def update_product(pid:str,b:ProdUpdate,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM products WHERE id=%s",(pid,),one=True): raise HTTPException(404,"Product not found")
        for f,v in b.model_dump(exclude_none=True).items(): db_x(f"UPDATE products SET {f}=%s WHERE id=%s",(v,pid))
        return db_q("SELECT * FROM products WHERE id=%s",(pid,),one=True)
    else:
        seed(); p=_p.get(pid)
        if not p: raise HTTPException(404,"Product not found")
        for f,v in b.model_dump(exclude_none=True).items(): p[f]=v
        return p

@app.delete("/products/{pid}",tags=["Products"])
def delete_product(pid:str,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM products WHERE id=%s",(pid,),one=True): raise HTTPException(404,"Product not found")
        db_x("DELETE FROM products WHERE id=%s",(pid,))
    else:
        seed()
        if pid not in _p: raise HTTPException(404,"Product not found")
        del _p[pid]
    return {"message":f"Product {pid} deleted"}

# ══ POSTS ═════════════════════════════════════════════════════════════════════
@app.get("/posts/",tags=["Posts"])
def list_posts(tag:Optional[str]=Query(None)):
    if use_pg():
        rows=db_q("SELECT p.*,(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) as comments_count FROM posts p ORDER BY p.created_at DESC")
        for r in rows: r["tags"]=parse_tags(r.get("tags","[]"))
        if tag: rows=[r for r in rows if tag in r["tags"]]
    else:
        seed(); rows=list(_po.values())
        for r in rows: r["comments_count"]=len([c for c in _co.values() if c["post_id"]==r["id"]])
        if tag: rows=[r for r in rows if tag in r.get("tags",[])]
    return {"count":len(rows),"items":rows}

@app.post("/posts/",status_code=201,tags=["Posts"])
def create_post(b:PostCreate,cu=Depends(get_current_user)):
    pid=new_id(); tags_s=_json.dumps(b.tags or [])
    if use_pg():
        db_x("INSERT INTO posts VALUES(%s,%s,%s,%s,%s,%s,%s)",(pid,b.title,b.body,cu["id"],tags_s,now(),now()))
        p=db_q("SELECT * FROM posts WHERE id=%s",(pid,),one=True); p["tags"]=parse_tags(p.get("tags","[]")); return p
    else:
        seed(); p={"id":pid,"title":b.title,"body":b.body,"author_id":cu["id"],"tags":b.tags or [],"created_at":now(),"updated_at":now()}; _po[pid]=p; return p

@app.get("/posts/{pid}",tags=["Posts"])
def get_post(pid:str):
    if use_pg():
        p=db_q("SELECT p.*,(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) as comments_count FROM posts p WHERE p.id=%s",(pid,),one=True)
        if not p: raise HTTPException(404,"Post not found")
        p["tags"]=parse_tags(p.get("tags","[]")); return p
    else:
        seed(); p=_po.get(pid)
        if not p: raise HTTPException(404,"Post not found")
        return {**p,"comments_count":len([c for c in _co.values() if c["post_id"]==pid])}

@app.put("/posts/{pid}",tags=["Posts"])
def update_post(pid:str,b:PostUpdate,cu=Depends(get_current_user)):
    if use_pg():
        p=db_q("SELECT * FROM posts WHERE id=%s",(pid,),one=True)
        if not p: raise HTTPException(404,"Post not found")
        if p["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your post")
        if b.title: db_x("UPDATE posts SET title=%s WHERE id=%s",(b.title,pid))
        if b.body: db_x("UPDATE posts SET body=%s WHERE id=%s",(b.body,pid))
        if b.tags is not None: db_x("UPDATE posts SET tags=%s WHERE id=%s",(_json.dumps(b.tags),pid))
        db_x("UPDATE posts SET updated_at=%s WHERE id=%s",(now(),pid))
        p=db_q("SELECT * FROM posts WHERE id=%s",(pid,),one=True); p["tags"]=parse_tags(p.get("tags","[]")); return p
    else:
        seed(); p=_po.get(pid)
        if not p: raise HTTPException(404,"Post not found")
        if p["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your post")
        for f,v in b.model_dump(exclude_none=True).items(): p[f]=v
        p["updated_at"]=now(); return p

@app.delete("/posts/{pid}",tags=["Posts"])
def delete_post(pid:str,cu=Depends(get_current_user)):
    if use_pg():
        p=db_q("SELECT * FROM posts WHERE id=%s",(pid,),one=True)
        if not p: raise HTTPException(404,"Post not found")
        if p["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your post")
        db_x("DELETE FROM comments WHERE post_id=%s",(pid,)); db_x("DELETE FROM posts WHERE id=%s",(pid,))
    else:
        seed(); p=_po.get(pid)
        if not p: raise HTTPException(404,"Post not found")
        if p["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your post")
        del _po[pid]
        for k in [k for k,c in _co.items() if c["post_id"]==pid]: del _co[k]
    return {"message":f"Post {pid} deleted"}

@app.get("/posts/{pid}/comments",tags=["Posts"])
def list_comments(pid:str):
    if use_pg():
        if not db_q("SELECT id FROM posts WHERE id=%s",(pid,),one=True): raise HTTPException(404,"Post not found")
        items=db_q("SELECT * FROM comments WHERE post_id=%s ORDER BY created_at",(pid,))
    else:
        seed()
        if pid not in _po: raise HTTPException(404,"Post not found")
        items=[c for c in _co.values() if c["post_id"]==pid]
    return {"count":len(items),"items":items}

@app.post("/posts/{pid}/comments",status_code=201,tags=["Posts"])
def create_comment(pid:str,b:CommentCreate,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM posts WHERE id=%s",(pid,),one=True): raise HTTPException(404,"Post not found")
        cid=new_id(); db_x("INSERT INTO comments VALUES(%s,%s,%s,%s,%s)",(cid,pid,b.body,cu["id"],now()))
        return db_q("SELECT * FROM comments WHERE id=%s",(cid,),one=True)
    else:
        seed()
        if pid not in _po: raise HTTPException(404,"Post not found")
        cid=new_id(); c={"id":cid,"post_id":pid,"body":b.body,"author_id":cu["id"],"created_at":now()}; _co[cid]=c; return c

@app.put("/posts/{pid}/comments/{cid}",tags=["Posts"])
def update_comment(pid:str,cid:str,b:CommentUpdate,cu=Depends(get_current_user)):
    if use_pg():
        c=db_q("SELECT * FROM comments WHERE id=%s AND post_id=%s",(cid,pid),one=True)
        if not c: raise HTTPException(404,"Comment not found")
        if c["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your comment")
        db_x("UPDATE comments SET body=%s WHERE id=%s",(b.body,cid))
        return db_q("SELECT * FROM comments WHERE id=%s",(cid,),one=True)
    else:
        seed(); c=_co.get(cid)
        if not c or c["post_id"]!=pid: raise HTTPException(404,"Comment not found")
        if c["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your comment")
        c["body"]=b.body; return c

@app.delete("/posts/{pid}/comments/{cid}",tags=["Posts"])
def delete_comment(pid:str,cid:str,cu=Depends(get_current_user)):
    if use_pg():
        c=db_q("SELECT * FROM comments WHERE id=%s AND post_id=%s",(cid,pid),one=True)
        if not c: raise HTTPException(404,"Comment not found")
        if c["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your comment")
        db_x("DELETE FROM comments WHERE id=%s",(cid,))
    else:
        seed(); c=_co.get(cid)
        if not c or c["post_id"]!=pid: raise HTTPException(404,"Comment not found")
        if c["author_id"]!=cu["id"] and cu["role"]!="admin": raise HTTPException(403,"Not your comment")
        del _co[cid]
    return {"message":f"Comment {cid} deleted"}

# ══ TASKS ═════════════════════════════════════════════════════════════════════
VP={"low","medium","high"}; VS={"todo","in_progress","done"}

@app.get("/tasks/",tags=["Tasks"])
def list_tasks(status:Optional[str]=Query(None),priority:Optional[str]=Query(None),assigned_to:Optional[str]=Query(None),cu=Depends(get_current_user)):
    if use_pg():
        sql="SELECT * FROM tasks WHERE 1=1"; params=[]
        if status: sql+=" AND status=%s"; params.append(status)
        if priority: sql+=" AND priority=%s"; params.append(priority)
        if assigned_to: sql+=" AND assigned_to=%s"; params.append(assigned_to)
        items=db_q(sql,params)
    else:
        seed(); items=list(_t.values())
        if status: items=[x for x in items if x["status"]==status]
        if priority: items=[x for x in items if x["priority"]==priority]
        if assigned_to: items=[x for x in items if x["assigned_to"]==assigned_to]
    return {"count":len(items),"items":items}

@app.post("/tasks/",status_code=201,tags=["Tasks"])
def create_task(b:TaskCreate,cu=Depends(get_current_user)):
    if b.priority and b.priority not in VP: raise HTTPException(400,f"priority must be one of: {VP}")
    if b.status and b.status not in VS: raise HTTPException(400,f"status must be one of: {VS}")
    tid=new_id()
    if use_pg():
        db_x("INSERT INTO tasks VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(tid,b.title,b.description,b.priority or "medium",b.status or "todo",b.assigned_to,cu["id"],now(),b.due_date))
        return db_q("SELECT * FROM tasks WHERE id=%s",(tid,),one=True)
    else:
        seed(); t={"id":tid,**b.model_dump(),"created_by":cu["id"],"created_at":now()}; _t[tid]=t; return t

@app.get("/tasks/{tid}",tags=["Tasks"])
def get_task(tid:str,cu=Depends(get_current_user)):
    t=db_q("SELECT * FROM tasks WHERE id=%s",(tid,),one=True) if use_pg() else _t.get(tid)
    if not t: raise HTTPException(404,"Task not found")
    return t

@app.put("/tasks/{tid}",tags=["Tasks"])
def update_task(tid:str,b:TaskUpdate,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM tasks WHERE id=%s",(tid,),one=True): raise HTTPException(404,"Task not found")
        for f,v in b.model_dump(exclude_none=True).items(): db_x(f"UPDATE tasks SET {f}=%s WHERE id=%s",(v,tid))
        return db_q("SELECT * FROM tasks WHERE id=%s",(tid,),one=True)
    else:
        seed(); t=_t.get(tid)
        if not t: raise HTTPException(404,"Task not found")
        for f,v in b.model_dump(exclude_none=True).items(): t[f]=v
        return t

@app.patch("/tasks/{tid}/status",tags=["Tasks"])
def update_task_status(tid:str,new_status:str=Query(...),cu=Depends(get_current_user)):
    if new_status not in VS: raise HTTPException(400,f"status must be one of: {VS}")
    if use_pg():
        if not db_q("SELECT id FROM tasks WHERE id=%s",(tid,),one=True): raise HTTPException(404,"Task not found")
        db_x("UPDATE tasks SET status=%s WHERE id=%s",(new_status,tid))
        return db_q("SELECT * FROM tasks WHERE id=%s",(tid,),one=True)
    else:
        seed(); t=_t.get(tid)
        if not t: raise HTTPException(404,"Task not found")
        t["status"]=new_status; return t

@app.delete("/tasks/{tid}",tags=["Tasks"])
def delete_task(tid:str,cu=Depends(get_current_user)):
    if use_pg():
        if not db_q("SELECT id FROM tasks WHERE id=%s",(tid,),one=True): raise HTTPException(404,"Task not found")
        db_x("DELETE FROM tasks WHERE id=%s",(tid,))
    else:
        seed()
        if tid not in _t: raise HTTPException(404,"Task not found")
        del _t[tid]
    return {"message":f"Task {tid} deleted"}

# ══ PAYMENTS ══════════════════════════════════════════════════════════════════
@app.get("/payments/stats/summary",tags=["Payments"])
def pay_stats(cu=Depends(get_current_user)):
    if use_pg():
        items=db_q("SELECT * FROM payments") if cu["role"]=="admin" else db_q("SELECT * FROM payments WHERE from_user_id=%s OR to_user_id=%s",(cu["id"],cu["id"]))
    else:
        seed(); items=list(_pay.values())
        if cu["role"]!="admin": items=[p for p in items if p["from_user_id"]==cu["id"] or p["to_user_id"]==cu["id"]]
    by_s={}
    for p in items: by_s[p["status"]]=by_s.get(p["status"],0)+p["amount"]
    return {"total_transactions":len(items),"total_volume":round(sum(p["amount"] for p in items),2),"by_status":{k:round(v,2) for k,v in by_s.items()}}

@app.get("/payments/",tags=["Payments"])
def list_payments(status:Optional[str]=Query(None),cu=Depends(get_current_user)):
    if use_pg():
        if cu["role"]=="admin": sql="SELECT * FROM payments WHERE 1=1"; params=[]
        else: sql="SELECT * FROM payments WHERE (from_user_id=%s OR to_user_id=%s)"; params=[cu["id"],cu["id"]]
        if status: sql+=" AND status=%s"; params.append(status)
        items=db_q(sql,params)
    else:
        seed(); items=list(_pay.values())
        if cu["role"]!="admin": items=[p for p in items if p["from_user_id"]==cu["id"] or p["to_user_id"]==cu["id"]]
        if status: items=[p for p in items if p["status"]==status]
    return {"count":len(items),"total_amount":round(sum(p["amount"] for p in items),2),"items":items}

@app.post("/payments/",status_code=201,tags=["Payments"])
def create_payment(b:PayCreate,cu=Depends(get_current_user)):
    if b.to_user_id==cu["id"]: raise HTTPException(400,"Cannot send payment to yourself")
    if b.amount<=0: raise HTTPException(400,"Amount must be greater than 0")
    if use_pg():
        if not db_q("SELECT id FROM users WHERE id=%s",(b.to_user_id,),one=True): raise HTTPException(404,"Recipient user not found")
        pid=new_id(); db_x("INSERT INTO payments VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(pid,cu["id"],b.to_user_id,round(b.amount,2),b.currency or "USD","completed",b.description,now()))
        return db_q("SELECT * FROM payments WHERE id=%s",(pid,),one=True)
    else:
        seed()
        if b.to_user_id not in _u: raise HTTPException(404,"Recipient user not found")
        pid=new_id(); p={"id":pid,"from_user_id":cu["id"],"to_user_id":b.to_user_id,"amount":round(b.amount,2),"currency":b.currency or "USD","status":"completed","description":b.description,"created_at":now()}
        _pay[pid]=p; return p

@app.get("/payments/{pid}",tags=["Payments"])
def get_payment(pid:str,cu=Depends(get_current_user)):
    p=db_q("SELECT * FROM payments WHERE id=%s",(pid,),one=True) if use_pg() else _pay.get(pid)
    if not p: raise HTTPException(404,"Payment not found")
    if cu["role"]!="admin" and p["from_user_id"]!=cu["id"] and p["to_user_id"]!=cu["id"]: raise HTTPException(403,"Access denied")
    return p

@app.patch("/payments/{pid}/refund",tags=["Payments"])
def refund_payment(pid:str,cu=Depends(get_current_user)):
    p=db_q("SELECT * FROM payments WHERE id=%s",(pid,),one=True) if use_pg() else _pay.get(pid)
    if not p: raise HTTPException(404,"Payment not found")
    if cu["role"]!="admin" and p["from_user_id"]!=cu["id"]: raise HTTPException(403,"Access denied")
    if p["status"]!="completed": raise HTTPException(400,f"Cannot refund payment with status '{p['status']}'")
    if use_pg():
        db_x("UPDATE payments SET status='refunded' WHERE id=%s",(pid,))
        return db_q("SELECT * FROM payments WHERE id=%s",(pid,),one=True)
    else:
        p["status"]="refunded"; return p
