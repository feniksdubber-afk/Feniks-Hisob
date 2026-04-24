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

# BAZA YO'LI (RAILWAY VOLUME)
DB_DIR = "/app/data"
if not os.path.exists(DB_DIR): os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_studio_v3.db")

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
            cursor.execute("INSERT INTO users (name, pin_code, role) VALUES ('Rejissyor', '7777', 'admin')")
        conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def safe_delete(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

def delete_later(chat_id, message_id, delay=3):
    def task():
        time.sleep(delay)
        safe_delete(chat_id, message_id)
    threading.Thread(target=task).start()

def get_user(tg_id):
    with db_lock:
        cursor.execute('''
            SELECT u.id, u.name, u.balance, u.card_number, u.role, u.pin_code 
            FROM users u
            JOIN active_logins al ON u.id = al.user_id
            WHERE al.telegram_id = ?
        ''', (tg_id,))
        return cursor.fetchone()

# ==========================================
# 4. KIRISH TIZIMI (START / PIN)
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def start_handler(message):
    user = get_user(message.chat.id)
    safe_delete(message.chat.id, message.message_id)
    
    if user:
        show_main_menu(message.chat.id, user[1], user[2])
    else:
        text = "<b>FENIKS STUDIO</b>\n━━━━━━━━━━━━━\n🛡 <b>Tizimga kirish:</b>\nDavom etish uchun maxsus <b>PIN-kodni</b> kiriting.\n\n<i>Kodingiz bo'lmasa, adminga murojaat qiling.</i>"
        msg = bot.send_message(message.chat.id, text)
        bot.register_next_step_handler(msg, process_pin_login, msg.message_id)

def process_pin_login(message, prompt_id):
    safe_delete(message.chat.id, message.message_id)
    safe_delete(message.chat.id, prompt_id)
    
    if message.text and message.text.startswith('/'): return start_handler(message)
    
    pin = message.text.strip() if message.text else ""
    with db_lock:
        cursor.execute("SELECT id, name, balance, role FROM users WHERE pin_code = ?", (pin,))
        user_data = cursor.fetchone()
        if user_data:
            cursor.execute("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (message.chat.id, user_data[0]))
            conn.commit()

    if user_data:
        bot.send_message(message.chat.id, f"✅ Salom, {user_data[1]}!")
        show_main_menu(message.chat.id, user_data[1], user_data[2])
    else:
        err = bot.send_message(message.chat.id, "❌ PIN-kod noto'g'ri!")
        delete_later(message.chat.id, err.message_id, 3)
        start_handler(message)

@bot.message_handler(commands=['exit_login'])
def exit_handler(message):
    with db_lock:
        cursor.execute("DELETE FROM active_logins WHERE telegram_id = ?", (message.chat.id,))
        conn.commit()
    bot.send_message(message.chat.id, "👋 Tizimdan chiqdingiz.", reply_markup=ReplyKeyboardRemove())
    start_handler(message)

# ==========================================
# 5. ASOSIY MENYU (ANIMATSIYA BILAN)
# ==========================================
def show_main_menu(chat_id, name, balance, message_id=None):
    global CACHED_GIF_ID
    text = f"<b>FENIKS STUDIO TIZIMI</b> 👋\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Xodim:</b> <code>{name}</code>\n💰 <b>Hisob:</b> <code>{balance:,} so'm</code>\n━━━━━━━━━━━━━━━━━━━━"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎙 Ovoz topshirish", callback_data="menu_submit"),
        InlineKeyboardButton("👤 Shaxsiy kabinet", callback_data="menu_cabinet")
    )
    
    user = get_user(chat_id)
    if user and user[4] == 'admin':
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_main"))

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

# ==========================================
# 6. OVOZ TOPSHIRISH LOGIKASI
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "menu_submit")
def submit_voice_start(call):
    user = get_user(call.message.chat.id)
    with db_lock:
        cursor.execute('SELECT p.id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?', (user[0],))
        projects = cursor.fetchall()
    
    if not projects:
        bot.answer_callback_query(call.id, "Sizga loyiha biriktirilmagan!", show_alert=True)
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for p in projects:
        markup.add(InlineKeyboardButton(p[1], callback_data=f"selp_{p[0]}"))
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main"))
    
    bot.edit_message_caption("🎬 Loyihani tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('selp_'))
def select_project_step(call):
    pid = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, "🔢 Qism raqamini yozing:")
    bot.register_next_step_handler(msg, process_ep_num, pid, call.message.message_id)

def process_ep_num(message, pid, menu_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text or not message.text.isdigit():
        return bot.send_message(message.chat.id, "Faqat raqam yozing! /start")
    
    ep = message.text
    bot.edit_message_caption(f"📤 {ep}-qism faylini yuboring...", message.chat.id, menu_id)
    bot.register_next_step_handler(message, process_file_upload, pid, ep, menu_id)

def process_file_upload(message, pid, ep, menu_id):
    safe_delete(message.chat.id, message.message_id)
    if not (message.audio or message.voice or message.video or message.document):
        return bot.send_message(message.chat.id, "Faqat fayl yuboring! /start")

    user = get_user(message.chat.id)
    with db_lock:
        cursor.execute('SELECT up.price, p.topic_id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE p.id = ? AND up.user_id = ?', (pid, user[0]))
        p_data = cursor.fetchone()
    
    price, tid, p_name = p_data[0], p_data[1], p_data[2]
    
    # Guruhga yuborish
    caption = f"🔔 <b>YANGI ISH!</b>\n👤 {user[1]}\n🎬 {p_name} | {ep}-qism\n💰 {price:,} so'm"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Rad etish", callback_data=f"rej_{user[0]}_{price}_{p_name}_{ep}"))
    
    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id if message.voice else message.video.file_id if message.video else message.document.file_id
        bot.send_document(ADMIN_GROUP_ID, file_id, caption=caption, reply_markup=markup, message_thread_id=tid)
        
        # Balansni yangilash
        with db_lock:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user[0]))
            conn.commit()
        
        bot.edit_message_caption(f"✅ Qabul qilindi!\n+{price:,} so'm", message.chat.id, menu_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Menyu", callback_data="back_to_main")))
    except Exception as e:
        bot.send_message(message.chat.id, f"Xato: {e}")

# ==========================================
# 7. ADMIN PANEL
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_router(call):
    user = get_user(call.message.chat.id)
    if not user or user[4] != 'admin': return
    
    cmd = call.data.split('_')[1]
    if cmd == "main":
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("👥 Xodimlar", callback_data="admin_workers"),
            InlineKeyboardButton("🎬 Loyihalar", callback_data="admin_projs"),
            InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_bc"),
            InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
        )
        bot.edit_message_caption("👑 ADMIN PANEL", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif cmd == "workers":
        with db_lock:
            cursor.execute("SELECT id, name, balance FROM users WHERE role != 'admin'")
            workers = cursor.fetchall()
        markup = InlineKeyboardMarkup()
        for w in workers: markup.add(InlineKeyboardButton(f"{w[1]} ({w[2]:,})", callback_data=f"adw_{w[0]}"))
        markup.add(InlineKeyboardButton("➕ Yangi xodim", callback_data="admin_addw"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_main"))
        bot.edit_message_caption("👥 Xodimlar:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif cmd == "bc":
        msg = bot.send_message(call.message.chat.id, "📢 Xabarni yozing:")
        bot.register_next_step_handler(msg, admin_process_bc)

def admin_process_bc(message):
    with db_lock:
        cursor.execute("SELECT telegram_id FROM active_logins")
        users = cursor.fetchall()
    for u in users:
        try: bot.send_message(u[0], f"📢 <b>ADMIN:</b>\n{message.text}")
        except: pass
    bot.send_message(message.chat.id, "✅ Yuborildi.")

# ==========================================
# 8. SHAXSIY KABINET
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "menu_cabinet")
def cab_main(call):
    user = get_user(call.message.chat.id)
    text = f"👤 {user[1]}\n💳 Karta: {user[3] or 'Yo`q'}\n💰 Balans: {user[2]:,} so'm"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("💳 Karta kiritish", callback_data="cab_setcard"),
        InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="cab_setname"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
    )
    bot.edit_message_caption(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "cab_setcard")
def cab_card_start(call):
    msg = bot.send_message(call.message.chat.id, "💳 16 xonali karta raqamini yuboring:")
    bot.register_next_step_handler(msg, cab_card_save)

def cab_card_save(message):
    card = message.text.replace(" ", "")
    if len(card) == 16 and card.isdigit():
        user = get_user(message.chat.id)
        with db_lock:
            cursor.execute("UPDATE users SET card_number = ? WHERE id = ?", (card, user[0]))
            conn.commit()
        bot.send_message(message.chat.id, "✅ Saqlandi! /start")
    else:
        bot.send_message(message.chat.id, "❌ Xato karta! /start")

# ==========================================
# 9. BACK HANDLERS
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_main(call):
    user = get_user(call.message.chat.id)
    show_main_menu(call.message.chat.id, user[1], user[2], call.message.message_id)

# ==========================================
# 10. SERVER VA POLLING
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Feniks Studio is running...")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), SimpleHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Bot ishga tushdi...")
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except: time.sleep(5)
