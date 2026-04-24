import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import threading
import time
import random
import os
import hashlib
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. SOZLAMALAR VA KONFIGURATSIYA
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', '-1000000000000'))
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
CACHED_GIF_ID = None

db_lock = threading.Lock()
user_states = {}  # Holatlar boshqaruvi

# ==========================================
# 2. XAVFSIZLIK VA PAROL SHIFRLASH
# ==========================================
def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(stored: str, password: str) -> bool:
    salt, pwd_hash = stored.split('$')
    return pwd_hash == hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

# ==========================================
# 3. MA'LUMOTLAR BAZASI (THREAD-SAFE)
# ==========================================
DB_DIR = "/app/data"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_studio.db")

def db_query(query, params=(), fetch_one=False, fetch_all=False, commit=False):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    try:
        with db_lock:
            cursor.execute(query, params)
            if commit:
                conn.commit()
            if fetch_one:                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
    finally:
        conn.close()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            name TEXT,
            login TEXT UNIQUE,
            password_hash TEXT,
            phone TEXT UNIQUE,
            balance INTEGER DEFAULT 0,
            card_number TEXT,
            pin_code TEXT,
            role TEXT DEFAULT 'worker',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_logins (
            telegram_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            topic_id INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_projects (
            user_id INTEGER,
            project_id INTEGER,
            price INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )''')
        try:
            c.execute("ALTER TABLE user_projects ADD COLUMN price INTEGER DEFAULT 0")
        except Exception:
            pass

        c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (name, login, password_hash, role) VALUES (?, ?, ?, ?)",
                      ('Rejissyor (Admin)', 'admin', hash_password('7777'), 'admin'))        
        conn.commit()
        conn.close()

init_db()

# ==========================================
# 4. AVTORIZATSIYA TIZIMI
# ==========================================
def show_auth_menu(chat_id, msg_id=None):
    text = "🎬 <b>FENIKS STUDIO</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Professional media platform tizimiga xush kelibsiz!</i>\n\n🔐 Kirish yoki ro'yxatdan o'tishni tanlang:"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("📥 Tizimga kirish", callback_data="auth_login"),
        InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="auth_register"),
        InlineKeyboardButton("🔑 Parolni tiklash", callback_data="auth_forgot")
    )
    if msg_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_command(message):
    user = db_query("SELECT u.id, u.name, u.balance FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", 
                    (message.chat.id,), fetch_one=True)
    if user:
        show_main_menu(message.chat.id, user[1], user[2])
    else:
        show_auth_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data in ['auth_login', 'auth_register', 'auth_forgot', 'auth_cancel'])
def auth_router(call):
    chat_id = call.message.chat.id
    bot.clear_step_handler(call.message)
    bot.answer_callback_query(call.id)
    
    if call.data == 'auth_cancel':
        show_auth_menu(chat_id, call.message.message_id)
        return

    if call.data == 'auth_register':
        text = "📝 <b>Ro'yxatdan o'tish</b>\n\n👤 Ismingizni kiriting (masalan: Ali Valiyev):"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="auth_cancel"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass        user_states[chat_id] = {'step': 'reg_name'}
        bot.register_next_step_handler(call.message, reg_step_handler)

    elif call.data == 'auth_login':
        text = "🔐 <b>Tizimga kirish</b>\n\n👤 Loginingizni kiriting:"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="auth_cancel"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        user_states[chat_id] = {'step': 'login_name'}
        bot.register_next_step_handler(call.message, login_step_handler)

    elif call.data == 'auth_forgot':
        text = "🔑 <b>Parolni tiklash</b>\n\nRo'yxatdan o'tgan telefon raqamingizni yuboring:"
        kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Telefon raqamni yuborish", request_contact=True))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=kb)
        except Exception:
            pass
        user_states[chat_id] = {'step': 'forgot_phone'}
        bot.register_next_step_handler(call.message, forgot_step_handler)

def reg_step_handler(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id, {})
    step = state.get('step')

    if step == 'reg_name':
        if not message.text or len(message.text.strip()) < 3:
            bot.send_message(chat_id, "❌ Ism kamida 3 ta belgidan iborat bo'lishi kerak. Qaytadan kiriting:")
            bot.register_next_step_handler(message, reg_step_handler)
            return
        state['name'] = message.text.strip()
        state['step'] = 'reg_login'
        user_states[chat_id] = state
        bot.send_message(chat_id, "✅ Qabul qilindi.\n🔑 <b>Login yarating:</b>\n(Faqat ingliz harflari, raqamlar yoki `_`, 4-20 ta belgi)")
        bot.register_next_step_handler(message, reg_step_handler)

    elif step == 'reg_login':
        login = message.text.strip()
        if not re.match(r"^[A-Za-z0-9_]{4,20}$", login):
            bot.send_message(chat_id, "❌ Login formati noto'g'ri. Qaytadan yozing:")
            bot.register_next_step_handler(message, reg_step_handler)
            return
        if db_query("SELECT id FROM users WHERE login = ?", (login,), fetch_one=True):
            bot.send_message(chat_id, "❌ Bu login band. Boshqasini tanlang:")
            bot.register_next_step_handler(message, reg_step_handler)
            return
        state['login'] = login        state['step'] = 'reg_pass'
        user_states[chat_id] = state
        bot.send_message(chat_id, "🔒 <b>Parol o'ylab toping:</b>\n(Kamida 6 ta belgi)")
        bot.register_next_step_handler(message, reg_step_handler)

    elif step == 'reg_pass':
        if len(message.text) < 6:
            bot.send_message(chat_id, "❌ Parol juda qisqa. Kamida 6 ta belgi kiriting:")
            bot.register_next_step_handler(message, reg_step_handler)
            return
        state['pass'] = message.text
        state['step'] = 'reg_pass_confirm'
        user_states[chat_id] = state
        bot.send_message(chat_id, "🔒 <b>Parolni tasdiqlang:</b>")
        bot.register_next_step_handler(message, reg_step_handler)

    elif step == 'reg_pass_confirm':
        if message.text != state['pass']:
            bot.send_message(chat_id, "❌ Parollar mos kelmadi. Qaytadan kiriting:")
            state['step'] = 'reg_pass'
            user_states[chat_id] = state
            bot.register_next_step_handler(message, reg_step_handler)
            return
        state['step'] = 'reg_phone'
        user_states[chat_id] = state
        kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Telefon raqamni yuborish", request_contact=True))
        bot.send_message(chat_id, "📞 <b>Tasdiqlash uchun Telegram kontakt yuboring:</b>", reply_markup=kb)
        bot.register_next_step_handler(message, reg_step_contact)

def reg_step_contact(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    if not state or state.get('step') != 'reg_phone':
        return
    
    if not message.contact:
        bot.send_message(chat_id, "❌ Iltimos, tugmani bosib kontakt yuboring.")
        bot.register_next_step_handler(message, reg_step_contact)
        return

    phone = message.contact.phone_number
    if db_query("SELECT id FROM users WHERE phone = ?", (phone,), fetch_one=True):
        bot.send_message(chat_id, "❌ Bu raqam allaqachon ro'yxatdan o'tgan. Boshqasini kiriting yoki admin bilan bog'laning.")
        return

    db_query("INSERT INTO users (name, login, password_hash, phone) VALUES (?, ?, ?, ?)",
             (state['name'], state['login'], hash_password(state['pass']), phone), commit=True)
    
    u_id = db_query("SELECT id FROM users WHERE login = ?", (state['login'],), fetch_one=True)[0]
    db_query("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (chat_id, u_id), commit=True)    
    user = db_query("SELECT name, balance FROM users WHERE id = ?", (u_id,), fetch_one=True)
    bot.send_message(chat_id, f"🎉 <b>Muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\nXush kelibsiz, {user[0]}!")
    del user_states[chat_id]
    show_main_menu(chat_id, user[0], user[1])

def login_step_handler(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id, {})
    step = state.get('step')

    if step == 'login_name':
        login = message.text.strip()
        user = db_query("SELECT id, password_hash, name FROM users WHERE login = ?", (login,), fetch_one=True)
        if not user:
            bot.send_message(chat_id, "❌ Login topilmadi. Qaytadan kiriting:")
            bot.register_next_step_handler(message, login_step_handler)
            return
        state['u_id'] = user[0]
        state['pwd_hash'] = user[1]
        state['name'] = user[2]
        state['step'] = 'login_pass'
        user_states[chat_id] = state
        bot.send_message(chat_id, "🔒 <b>Parolingizni kiriting:</b>")
        bot.register_next_step_handler(message, login_step_handler)

    elif step == 'login_pass':
        if not verify_password(state['pwd_hash'], message.text):
            bot.send_message(chat_id, "❌ Parol noto'g'ri. Qaytadan urinib ko'ring:")
            bot.register_next_step_handler(message, login_step_handler)
            return
        db_query("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (chat_id, state['u_id']), commit=True)
        del user_states[chat_id]
        bot.send_message(chat_id, f"✅ Xush kelibsiz, <b>{state['name']}</b>!")
        show_main_menu(chat_id, state['name'], 0)

def forgot_step_handler(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    if not message.contact:
        bot.send_message(chat_id, "❌ Iltimos, kontakt tugmasini bosing.")
        bot.register_next_step_handler(message, forgot_step_handler)
        return
    
    phone = message.contact.phone_number
    user = db_query("SELECT id, name, login FROM users WHERE phone = ?", (phone,), fetch_one=True)
    if not user:
        bot.send_message(chat_id, "❌ Bu raqam tizimda topilmadi. Iltimos, admin bilan bog'laning.")
        return
        new_pass = str(random.randint(100000, 999999))
    db_query("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_pass), user[0]), commit=True)
    bot.send_message(chat_id, f"🔑 <b>Parol tiklandi!</b>\n\n👤 {user[1]}\n🔑 Login: <code>{user[2]}</code>\n🔑 Yangi parol: <code>{new_pass}</code>\n\nTezroq /start orqali kirib, parolni o'zgartiring.")
    del user_states[chat_id]
    show_auth_menu(chat_id)

# ==========================================
# 5. ASOSIY MENYU VA SHAXSIY KABINET
# ==========================================
def show_main_menu(chat_id, name, balance, msg_id=None):
    global CACHED_GIF_ID
    text = f"<b>FENIKS STUDIO TIZIMIGA XUSH KELIBSIZ!</b> 👋\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Xodim:</b> <code>{name}</code>\n💰 <b>Hisobingiz:</b> <code>{balance} so'm</code>\n━━━━━━━━━━━━━━━━━━━━\n<i>Amalni tanlang:</i>"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎙 Ovoz topshirish", callback_data="menu_submit_voice"),
        InlineKeyboardButton("👤 Shaxsiy kabinet", callback_data="menu_cabinet")
    )
    if msg_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        try:
            if CACHED_GIF_ID:
                bot.send_animation(chat_id, CACHED_GIF_ID, caption=text, reply_markup=markup)
            else:
                with open('feniks.mp4', 'rb') as f:
                    msg = bot.send_animation(chat_id, f, caption=text, reply_markup=markup)
                    if msg.animation:
                        CACHED_GIF_ID = msg.animation.file_id
                    elif msg.video:
                        CACHED_GIF_ID = msg.video.file_id
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)

def show_cabinet_menu(chat_id):
    """Kabinet menyusini toza qayta ko'rsatish uchun yordamchi funksiya"""
    text = "👤 <b>Shaxsiy kabinet</b>"
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📂 Loyihalarim", callback_data="cab_projects"), 
        InlineKeyboardButton("💳 Karta raqami", callback_data="cab_card"),
        InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="cab_editname"), 
        InlineKeyboardButton("🔒 Parolni o'zgartirish", callback_data="cab_changepass"), 
        InlineKeyboardButton("💬 Adminga yozish", callback_data="cab_support"), 
        InlineKeyboardButton("🚪 Tizimdan chiqish", callback_data="exit_login"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_main")
    )
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))def callback_menu(call):
    user = db_query("SELECT u.id, u.name, u.balance FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", 
                    (call.message.chat.id,), fetch_one=True)
    if not user:
        return show_auth_menu(call.message.chat.id, call.message.message_id)
    
    if call.data == "menu_cabinet":
        show_cabinet_menu(call.message.chat.id)
    elif call.data == "menu_main":
        show_main_menu(call.message.chat.id, user[1], user[2], call.message.message_id)
    elif call.data == "menu_submit_voice":
        projs = db_query('SELECT p.id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?', (user[0],), fetch_all=True)
        if not projs:
            bot.answer_callback_query(call.id, "Sizda hozircha faol loyihalar yo'q.", show_alert=True)
            return
        text = "🎬 <b>Qaysi loyiha uchun ovoz topshiryapsiz?</b>"
        markup = InlineKeyboardMarkup(row_width=1)
        for p in projs:
            markup.add(InlineKeyboardButton(p[1], callback_data=f"proj_{p[0]}_{p[1]}"))
        markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data in ['exit_login', 'cab_changepass', 'cab_projects', 'cab_card', 'cab_editname', 'cab_support'])
def cabinet_handler(call):
    chat_id = call.message.chat.id
    user = db_query("SELECT u.id, u.name, u.balance, u.card_number FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", 
                    (chat_id,), fetch_one=True)
    if not user:
        return

    bot.clear_step_handler(call.message)
    
    if call.data == 'exit_login':
        db_query("DELETE FROM active_logins WHERE telegram_id = ?", (chat_id,), commit=True)
        bot.send_message(chat_id, "👋 <b>Tizimdan muvaffaqiyatli chiqdingiz.</b>")
        show_auth_menu(chat_id)
        
    elif call.data == 'cab_projects':
        projs = db_query("SELECT p.name, up.price FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?", (user[0],), fetch_all=True)
        text = "📂 <b>LOYIHALARINGIZ:</b>\n" + "\n".join([f"• {p[0]} (<i>{p[1]} so'm/qism</i>)" for p in projs]) if projs else "<i>Loyihalar yo'q.</i>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_cabinet"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass

    elif call.data == 'cab_card':        card_mask = f"<code>{user[3][:4]} **** **** {user[3][-4:]}</code>" if user[3] else "Kiritilmagan"
        text = f"💳 <b>Joriy kartangiz:</b> {card_mask}\n\n<i>Yangilash uchun 16 xonali raqamni yuboring:</i>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        bot.register_next_step_handler(call.message, process_card_number, call.message.message_id)

    elif call.data == 'cab_editname':
        text = "✏️ <b>Yangi ismingizni kiriting:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        bot.register_next_step_handler(call.message, process_edit_name, call.message.message_id)

    elif call.data == 'cab_changepass':
        text = "🔒 <b>Eski parolingizni kiriting:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        bot.register_next_step_handler(call.message, process_change_pass_step1, user[0], call.message.message_id)

    elif call.data == 'cab_support':
        text = "💬 <b>Rejissyorga xabar qoldiring:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        bot.register_next_step_handler(call.message, process_support_msg, call.message.message_id)

# ==========================================
# 6. QO'SHIMCHA STEP HANDLERS (TOZALANGAN)
# ==========================================
def process_card_number(message, menu_msg_id):
    chat_id = message.chat.id
    user = db_query("SELECT id FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", (chat_id,), fetch_one=True)
    if not user: return
    card = message.text.replace(" ", "")
    if len(card) == 16 and card.isdigit():
        db_query("UPDATE users SET card_number = ? WHERE id = ?", (card, user[0]), commit=True)
        bot.send_message(chat_id, "✅ Karta muvaffaqiyatli saqlandi!")
        show_cabinet_menu(chat_id)
    else:
        bot.send_message(chat_id, "❌ Karta raqami 16 ta raqamdan iborat bo'lishi kerak. Qaytadan yuboring:")        bot.register_next_step_handler(message, process_card_number, menu_msg_id)

def process_edit_name(message, menu_msg_id):
    chat_id = message.chat.id
    user = db_query("SELECT id FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", (chat_id,), fetch_one=True)
    if not user or not message.text: return
    db_query("UPDATE users SET name = ? WHERE id = ?", (message.text, user[0]), commit=True)
    bot.send_message(chat_id, "✅ Ismingiz muvaffaqiyatli o'zgartirildi!")
    show_cabinet_menu(chat_id)

def process_change_pass_step1(message, user_id, menu_msg_id):
    chat_id = message.chat.id
    stored_hash = db_query("SELECT password_hash FROM users WHERE id = ?", (user_id,), fetch_one=True)[0]
    if not verify_password(stored_hash, message.text):
        bot.send_message(chat_id, "❌ Eski parol noto'g'ri. Qaytadan kiriting:")
        bot.register_next_step_handler(message, process_change_pass_step1, user_id, menu_msg_id)
        return
    user_states[chat_id] = {'user_id': user_id, 'menu_msg_id': menu_msg_id}
    bot.send_message(chat_id, "🔒 <b>Yangi parolni kiriting:</b> (Kamida 6 ta belgi)")
    bot.register_next_step_handler(message, process_change_pass_step2)

def process_change_pass_step2(message):
    chat_id = message.chat.id
    if len(message.text) < 6:
        bot.send_message(chat_id, "❌ Parol juda qisqa. Qaytadan kiriting:")
        bot.register_next_step_handler(message, process_change_pass_step2)
        return
    state = user_states.get(chat_id)
    db_query("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(message.text), state['user_id']), commit=True)
    bot.send_message(chat_id, "✅ Parol muvaffaqiyatli o'zgartirildi!")
    del user_states[chat_id]
    show_cabinet_menu(chat_id)

def process_support_msg(message, menu_msg_id):
    chat_id = message.chat.id
    user = db_query("SELECT u.name FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", (chat_id,), fetch_one=True)
    text_prefix = f"#murojaat\n👤 <b>Xodim:</b> {user[0]}\n\n"
    if message.text:
        bot.send_message(ADMIN_GROUP_ID, text_prefix + message.text)
    elif message.voice:
        bot.send_voice(ADMIN_GROUP_ID, message.voice.file_id, caption=text_prefix)
    elif message.photo:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=text_prefix + (message.caption or ''))
    bot.send_message(chat_id, "✅ Xabaringiz Rejissyorga yetkazildi.")
    show_cabinet_menu(chat_id)

# ==========================================
# 7. ADMIN PANELI
# ==========================================
@bot.message_handler(commands=['admin'])def admin_panel(message):
    user = db_query("SELECT u.id, u.name, u.role FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", 
                    (message.chat.id,), fetch_one=True)
    if user and user[2] == 'admin':
        text = "👑 <b>REJISSYOR PULTI</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Kerakli bo'limni tanlang:</i>"
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("👥 Xodimlar boshqaruvi", callback_data="admin_workers"),
            InlineKeyboardButton("🎬 Loyihalar boshqaruvi", callback_data="admin_projects"),
            InlineKeyboardButton("📢 Umumiy xabar yuborish", callback_data="admin_broadcast"),
            InlineKeyboardButton("❌ Yopish", callback_data="admin_close")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    cmd = call.data.split('_')[1]
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if cmd == "close":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        
    elif cmd == "broadcast":
        text = "📢 <b>Barcha xodimlarga yuboriladigan xabarni yozing:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_close"))
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        bot.register_next_step_handler(call.message, process_broadcast)

    elif cmd == "workers":
        workers = db_query("SELECT id, name, balance, phone FROM users WHERE role != 'admin'", fetch_all=True)
        text = "👥 <b>XODIMLAR:</b>\n\n" + "\n".join([f"👤 {w[1]} | 💰 {w[2]} | 📞 {w[3]}" for w in workers]) if workers else "<i>Hali xodimlar yo'q.</i>"
        markup = InlineKeyboardMarkup(row_width=2)
        for w in workers:
            markup.add(InlineKeyboardButton(f"⚙️ {w[1]}", callback_data=f"admuser_{w[0]}"))
        markup.add(InlineKeyboardButton("➕ Yangi xodim", callback_data="admin_addworker"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass

    elif cmd == "projects":
        projs = db_query("SELECT id, name FROM projects", fetch_all=True)
        text = "🎬 <b>LOYIHALAR:</b>\n\n" + "\n".join([f"📌 {p[1]}" for p in projs]) if projs else "<i>Loyihalar yo'q.</i>"
        markup = InlineKeyboardMarkup(row_width=1)
        for p in projs:
            markup.add(InlineKeyboardButton(f"⚙️ {p[1]}", callback_data=f"admproj_{p[0]}"))        markup.add(InlineKeyboardButton("➕ Yangi loyiha", callback_data="admin_addproject"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except Exception:
            pass
        
    elif cmd == "back":
        admin_panel(call.message)

def process_broadcast(message):
    chat_id = message.chat.id
    users = db_query("SELECT telegram_id FROM active_logins", fetch_all=True)
    count = 0
    for tg in users:
        try:
            bot.send_message(tg[0], f"📢 <b>ADMINIDAN XABAR:</b>\n━━━━━━━━━━━━━━━━━━━━\n{message.text}")
            count += 1
        except Exception:
            pass
    bot.send_message(chat_id, f"✅ Xabar tizimdagi faol {count} ta xodimga yuborildi.")
    bot.register_next_step_handler(message, lambda m: None)

# ==========================================
# 8. LOYIHALAR VA OVOZ TOPSHIRISH
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('proj_'))
def select_project(call):
    _, proj_id, proj_name = call.data.split('_', 2)
    text = "🔢 <b>Qism raqamini yozing:</b>\n<i>(Masalan: 5)</i>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
    try:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except Exception:
        pass
    bot.register_next_step_handler(call.message, process_episode_number, proj_id, proj_name, call.message.message_id)

def process_episode_number(message, proj_id, proj_name, menu_msg_id):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Faqat raqam kiriting.")
        bot.register_next_step_handler(message, process_episode_number, proj_id, proj_name, menu_msg_id)
        return
    text = "📤 <b>Tayyor faylni (Audio/Video) shu yerga yuboring.</b>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
    try:
        bot.edit_message_text(chat_id=message.chat.id, message_id=menu_msg_id, text=text, reply_markup=markup)
    except Exception:
        pass
    bot.register_next_step_handler(message, process_media_file, proj_id, proj_name, message.text, menu_msg_id)
def process_media_file(message, proj_id, proj_name, episode, menu_msg_id):
    if not (message.audio or message.voice or message.video or message.document):
        bot.send_message(message.chat.id, "❌ Faqat Media fayl yuboring.")
        bot.register_next_step_handler(message, process_media_file, proj_id, proj_name, episode, menu_msg_id)
        return

    user = db_query("SELECT u.id, u.name, u.balance FROM users u JOIN active_logins al ON u.id = al.user_id WHERE al.telegram_id = ?", 
                    (message.chat.id,), fetch_one=True)
    p_data = db_query('SELECT up.price, p.topic_id FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE p.id = ? AND up.user_id = ?', 
                      (proj_id, user[0]), fetch_one=True)
    price, topic_id = p_data[0], p_data[1]
    db_query("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user[0]), commit=True)
    
    success_text = f"✅ <b>Fayl qabul qilindi!</b>\n🎬 <code>{proj_name}</code> | 🔢 <code>{episode}</code>\n💰 <code>+ {price} so'm</code>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu_main"))
    try:
        bot.edit_message_text(chat_id=message.chat.id, message_id=menu_msg_id, text=success_text, reply_markup=markup)
    except Exception:
        pass

    admin_text = f"🔔 <b>YANGI ISH!</b>\n👤 {user[1]} | 🎬 {proj_name} | 🔢 {episode}\n💰 {price} so'm"
    admin_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user[0]}_{price}_{proj_id}_{episode}"))
    try:
        media_id = (message.audio or message.voice or message.video or message.document).file_id
        if message.audio: bot.send_audio(ADMIN_GROUP_ID, media_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        elif message.voice: bot.send_voice(ADMIN_GROUP_ID, media_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        elif message.video: bot.send_video(ADMIN_GROUP_ID, media_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        else: bot.send_document(ADMIN_GROUP_ID, media_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_submission(call):
    _, user_id, price, proj_id, episode = call.data.split('_', 4)
    user_id, price = int(user_id), int(price)
    db_query("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id), commit=True)
    new_caption = call.message.caption + "\n\n❌ <b>Rad etildi va to'lov bekor qilindi.</b>"
    try:
        bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=new_caption)
    except Exception:
        pass
    tg_ids = db_query("SELECT telegram_id FROM active_logins WHERE user_id = ?", (user_id,), fetch_all=True)
    for tg in tg_ids:
        try:
            bot.send_message(tg[0], f"⚠️ <b>DIQQAT: ISHINGIZ RAD ETILDI!</b>\n🎬 {proj_id} | 🔢 {episode}\n📉 Hisobingizdan {price} so'm chegirildi.")
        except Exception:
            pass

# ==========================================
# 9. SERVER VA ISHGA TUSHIRISH# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Feniks Bot ishlashda!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), DummyHandler).serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

print("Feniks Studio Bot ishga tushdi...")
while True:
    try:
        bot.infinity_polling(skip_pending=True)
        break
    except Exception as e:
        print(f"Xatolik: {e}. 10 soniyadan keyin qayta ulanadi...")
        time.sleep(10)
