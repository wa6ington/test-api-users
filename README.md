# Test Users API — Vercel Deploy

REST API для тестирования в Postman. FastAPI + JWT, данные в памяти.

## Структура проекта

```
├── api/
│   └── index.py       # Весь код API
├── requirements.txt   # Зависимости
├── vercel.json        # Конфиг Vercel
└── README.md
```

## Деплой на Vercel

### Вариант 1 — через GitHub (рекомендую)
1. Создай репо на GitHub, закинь туда все файлы
2. Зайди на https://vercel.com → New Project → Import Git Repository
3. Выбери репо → Deploy
4. Получишь URL: `https://your-project.vercel.app`

### Вариант 2 — через Vercel CLI
```bash
npm i -g vercel
vercel login
vercel --prod
```

## Эндпоинты

| Метод | URL | Auth | Описание |
|-------|-----|------|---------|
| GET | `/` | ❌ | Health check |
| GET | `/health` | ❌ | Статус + кол-во юзеров |
| POST | `/auth/register` | ❌ | Регистрация |
| POST | `/auth/login` | ❌ | Логин → JWT токен |
| GET | `/users/me` | ✅ | Свой профиль |
| GET | `/users/` | ✅ | Все пользователи |
| GET | `/users/{id}` | ✅ | Юзер по ID |
| PUT | `/users/{id}` | ✅ | Обновить юзера |
| DELETE | `/users/{id}` | ✅ | Удалить юзера |

## Тестовый аккаунт
- username: `admin`
- password: `admin123`

## Как пользоваться в Postman

### Шаг 1 — Логин
- POST `{{base_url}}/auth/login`
- Body: `x-www-form-urlencoded`
  - `username` = `admin`
  - `password` = `admin123`
- Скопируй `access_token` из ответа

### Шаг 2 — Защищённые запросы
- Headers: `Authorization: Bearer <токен>`

### Swagger UI
Открой `{{base_url}}/docs` — интерактивная документация в браузере.

## ⚠️ Важно про Vercel
Vercel serverless — каждый холодный старт пересоздаёт in-memory DB.
Это значит: созданные юзеры могут пропасть через ~10 мин неактивности.
Но `admin` всегда есть — он создаётся при старте.

Если нужно постоянное хранение — добавь Vercel Postgres (бесплатно в их dashboard).
