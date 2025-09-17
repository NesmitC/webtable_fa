# main.py
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
import asyncpg
import os
import secrets
import hashlib
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан в .env")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не задан в .env")

app = FastAPI(title="WebTable FA")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Инициализация сериализатора для сессий ---
serializer = URLSafeTimedSerializer(SECRET_KEY)


# --- Middleware для загрузки сессии ---
@app.middleware("http")
async def load_session(request: Request, call_next):
    session_cookie = request.cookies.get("session")
    request.state.session = {}
    if session_cookie:
        try:
            request.state.session = serializer.loads(session_cookie, max_age=3600)  # 1 час
        except Exception:
            pass  # Игнорируем невалидные куки
    response = await call_next(request)
    return response

# --- Функция для сохранения сессии ---
def save_session(response: Response, session_data: dict):
    session_cookie = serializer.dumps(session_data)
    response.set_cookie(
        key="session",
        value=session_cookie,
        httponly=True,
        max_age=3600,
        samesite="Lax"
    )

# --- Startup ---
@app.on_event("startup")
async def startup():
    try:
        system_db_url = DATABASE_URL.replace("/webtable_fa", "/postgres")
        system_conn = await asyncpg.connect(system_db_url)

        try:
            await system_conn.execute("CREATE DATABASE webtable_fa")
            print("✅ База 'webtable_fa' создана")
        except asyncpg.exceptions.DuplicateDatabaseError:
            print("✅ База 'webtable_fa' уже существует")
        finally:
            await system_conn.close()

        app.state.db = await asyncpg.connect(DATABASE_URL)

        await app.state.db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                value VARCHAR(100) NOT NULL
            )
        """)

        await app.state.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_confirmed BOOLEAN DEFAULT FALSE,
                confirm_token TEXT,
                name VARCHAR(100),
                surname VARCHAR(100),
                class VARCHAR(50),
                telegram VARCHAR(255)
            )
        """)

        # Добавляем поля, если их нет
        for column in ["name", "surname", "class", "telegram"]:
            try:
                await app.state.db.execute(f"ALTER TABLE users ADD COLUMN {column} VARCHAR(255)")
            except asyncpg.exceptions.DuplicateColumnError:
                pass

        print("✅ Таблицы готовы")

    except Exception as e:
        print(f"❌ ОШИБКА В STARTUP: {e}")
        raise

# --- Shutdown ---
@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "db"):
        await app.state.db.close()

# --- Главная страница ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    html_content = Path("templates/index.html").read_text(encoding="utf-8")

    # Проверяем, залогинен ли пользователь
    if request.state.session.get("username"):
        username = request.state.session["username"]
        html_content = html_content.replace(
            '<div id="welcome-message" style="display: none;',
            '<div id="welcome-message" style="display: block;'
        )
        html_content = html_content.replace("ученик", username)
        html_content = html_content.replace(
            '<span id="auth-buttons">',
            f'''
            <span id="auth-buttons">
                <button id="btn-lk">ЛК</button>
                <button id="btn-logout">Выйти</button>
            '''
        )
    else:
        html_content = html_content.replace(
            '<span id="auth-buttons">',
            '''
            <span id="auth-buttons">
                <button id="btn-register">Зарегистрироваться</button>
                <button id="btn-login" style="margin-left:10px;">Войти</button>
            </span>
            '''
        )

    return html_content

# --- Отправка email ---
def send_confirmation_email(email: str, token: str):
    subject = "Подтвердите ваш email — Нейростат"
    confirm_url = f"http://localhost:8000/api/confirm/{token}"
    body = f"""
    Здравствуйте!

    Вы зарегистрировались в Нейростат.
    Для подтверждения email перейдите по ссылке:

    {confirm_url}

    С уважением,
    Команда Нейростат
    """

    msg = MIMEMultipart()
    msg["From"] = os.getenv("MAIL_DEFAULT_SENDER")
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT")), context=context) as server:
        server.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
        server.sendmail(os.getenv("MAIL_DEFAULT_SENDER"), email, msg.as_string())

# --- Регистрация ---
@app.post("/api/register")
async def register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = app.state.db
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    token = secrets.token_urlsafe(32)

    try:
        await conn.execute("""
            INSERT INTO users (username, email, password_hash, confirm_token)
            VALUES ($1, $2, $3, $4)
        """, username, email, password_hash, token)
    except asyncpg.exceptions.UniqueViolationError:
        return {"error": "Пользователь с таким логином или email уже существует"}

    try:
        send_confirmation_email(email, token)
        return {"message": "Регистрация успешна. Проверьте почту для подтверждения."}
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return {"error": "Не удалось отправить письмо. Попробуйте позже."}

# --- Подтверждение email ---
@app.get("/api/confirm/{token}")
async def confirm_email(token: str, response: Response):
    conn = app.state.db
    user = await conn.fetchrow("SELECT id, username FROM users WHERE confirm_token = $1", token)
    if not user:
        return {"error": "Неверный или устаревший токен"}

    await conn.execute(
        "UPDATE users SET is_confirmed = TRUE, confirm_token = NULL WHERE id = $1",
        user["id"]
    )

    # Сохраняем пользователя в сессию
    save_session(response, {"username": user["username"]})

    # Возвращаем response
    return RedirectResponse(url="/", status_code=303)

# --- Вход ---
@app.post("/api/login")
async def login(response: Response, email: str = Form(...), password: str = Form(...)):
    conn = app.state.db
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    user = await conn.fetchrow("""
        SELECT id, username, is_confirmed
        FROM users
        WHERE email = $1 AND password_hash = $2
    """, email, password_hash)

    if not user:
        return {"error": "Неверный email или пароль"}
    if not user["is_confirmed"]:
        return {"error": "Email не подтверждён. Проверьте почту."}

    # Сохраняем пользователя в сессию
    save_session(response, {"username": user["username"]})

    # Возвращаем response
    return {
        "message": "Вход выполнен",
        "user": {"id": user["id"], "username": user["username"]}
    }

# --- Личный кабинет — получение данных ---
@app.get("/api/profile")
async def get_profile(request: Request):
    username = request.state.session.get("username")
    if not username:
        return {"error": "Не авторизован"}

    conn = app.state.db
    user = await conn.fetchrow("""
        SELECT name, surname, class, telegram
        FROM users
        WHERE username = $1
    """, username)

    if not user:
        return {"error": "Пользователь не найден"}

    return {
        "name": user["name"],
        "surname": user["surname"],
        "class": user["class"],
        "telegram": user["telegram"]
    }

# --- Личный кабинет — сохранение данных ---
@app.post("/api/profile")
async def save_profile(
    request: Request,
    name: str = Form(...),
    surname: str = Form(...),
    class_: str = Form(...),
    telegram: str = Form(...)
):
    username = request.state.session.get("username")
    if not username:
        return {"error": "Не авторизован"}

    conn = app.state.db
    try:
        await conn.execute("""
            UPDATE users 
            SET name = $1, surname = $2, class = $3, telegram = $4
            WHERE username = $5
        """, name, surname, class_, telegram, username)
        return {"message": "Данные сохранены"}
    except Exception as e:
        print(f"❌ Ошибка при сохранении данных: {e}")
        return {"error": "Не удалось сохранить данные"}

# --- Выход ---
@app.post("/api/logout")
async def logout(response: Response):
    # Очищаем куку сессии
    response.delete_cookie("session")
    return {"message": "Выход выполнен"}

# --- Добавление записи ---
@app.post("/add")
async def add_item(name: str = Form(...), value: str = Form(...)):
    conn = app.state.db
    await conn.execute("INSERT INTO items (name, value) VALUES ($1, $2)", name, value)
    return {"message": "Запись добавлена"}
