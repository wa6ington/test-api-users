from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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
    title="Test Users API",
    description="REST API для тестирования в Postman. Users + Auth с JWT.",
    version="1.0.0"
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

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(user_id)
    if user is None:
        raise credentials_exception
    return user

# ─── In-Memory DB ──────────────────────────────────────────────────────────────
# Vercel — serverless, каждый cold start пересоздаёт db.
# Для тестов это нормально — admin всегда есть.
db: dict = {}

seed_id = str(uuid.uuid4())
db[seed_id] = {
    "id": seed_id,
    "username": "admin",
    "email": "admin@test.com",
    "password_hash": hash_password("admin123"),
    "role": "admin",
    "created_at": datetime.utcnow().isoformat()
}

# ─── Schemas ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "user"

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: str

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# ─── Helper ────────────────────────────────────────────────────────────────────
def _to_response(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"]
    }

# ─── Auth Routes ───────────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=UserResponse, status_code=201, tags=["Auth"])
def register(body: RegisterRequest):
    """Регистрация нового пользователя"""
    for u in db.values():
        if u["email"] == body.email:
            raise HTTPException(status_code=400, detail="Email already registered")
        if u["username"] == body.username:
            raise HTTPException(status_code=400, detail="Username already taken")

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "username": body.username,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "created_at": datetime.utcnow().isoformat()
    }
    db[user_id] = user
    return _to_response(user)


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Логин. В Postman: Body → x-www-form-urlencoded, поля **username** и **password**.

    Тестовый аккаунт: `admin` / `admin123`
    """
    user = next((u for u in db.values() if u["username"] == form.username), None)
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token({"sub": user["id"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _to_response(user)
    }

# ─── Users Routes ──────────────────────────────────────────────────────────────
@app.get("/users/me", response_model=UserResponse, tags=["Users"])
def get_me(current_user=Depends(get_current_user)):
    """Получить свой профиль (требует Bearer токен)"""
    return _to_response(current_user)


@app.get("/users/", response_model=list[UserResponse], tags=["Users"])
def list_users(current_user=Depends(get_current_user)):
    """Список всех пользователей (требует Bearer токен)"""
    return [_to_response(u) for u in db.values()]


@app.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: str, current_user=Depends(get_current_user)):
    """Получить пользователя по ID"""
    user = db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_response(user)


@app.put("/users/{user_id}", response_model=UserResponse, tags=["Users"])
def update_user(user_id: str, body: UpdateUserRequest, current_user=Depends(get_current_user)):
    """Обновить пользователя"""
    user = db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username:
        user["username"] = body.username
    if body.email:
        user["email"] = body.email
    if body.role:
        user["role"] = body.role

    db[user_id] = user
    return _to_response(user)


@app.delete("/users/{user_id}", tags=["Users"])
def delete_user(user_id: str, current_user=Depends(get_current_user)):
    """Удалить пользователя"""
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    del db[user_id]
    return {"message": f"User {user_id} deleted"}

# ─── Health ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Test API is running 🚀"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "users_count": len(db)}
