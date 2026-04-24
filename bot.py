import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import sqlite3
import threading
import time
import random
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. KONFIGURATSIYA
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', '7709322312:AAH97S0tq54R-VfDCHp_X3XOf6I-pY_X5kI')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -1002447942125))

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = threading.Lock()
CACHED_GIF_ID = None

# BAZA YO'LI
DB_DIR = "/app/data"
if not os.path.exists(DB_DIR): os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_final.db")

# ==========================================
# 2. MA'LUMOTLAR BAZASI
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    with db_lock:
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT,
            balance INTEGER DEFAULT 0,
            card_number TEXT,
            pin_code TEXT UNIQUE,
            role TEXT DEFAULT 'worker',
            status TEXT DEFAULT 'active'
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_logins (
            telegram_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            topic_id INTEGER
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_projects (
            user_id INTEGER,
            project_id INTEGER,
            price INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, project_id)
        )''')
        
        # Adminni tekshirish
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (name, pin_code, role, status) VALUES ('Rejissyor', '7777', 'admin', 'active')")
        conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def safe_delete(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

def get_user(tg_id):
    with db_lock:
        cursor.execute('''
            SELECT u.id, u.name, u.balance, u.card_number, u.role, u.pin_code 
            FROM users u
            JOIN active_logins al ON u.id = al.user_id
            WHERE al.telegram_id = ? AND u.status = 'active'
        ''', (tg_id,))
        return cursor.fetchone()

# ==========================================
# 4. KIRISH VA RO'YXATDAN O'TISH
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def start_handler(message):
    user = get_user(message.chat.id)
    safe_delete(message.chat.id, message.message_id)
    
    if user:
        show_main_menu(message.chat.id, user[1], user[2])
    else:
        text = "<b>FENIKS STUDIO | TIZIM</b>\n\nAssalomu alaykum! Botdan foydalanish uchun tizimga kiring yoki ro'yxatdan o'ting."
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("🔑 Kirish (PIN)", callback_data="auth_login"),
            InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="auth_reg")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

# --- LOGIN ---
@bot.callback_query_handler(func=lambda call: call.data == "auth_login")
def login_init(call):
    msg = bot.send_message(call.message.chat.id, "🔐 <b>PIN-kodingizni kiriting:</b>")
    bot.register_next_step_handler(msg, login_process)

def login_process(message):
    if message.text and message.text.startswith('/'): return start_handler(message)
    pin = message.text.strip()
    with db_lock:
        cursor.execute("SELECT id, name, balance, status FROM users WHERE pin_code = ?", (pin,))
        user_data = cursor.fetchone()
    
    if user_data:
        if user_data[3] != 'active':
            bot.send_message(message.chat.id, "⏳ Arizangiz hali ko'rib chiqilmoqda...")
            return
        with db_lock:
            cursor.execute("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (message.chat.id, user_data[0]))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ Salom, {user_data[1]}!")
        show_main_menu(message.chat.id, user_data[1], user_data[2])
    else:
        bot.send_message(message.chat.id, "❌ PIN-kod noto'g'ri!")

# --- REGISTRATION ---
@bot.callback_query_handler(func=lambda call: call.data == "auth_reg")
def reg_init(call):
    msg = bot.send_message(call.message.chat.id, "👤 <b>Ism va familiyangizni yozing:</b>")
    bot.register_next_step_handler(msg, reg_step_name)

def reg_step_name(message):
    name = message.text.strip()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    msg = bot.send_message(message.chat.id, f"Salom {name}, endi telefon raqamingizni yuboring:", reply_markup=markup)
    bot.register_next_step_handler(msg, reg_step_phone, name)

def reg_step_phone(message, name):
    if not message.contact:
        bot.send_message(message.chat.id, "Iltimos, tugmani bosib raqamingizni yuboring.")
        return start_handler(message)
    
    phone = message.contact.phone_number
    # Yangi foydalanuvchini 'pending' (kutilmoqda) holatida yaratish
    pin = str(random.randint(1000, 9999))
    with db_lock:
        cursor.execute("INSERT INTO users (name, phone, pin_code, status) VALUES (?, ?, ?, 'pending')", (name, phone, pin))
        conn.commit()
        new_id = cursor.lastrowid

    bot.send_message(message.chat.id, "✅ Arizangiz adminlarga yuborildi. Iltimos, tasdiqlashlarini kuting.", reply_markup=ReplyKeyboardRemove())
    
    # Adminga xabar
    admin_markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_ok_{new_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_no_{new_id}")
    )
    bot.send_message(ADMIN_GROUP_ID, f"🆕 <b>YANGI ARIZA:</b>\n👤 {name}\n📞 {phone}\n🔑 PIN: {pin}", reply_markup=admin_markup)

# --- ADMIN APPROVAL ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_approval(call):
    action, uid = call.data.split('_')[1], call.data.split('_')[2]
    if action == "ok":
        with db_lock:
            cursor.execute("UPDATE users SET status = 'active' WHERE id = ?", (uid,))
            cursor.execute("SELECT name, pin_code FROM users WHERE id = ?", (uid,))
            u = cursor.fetchone()
            conn.commit()
        bot.edit_message_text(f"✅ {u[0]} tasdiqlandi. PIN: {u[1]}", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("❌ Rad etildi.", call.message.chat.id, call.message.message_id)

# ==========================================
# 5. ASOSIY MENYU VA OVOZ TOPSHIRISH
# ==========================================
def show_main_menu(chat_id, name, balance, message_id=None):
    global CACHED_GIF_ID
    text = f"<b>FENIKS STUDIO</b> 👋\n━━━━━━━━━━━━━━━━━━━━\n👤 {name}\n💰 Balans: {balance:,} so'm\n━━━━━━━━━━━━━━━━━━━━"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎙 Ovoz topshirish", callback_data="btn_submit"),
        InlineKeyboardButton("👤 Kabinet", callback_data="btn_cab")
    )
    
    user = get_user(chat_id)
    if user and user[4] == 'admin':
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))

    if message_id:
        try: bot.edit_message_caption(text, chat_id, message_id, reply_markup=markup)
        except: bot.send_message(chat_id, text, reply_markup=markup)
    else:
        try:
            if CACHED_GIF_ID:
                bot.send_animation(chat_id, CACHED_GIF_ID, caption=text, reply_markup=markup)
            else:
                with open('feniks.mp4', 'rb') as f:
                    msg = bot.send_animation(chat_id, f, caption=text, reply_markup=markup)
                    CACHED_GIF_ID = msg.animation.file_id
        except:
            bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "btn_submit")
def submit_voice(call):
    user = get_user(call.message.chat.id)
    with db_lock:
        cursor.execute('SELECT p.id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?', (user[0],))
        projects = cursor.fetchall()
    
    if not projects:
        bot.answer_callback_query(call.id, "Loyiha biriktirilmagan!", show_alert=True)
        return

    markup = InlineKeyboardMarkup()
    for p in projects: markup.add(InlineKeyboardButton(p[1], callback_data=f"work_{p[0]}"))
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu"))
    bot.edit_message_caption("🎬 Loyihani tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('work_'))
def work_ep(call):
    pid = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, "🔢 Qism raqamini yozing:")
    bot.register_next_step_handler(msg, process_upload, pid, call.message.message_id)

def process_upload(message, pid, menu_id):
    safe_delete(message.chat.id, message.message_id)
    ep = message.text
    bot.edit_message_caption(f"📤 {ep}-qism faylini yuboring...", message.chat.id, menu_id)
    bot.register_next_step_handler(message, save_work, pid, ep, menu_id)

def save_work(message, pid, ep, menu_id):
    safe_delete(message.chat.id, message.message_id)
    user = get_user(message.chat.id)
    with db_lock:
        cursor.execute('SELECT up.price, p.topic_id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE p.id = ? AND up.user_id = ?', (pid, user[0]))
        p_data = cursor.fetchone()
    
    price, tid, p_name = p_data[0], p_data[1], p_data[2]
    
    # Guruhga
    caption = f"🔔 <b>YANGI ISH!</b>\n👤 {user[1]}\n🎬 {p_name} | {ep}-qism\n💰 {price:,} so'm"
    try:
        f_id = message.audio.file_id if message.audio else message.voice.file_id if message.voice else message.video.file_id if message.video else message.document.file_id
        bot.send_document(ADMIN_GROUP_ID, f_id, caption=caption, message_thread_id=tid)
        with db_lock:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user[0]))
            conn.commit()
        bot.send_message(message.chat.id, "✅ Ish qabul qilindi!")
    except:
        bot.send_message(message.chat.id, "❌ Xato! Fayl yubormadingiz yoki guruhda Topic xatosi.")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_home(call):
    user = get_user(call.message.chat.id)
    show_main_menu(call.message.chat.id, user[1], user[2], call.message.message_id)

# ==========================================
# 6. SERVER
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Feniks Bot is Active")

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), SimpleHandler).serve_forever(), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
