from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid

# ─── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = "super-secret-key-for-testing-only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QA Practice API",
    description="""
## REST API для практики QA в Postman

Полный набор эндпоинтов для тренировки тестирования:

- 👤 **Auth / Users** — регистрация, логин, JWT
- 🛍️ **Products** — товары с категориями и ценами
- 📝 **Posts + Comments** — блог с комментариями
- ✅ **Tasks** — todo с приоритетами и статусами
- 💳 **Payments** — транзакции между пользователями

**Тестовый аккаунт:** `admin` / `admin123`
    """,
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Utils ─────────────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def hash_password(p): return pwd_context.hash(p)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
def new_id(): return str(uuid.uuid4())
def now(): return datetime.utcnow().isoformat()

def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    exc = HTTPException(status_code=401, detail="Invalid or expired token",
                        headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        if not uid: raise exc
    except JWTError:
        raise exc
    user = users_db.get(uid)
    if not user: raise exc
    return user

# ═══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY DATABASES
# ═══════════════════════════════════════════════════════════════════════════════
users_db: dict = {}
products_db: dict = {}
posts_db: dict = {}
comments_db: dict = {}
tasks_db: dict = {}
payments_db: dict = {}

# ── Seed data ──────────────────────────────────────────────────────────────────
_admin_id = new_id()
_user_id  = new_id()

users_db[_admin_id] = {
    "id": _admin_id, "username": "admin", "email": "admin@test.com",
    "password_hash": hash_password("admin123"), "role": "admin", "created_at": now()
}
users_db[_user_id] = {
    "id": _user_id, "username": "tester", "email": "tester@test.com",
    "password_hash": hash_password("tester123"), "role": "user", "created_at": now()
}

# Seed products
for name, cat, price, stock in [
    ("iPhone 15",      "Electronics", 999.99, 50),
    ("Samsung TV 55",  "Electronics", 599.99, 20),
    ("Nike Air Max",   "Shoes",       149.99, 100),
    ("Python Book",    "Books",       39.99,  200),
    ("Coffee Maker",   "Kitchen",     79.99,  35),
]:
    pid = new_id()
    products_db[pid] = {
        "id": pid, "name": name, "category": cat, "price": price,
        "stock": stock, "description": f"Test product: {name}",
        "created_by": _admin_id, "created_at": now()
    }

# Seed posts
for title, body in [
    ("How to test REST API", "REST API testing is essential for quality assurance..."),
    ("Postman tips and tricks", "Here are some useful Postman features for QA engineers..."),
    ("JWT Authentication explained", "JSON Web Tokens are widely used for API authentication..."),
]:
    post_id = new_id()
    posts_db[post_id] = {
        "id": post_id, "title": title, "body": body,
        "author_id": _admin_id, "tags": ["qa", "testing"], "created_at": now(), "updated_at": now()
    }
    # Add a comment to each post
    cid = new_id()
    comments_db[cid] = {
        "id": cid, "post_id": post_id, "body": "Great post! Very helpful.",
        "author_id": _user_id, "created_at": now()
    }

# Seed tasks
for title, priority, task_status in [
    ("Write test cases for login", "high",   "in_progress"),
    ("Test registration endpoint", "high",   "done"),
    ("Check 404 responses",        "medium", "todo"),
    ("Test JWT expiration",        "medium", "todo"),
    ("Performance testing",        "low",    "todo"),
]:
    tid = new_id()
    tasks_db[tid] = {
        "id": tid, "title": title, "description": f"Task: {title}",
        "priority": priority, "status": task_status,
        "assigned_to": _user_id, "created_by": _admin_id, "created_at": now(), "due_date": "2026-12-31"
    }

# Seed payments
for amount, desc in [(100.0, "Course payment"), (50.0, "Book purchase"), (250.0, "Software license")]:
    pay_id = new_id()
    payments_db[pay_id] = {
        "id": pay_id, "from_user_id": _user_id, "to_user_id": _admin_id,
        "amount": amount, "currency": "USD", "status": "completed",
        "description": desc, "created_at": now()
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

# — Auth / Users —
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "user"

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# — Products —
class ProductCreate(BaseModel):
    name: str
    category: str
    price: float
    stock: int = 0
    description: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None

# — Posts —
class PostCreate(BaseModel):
    title: str
    body: str
    tags: Optional[List[str]] = []

class PostUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[List[str]] = None

# — Comments —
class CommentCreate(BaseModel):
    body: str

class CommentUpdate(BaseModel):
    body: str

# — Tasks —
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"   # low / medium / high
    status: Optional[str] = "todo"       # todo / in_progress / done
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None

# — Payments —
class PaymentCreate(BaseModel):
    to_user_id: str
    amount: float
    currency: Optional[str] = "USD"
    description: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════════
# ── HEALTH ──────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "message": "QA Practice API v2.0 🚀",
        "docs": "/docs",
        "endpoints": {
            "auth":     ["/auth/register", "/auth/login"],
            "users":    ["/users/", "/users/me", "/users/{id}"],
            "products": ["/products/", "/products/{id}"],
            "posts":    ["/posts/", "/posts/{id}", "/posts/{id}/comments"],
            "tasks":    ["/tasks/", "/tasks/{id}"],
            "payments": ["/payments/", "/payments/{id}"],
        }
    }

@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "counts": {
            "users": len(users_db), "products": len(products_db),
            "posts": len(posts_db), "comments": len(comments_db),
            "tasks": len(tasks_db), "payments": len(payments_db),
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ── AUTH ────────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/auth/register", status_code=201, tags=["Auth"])
def register(body: RegisterRequest):
    """Регистрация. Аккаунты: admin/admin123, tester/tester123"""
    for u in users_db.values():
        if u["email"] == body.email:
            raise HTTPException(400, "Email already registered")
        if u["username"] == body.username:
            raise HTTPException(400, "Username already taken")
    uid = new_id()
    user = {"id": uid, "username": body.username, "email": body.email,
            "password_hash": hash_password(body.password), "role": body.role or "user",
            "created_at": now()}
    users_db[uid] = user
    return _fmt_user(user)

@app.post("/auth/login", tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    """Логин. Body: x-www-form-urlencoded → username + password"""
    user = next((u for u in users_db.values() if u["username"] == form.username), None)
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": create_token({"sub": user["id"]}), "token_type": "bearer", "user": _fmt_user(user)}

# ═══════════════════════════════════════════════════════════════════════════════
# ── USERS ───────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/users/me", tags=["Users"])
def get_me(cu=Depends(get_current_user)):
    """Свой профиль"""
    return _fmt_user(cu)

@app.get("/users/", tags=["Users"])
def list_users(cu=Depends(get_current_user)):
    """Список всех пользователей"""
    return [_fmt_user(u) for u in users_db.values()]

@app.get("/users/{user_id}", tags=["Users"])
def get_user(user_id: str, cu=Depends(get_current_user)):
    """Пользователь по ID"""
    u = users_db.get(user_id)
    if not u: raise HTTPException(404, "User not found")
    return _fmt_user(u)

@app.put("/users/{user_id}", tags=["Users"])
def update_user(user_id: str, body: UpdateUserRequest, cu=Depends(get_current_user)):
    """Обновить пользователя"""
    u = users_db.get(user_id)
    if not u: raise HTTPException(404, "User not found")
    if body.username: u["username"] = body.username
    if body.email:    u["email"]    = body.email
    if body.role:     u["role"]     = body.role
    users_db[user_id] = u
    return _fmt_user(u)

@app.delete("/users/{user_id}", tags=["Users"])
def delete_user(user_id: str, cu=Depends(get_current_user)):
    """Удалить пользователя"""
    if user_id not in users_db: raise HTTPException(404, "User not found")
    del users_db[user_id]
    return {"message": f"User {user_id} deleted"}

# ═══════════════════════════════════════════════════════════════════════════════
# ── PRODUCTS ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/products/", tags=["Products"])
def list_products(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    min_price: Optional[float] = Query(None, description="Минимальная цена"),
    max_price: Optional[float] = Query(None, description="Максимальная цена"),
):
    """
    Список товаров. Публичный (без токена).
    
    Query params: `?category=Electronics`, `?min_price=50&max_price=200`
    """
    items = list(products_db.values())
    if category:  items = [p for p in items if p["category"].lower() == category.lower()]
    if min_price is not None: items = [p for p in items if p["price"] >= min_price]
    if max_price is not None: items = [p for p in items if p["price"] <= max_price]
    return {"count": len(items), "items": items}

@app.post("/products/", status_code=201, tags=["Products"])
def create_product(body: ProductCreate, cu=Depends(get_current_user)):
    """Создать товар (нужен токен)"""
    pid = new_id()
    product = {"id": pid, **body.model_dump(), "created_by": cu["id"], "created_at": now()}
    products_db[pid] = product
    return product

@app.get("/products/{product_id}", tags=["Products"])
def get_product(product_id: str):
    """Товар по ID. Публичный."""
    p = products_db.get(product_id)
    if not p: raise HTTPException(404, "Product not found")
    return p

@app.put("/products/{product_id}", tags=["Products"])
def update_product(product_id: str, body: ProductUpdate, cu=Depends(get_current_user)):
    """Обновить товар (нужен токен)"""
    p = products_db.get(product_id)
    if not p: raise HTTPException(404, "Product not found")
    for field, val in body.model_dump(exclude_none=True).items():
        p[field] = val
    products_db[product_id] = p
    return p

@app.delete("/products/{product_id}", tags=["Products"])
def delete_product(product_id: str, cu=Depends(get_current_user)):
    """Удалить товар (нужен токен)"""
    if product_id not in products_db: raise HTTPException(404, "Product not found")
    del products_db[product_id]
    return {"message": f"Product {product_id} deleted"}

@app.get("/products/categories/all", tags=["Products"])
def get_categories():
    """Список всех категорий товаров. Публичный."""
    cats = list(set(p["category"] for p in products_db.values()))
    return {"categories": sorted(cats)}

# ═══════════════════════════════════════════════════════════════════════════════
# ── POSTS ───────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/posts/", tags=["Posts"])
def list_posts(tag: Optional[str] = Query(None, description="Фильтр по тегу")):
    """Список постов. Публичный. Query: `?tag=qa`"""
    items = list(posts_db.values())
    if tag: items = [p for p in items if tag in p.get("tags", [])]
    return {"count": len(items), "items": items}

@app.post("/posts/", status_code=201, tags=["Posts"])
def create_post(body: PostCreate, cu=Depends(get_current_user)):
    """Создать пост (нужен токен)"""
    pid = new_id()
    post = {"id": pid, **body.model_dump(), "author_id": cu["id"], "created_at": now(), "updated_at": now()}
    posts_db[pid] = post
    return post

@app.get("/posts/{post_id}", tags=["Posts"])
def get_post(post_id: str):
    """Пост по ID. Публичный."""
    p = posts_db.get(post_id)
    if not p: raise HTTPException(404, "Post not found")
    post_comments = [c for c in comments_db.values() if c["post_id"] == post_id]
    return {**p, "comments_count": len(post_comments)}

@app.put("/posts/{post_id}", tags=["Posts"])
def update_post(post_id: str, body: PostUpdate, cu=Depends(get_current_user)):
    """Обновить пост (только автор)"""
    p = posts_db.get(post_id)
    if not p: raise HTTPException(404, "Post not found")
    if p["author_id"] != cu["id"] and cu["role"] != "admin":
        raise HTTPException(403, "Not your post")
    for field, val in body.model_dump(exclude_none=True).items():
        p[field] = val
    p["updated_at"] = now()
    posts_db[post_id] = p
    return p

@app.delete("/posts/{post_id}", tags=["Posts"])
def delete_post(post_id: str, cu=Depends(get_current_user)):
    """Удалить пост (автор или admin)"""
    p = posts_db.get(post_id)
    if not p: raise HTTPException(404, "Post not found")
    if p["author_id"] != cu["id"] and cu["role"] != "admin":
        raise HTTPException(403, "Not your post")
    del posts_db[post_id]
    # Удаляем комменты этого поста
    for cid in [k for k, c in comments_db.items() if c["post_id"] == post_id]:
        del comments_db[cid]
    return {"message": f"Post {post_id} deleted"}

# ── Comments ──────────────────────────────────────────────────────────────────
@app.get("/posts/{post_id}/comments", tags=["Posts"])
def list_comments(post_id: str):
    """Комментарии к посту. Публичный."""
    if post_id not in posts_db: raise HTTPException(404, "Post not found")
    items = [c for c in comments_db.values() if c["post_id"] == post_id]
    return {"count": len(items), "items": items}

@app.post("/posts/{post_id}/comments", status_code=201, tags=["Posts"])
def create_comment(post_id: str, body: CommentCreate, cu=Depends(get_current_user)):
    """Добавить комментарий (нужен токен)"""
    if post_id not in posts_db: raise HTTPException(404, "Post not found")
    cid = new_id()
    comment = {"id": cid, "post_id": post_id, "body": body.body,
                "author_id": cu["id"], "created_at": now()}
    comments_db[cid] = comment
    return comment

@app.put("/posts/{post_id}/comments/{comment_id}", tags=["Posts"])
def update_comment(post_id: str, comment_id: str, body: CommentUpdate, cu=Depends(get_current_user)):
    """Обновить комментарий (только автор)"""
    c = comments_db.get(comment_id)
    if not c or c["post_id"] != post_id: raise HTTPException(404, "Comment not found")
    if c["author_id"] != cu["id"] and cu["role"] != "admin":
        raise HTTPException(403, "Not your comment")
    c["body"] = body.body
    comments_db[comment_id] = c
    return c

@app.delete("/posts/{post_id}/comments/{comment_id}", tags=["Posts"])
def delete_comment(post_id: str, comment_id: str, cu=Depends(get_current_user)):
    """Удалить комментарий (автор или admin)"""
    c = comments_db.get(comment_id)
    if not c or c["post_id"] != post_id: raise HTTPException(404, "Comment not found")
    if c["author_id"] != cu["id"] and cu["role"] != "admin":
        raise HTTPException(403, "Not your comment")
    del comments_db[comment_id]
    return {"message": f"Comment {comment_id} deleted"}

# ═══════════════════════════════════════════════════════════════════════════════
# ── TASKS ───────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/tasks/", tags=["Tasks"])
def list_tasks(
    status: Optional[str] = Query(None, description="todo / in_progress / done"),
    priority: Optional[str] = Query(None, description="low / medium / high"),
    assigned_to: Optional[str] = Query(None, description="user_id"),
    cu=Depends(get_current_user)
):
    """
    Список задач (нужен токен).
    
    Query: `?status=todo`, `?priority=high`, `?assigned_to=<user_id>`
    """
    items = list(tasks_db.values())
    if status:      items = [t for t in items if t["status"]   == status]
    if priority:    items = [t for t in items if t["priority"] == priority]
    if assigned_to: items = [t for t in items if t["assigned_to"] == assigned_to]
    return {"count": len(items), "items": items}

@app.post("/tasks/", status_code=201, tags=["Tasks"])
def create_task(body: TaskCreate, cu=Depends(get_current_user)):
    """Создать задачу (нужен токен)"""
    VALID_PRIORITIES = {"low", "medium", "high"}
    VALID_STATUSES   = {"todo", "in_progress", "done"}
    if body.priority and body.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of: {VALID_PRIORITIES}")
    if body.status and body.status not in VALID_STATUSES:
        raise HTTPException(400, f"status must be one of: {VALID_STATUSES}")
    tid = new_id()
    task = {"id": tid, **body.model_dump(), "created_by": cu["id"], "created_at": now()}
    tasks_db[tid] = task
    return task

@app.get("/tasks/{task_id}", tags=["Tasks"])
def get_task(task_id: str, cu=Depends(get_current_user)):
    """Задача по ID"""
    t = tasks_db.get(task_id)
    if not t: raise HTTPException(404, "Task not found")
    return t

@app.put("/tasks/{task_id}", tags=["Tasks"])
def update_task(task_id: str, body: TaskUpdate, cu=Depends(get_current_user)):
    """Обновить задачу (нужен токен)"""
    t = tasks_db.get(task_id)
    if not t: raise HTTPException(404, "Task not found")
    for field, val in body.model_dump(exclude_none=True).items():
        t[field] = val
    tasks_db[task_id] = t
    return t

@app.patch("/tasks/{task_id}/status", tags=["Tasks"])
def update_task_status(task_id: str, new_status: str = Query(..., description="todo / in_progress / done"), cu=Depends(get_current_user)):
    """
    Быстро поменять статус задачи (PATCH).
    
    Query: `?new_status=done`
    """
    VALID = {"todo", "in_progress", "done"}
    if new_status not in VALID: raise HTTPException(400, f"status must be one of: {VALID}")
    t = tasks_db.get(task_id)
    if not t: raise HTTPException(404, "Task not found")
    t["status"] = new_status
    tasks_db[task_id] = t
    return t

@app.delete("/tasks/{task_id}", tags=["Tasks"])
def delete_task(task_id: str, cu=Depends(get_current_user)):
    """Удалить задачу"""
    if task_id not in tasks_db: raise HTTPException(404, "Task not found")
    del tasks_db[task_id]
    return {"message": f"Task {task_id} deleted"}

# ═══════════════════════════════════════════════════════════════════════════════
# ── PAYMENTS ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/payments/", tags=["Payments"])
def list_payments(
    status: Optional[str] = Query(None, description="pending / completed / failed / refunded"),
    cu=Depends(get_current_user)
):
    """
    Список платежей (нужен токен).
    
    Возвращает только те платежи, где ты отправитель или получатель.
    Admin видит все.
    """
    items = list(payments_db.values())
    if cu["role"] != "admin":
        items = [p for p in items if p["from_user_id"] == cu["id"] or p["to_user_id"] == cu["id"]]
    if status:
        items = [p for p in items if p["status"] == status]
    total = sum(p["amount"] for p in items)
    return {"count": len(items), "total_amount": round(total, 2), "items": items}

@app.post("/payments/", status_code=201, tags=["Payments"])
def create_payment(body: PaymentCreate, cu=Depends(get_current_user)):
    """
    Отправить платёж (нужен токен).
    
    Нельзя платить самому себе. to_user_id должен существовать.
    """
    if body.to_user_id == cu["id"]:
        raise HTTPException(400, "Cannot send payment to yourself")
    if body.to_user_id not in users_db:
        raise HTTPException(404, "Recipient user not found")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be greater than 0")

    pay_id = new_id()
    payment = {
        "id": pay_id,
        "from_user_id": cu["id"],
        "to_user_id": body.to_user_id,
        "amount": round(body.amount, 2),
        "currency": body.currency or "USD",
        "status": "completed",
        "description": body.description,
        "created_at": now()
    }
    payments_db[pay_id] = payment
    return payment

@app.get("/payments/{payment_id}", tags=["Payments"])
def get_payment(payment_id: str, cu=Depends(get_current_user)):
    """Платёж по ID"""
    p = payments_db.get(payment_id)
    if not p: raise HTTPException(404, "Payment not found")
    if cu["role"] != "admin" and p["from_user_id"] != cu["id"] and p["to_user_id"] != cu["id"]:
        raise HTTPException(403, "Access denied")
    return p

@app.patch("/payments/{payment_id}/refund", tags=["Payments"])
def refund_payment(payment_id: str, cu=Depends(get_current_user)):
    """
    Вернуть платёж (PATCH). Только completed → refunded.
    Только отправитель или admin.
    """
    p = payments_db.get(payment_id)
    if not p: raise HTTPException(404, "Payment not found")
    if cu["role"] != "admin" and p["from_user_id"] != cu["id"]:
        raise HTTPException(403, "Access denied")
    if p["status"] != "completed":
        raise HTTPException(400, f"Cannot refund payment with status '{p['status']}'")
    p["status"] = "refunded"
    payments_db[payment_id] = p
    return p

@app.get("/payments/stats/summary", tags=["Payments"])
def payment_stats(cu=Depends(get_current_user)):
    """Статистика по платежам (нужен токен)"""
    items = list(payments_db.values())
    if cu["role"] != "admin":
        items = [p for p in items if p["from_user_id"] == cu["id"] or p["to_user_id"] == cu["id"]]
    by_status = {}
    for p in items:
        s = p["status"]
        by_status[s] = by_status.get(s, 0) + p["amount"]
    return {
        "total_transactions": len(items),
        "total_volume": round(sum(p["amount"] for p in items), 2),
        "by_status": {k: round(v, 2) for k, v in by_status.items()},
    }

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _fmt_user(u):
    return {"id": u["id"], "username": u["username"], "email": u["email"],
            "role": u["role"], "created_at": u["created_at"]}
