import os
import time
import sqlite3
import threading
import hashlib
import random
import re
import telebot
from telebot.types import *

# =====================================
# CONFIG
# =====================================
TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1000000000000"))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

DB_PATH = "database.db"
lock = threading.Lock()
user_states = {}

# =====================================
# DATABASE
# =====================================
def db(q, p=(), one=False, all=False, commit=False):
    with lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(q, p)

        if commit:
            conn.commit()

        res = None
        if one:
            res = cur.fetchone()
        if all:
            res = cur.fetchall()

        conn.close()
        return res


def init_db():
    db("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER,
        name TEXT,
        login TEXT UNIQUE,
        password TEXT,
        phone TEXT UNIQUE,
        balance INTEGER DEFAULT 0,
        role TEXT DEFAULT 'worker'
    )
    """, commit=True)

    db("""
    CREATE TABLE IF NOT EXISTS active(
        telegram_id INTEGER PRIMARY KEY,
        user_id INTEGER
    )
    """, commit=True)

    db("""
    CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY,
        name TEXT,
        price INTEGER DEFAULT 0
    )
    """, commit=True)

    # admin create
    if not db("SELECT id FROM users WHERE role='admin'", one=True):
        db("INSERT INTO users(name,login,password,role) VALUES(?,?,?,?)",
           ("Admin", "admin", hash_pass("7777"), "admin"), commit=True)


# =====================================
# SECURITY
# =====================================
def hash_pass(p):
    salt = os.urandom(8).hex()
    h = hashlib.sha256((p + salt).encode()).hexdigest()
    return salt + "$" + h


def check_pass(stored, p):
    salt, h = stored.split("$")
    return hashlib.sha256((p + salt).encode()).hexdigest() == h


# =====================================
# HELPERS
# =====================================
def get_user(chat_id):
    return db("""
    SELECT u.id,u.name,u.balance,u.role
    FROM users u
    JOIN active a ON u.id=a.user_id
    WHERE a.telegram_id=?
    """, (chat_id,), one=True)


def login_user(chat_id, user_id):
    db("INSERT OR REPLACE INTO active VALUES(?,?)", (chat_id, user_id), commit=True)


def logout_user(chat_id):
    db("DELETE FROM active WHERE telegram_id=?", (chat_id,), commit=True)


# =====================================
# START
# =====================================
@bot.message_handler(commands=["start"])
def start(m):
    u = get_user(m.chat.id)
    if u:
        main_menu(m.chat.id, u[1], u[2])
    else:
        auth_menu(m.chat.id)


# =====================================
# AUTH MENU
# =====================================
def auth_menu(cid):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔐 Login", callback_data="login"),
        InlineKeyboardButton("📝 Register", callback_data="reg")
    )
    bot.send_message(cid, "Xush kelibsiz", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data in ["login", "reg"])
def auth(c):
    if c.data == "login":
        msg = bot.send_message(c.message.chat.id, "Login:")
        bot.register_next_step_handler(msg, login_step1)
    else:
        msg = bot.send_message(c.message.chat.id, "Ismingiz:")
        user_states[c.message.chat.id] = {}
        bot.register_next_step_handler(msg, reg_name)


# =====================================
# REGISTER
# =====================================
def reg_name(m):
    user_states[m.chat.id]["name"] = m.text
    msg = bot.send_message(m.chat.id, "Login:")
    bot.register_next_step_handler(msg, reg_login)


def reg_login(m):
    if db("SELECT id FROM users WHERE login=?", (m.text,), one=True):
        return bot.send_message(m.chat.id, "Band login")

    user_states[m.chat.id]["login"] = m.text
    msg = bot.send_message(m.chat.id, "Parol:")
    bot.register_next_step_handler(msg, reg_pass)


def reg_pass(m):
    st = user_states[m.chat.id]
    db("INSERT INTO users(name,login,password) VALUES(?,?,?)",
       (st["name"], st["login"], hash_pass(m.text)), commit=True)

    uid = db("SELECT id FROM users WHERE login=?", (st["login"],), one=True)[0]
    login_user(m.chat.id, uid)

    bot.send_message(m.chat.id, "✅ Ro'yxatdan o'tdingiz")
    main_menu(m.chat.id, st["name"], 0)


# =====================================
# LOGIN
# =====================================
def login_step1(m):
    u = db("SELECT id,password,name FROM users WHERE login=?", (m.text,), one=True)
    if not u:
        return bot.send_message(m.chat.id, "Topilmadi")

    user_states[m.chat.id] = {"id": u[0], "pass": u[1], "name": u[2]}
    msg = bot.send_message(m.chat.id, "Parol:")
    bot.register_next_step_handler(msg, login_step2)


def login_step2(m):
    st = user_states[m.chat.id]
    if not check_pass(st["pass"], m.text):
        return bot.send_message(m.chat.id, "Xato parol")

    login_user(m.chat.id, st["id"])
    bot.send_message(m.chat.id, "✅ Kirdingiz")
    main_menu(m.chat.id, st["name"], 0)


# =====================================
# MAIN MENU
# =====================================
def main_menu(cid, name, bal):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📤 Ish yuborish", callback_data="send"),
        InlineKeyboardButton("👤 Kabinet", callback_data="cab")
    )
    bot.send_message(cid, f"{name}\nBalans: {bal}", reply_markup=kb)


# =====================================
# CABINET
# =====================================
@bot.callback_query_handler(func=lambda c: c.data in ["cab", "logout"])
def cab(c):
    if c.data == "logout":
        logout_user(c.message.chat.id)
        bot.send_message(c.message.chat.id, "Chiqdingiz")
        return auth_menu(c.message.chat.id)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚪 Logout", callback_data="logout"))
    bot.send_message(c.message.chat.id, "Kabinet", reply_markup=kb)


# =====================================
# ADMIN
# =====================================
@bot.message_handler(commands=["admin"])
def admin(m):
    u = get_user(m.chat.id)
    if not u or u[3] != "admin":
        return

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Project", callback_data="addp"))
    bot.send_message(m.chat.id, "Admin panel", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "addp")
def addp(c):
    msg = bot.send_message(c.message.chat.id, "Project nomi:")
    bot.register_next_step_handler(msg, addp2)


def addp2(m):
    db("INSERT INTO projects(name,price) VALUES(?,?)", (m.text, 1000), commit=True)
    bot.send_message(m.chat.id, "Qo'shildi")


# =====================================
# RUN
# =====================================
init_db()

print("Bot ishga tushdi...")
while True:
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("Xato:", e)
        time.sleep(5)
