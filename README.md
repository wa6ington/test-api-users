# QA Practice API v2.0 — Vercel

Расширенный REST API для практики в Postman. 5 предметных областей, 38 эндпоинтов, JWT auth.

## Структура проекта

```
├── api/
│   └── index.py       # Весь код API
├── requirements.txt
└── vercel.json
```

## Деплой
Просто замени `index.py` в своём GitHub репо и запушь — Vercel передеплоит автоматически:

```bash
git add .
git commit -m "feat: add products, posts, tasks, payments endpoints"
git push
```

## Тестовые аккаунты
| username | password   | role  |
|----------|-----------|-------|
| admin    | admin123  | admin |
| tester   | tester123 | user  |

---

## 📚 Эндпоинты по модулям

### 👤 Auth
| Метод | URL | Auth |
|---|---|---|
| POST | `/auth/register` | ❌ |
| POST | `/auth/login` | ❌ |

### 👥 Users
| Метод | URL | Auth |
|---|---|---|
| GET | `/users/me` | ✅ |
| GET | `/users/` | ✅ |
| GET | `/users/{id}` | ✅ |
| PUT | `/users/{id}` | ✅ |
| DELETE | `/users/{id}` | ✅ |

### 🛍️ Products
| Метод | URL | Auth | Особенности |
|---|---|---|---|
| GET | `/products/` | ❌ | Query: `?category=`, `?min_price=`, `?max_price=` |
| POST | `/products/` | ✅ | Создать товар |
| GET | `/products/{id}` | ❌ | Публичный просмотр |
| PUT | `/products/{id}` | ✅ | |
| DELETE | `/products/{id}` | ✅ | |
| GET | `/products/categories/all` | ❌ | Список категорий |

### 📝 Posts + Comments
| Метод | URL | Auth | Особенности |
|---|---|---|---|
| GET | `/posts/` | ❌ | Query: `?tag=qa` |
| POST | `/posts/` | ✅ | |
| GET | `/posts/{id}` | ❌ | Включает comments_count |
| PUT | `/posts/{id}` | ✅ | Только автор/admin |
| DELETE | `/posts/{id}` | ✅ | Только автор/admin, каскадно удаляет комменты |
| GET | `/posts/{id}/comments` | ❌ | |
| POST | `/posts/{id}/comments` | ✅ | |
| PUT | `/posts/{id}/comments/{cid}` | ✅ | Только автор/admin |
| DELETE | `/posts/{id}/comments/{cid}` | ✅ | Только автор/admin |

### ✅ Tasks
| Метод | URL | Auth | Особенности |
|---|---|---|---|
| GET | `/tasks/` | ✅ | Query: `?status=`, `?priority=`, `?assigned_to=` |
| POST | `/tasks/` | ✅ | Валидация priority/status, иначе 400 |
| GET | `/tasks/{id}` | ✅ | |
| PUT | `/tasks/{id}` | ✅ | |
| PATCH | `/tasks/{id}/status?new_status=done` | ✅ | Быстрая смена статуса |
| DELETE | `/tasks/{id}` | ✅ | |

**Валидные значения:** priority = `low/medium/high`, status = `todo/in_progress/done`

### 💳 Payments
| Метод | URL | Auth | Особенности |
|---|---|---|---|
| GET | `/payments/` | ✅ | Видишь только свои (admin — все). Query: `?status=` |
| POST | `/payments/` | ✅ | 400 если self-payment, 404 если recipient не найден |
| GET | `/payments/{id}` | ✅ | 403 если не участник платежа |
| PATCH | `/payments/{id}/refund` | ✅ | completed → refunded, только отправитель/admin |
| GET | `/payments/stats/summary` | ✅ | Статистика по сумме и статусам |

---

## 🧪 Сценарии для практики QA

**Позитивные:**
1. Регистрация → логин → получить токен → GET /users/me
2. Создать товар → отфильтровать по категории → проверить что он есть
3. Создать пост → добавить комментарий → удалить пост → проверить что коммент тоже удалился
4. Создать задачу с priority=high → PATCH status=done → GET и проверить статус
5. Отправить платёж → GET stats/summary → проверить сумму

**Негативные (то что обязательно проверяет QA):**
- Логин с неверным паролем → 401
- Запрос без токена на защищённый эндпоинт → 401
- GET несуществующего ID → 404
- POST задачи с priority="urgent" (невалидное значение) → 400
- Платёж самому себе → 400
- Платёж на несуществующего юзера → 404
- Обновить чужой пост → 403
- Refund платежа который уже refunded → 400

## Swagger UI
`{{base_url}}/docs` — интерактивная документация, можно тестировать прямо в браузере.
