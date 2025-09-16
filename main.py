# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан в .env")

app = FastAPI(title="WebTable FA")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    # Подключаемся к системной базе 'postgres' для создания новой БД
    system_db_url = DATABASE_URL.replace("/webtable_fa", "/postgres")
    system_conn = await asyncpg.connect(system_db_url)

    # Создаём базу, если её нет
    try:
        await system_conn.execute("CREATE DATABASE webtable_fa")
        print("✅ База данных 'webtable_fa' создана")
    except asyncpg.exceptions.DuplicateDatabaseError:
        print("✅ База данных 'webtable_fa' уже существует")

    await system_conn.close()

    # Подключаемся к целевой базе
    app.state.db = await asyncpg.connect(DATABASE_URL)

    # Создаём таблицу, если её нет
    await app.state.db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            value VARCHAR(100) NOT NULL
        )
    """)
    print("✅ Таблица 'items' готова")

@app.on_event("shutdown")
async def shutdown():
    await app.state.db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    conn = app.state.db
    rows = await conn.fetch("SELECT id, name, value FROM items ORDER BY id")
    return templates.TemplateResponse("index.html", {"request": request, "items": rows})

@app.post("/add")
async def add_item(name: str = Form(...), value: str = Form(...)):
    conn = app.state.db
    await conn.execute("INSERT INTO items (name, value) VALUES ($1, $2)", name, value)
    return RedirectResponse(url="/", status_code=303)