import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
import time
import random
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. SOZLAMALAR VA KONFIGURATSIYA (Xavfsiz qilingan)
# ==========================================
# Token va Guruh ID sini Railway Variables bo'limidan oladi
TOKEN = os.environ.get('BOT_TOKEN', 'BU_YERGA_TOKEN_YOZILMAYDI')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -1003783348785))

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
CACHED_GIF_ID = None

# BAZA UCHUN SVETOFOR (HIMOYA)
db_lock = threading.Lock()

# ==========================================
# RAILWAY VOLUME UCHUN BAZA YO'LI
# ==========================================
DB_DIR = "/app/data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_studio.db")

# ==========================================
# 2. AVTOMATIK XODIM QO'SHISH RO'YXATI
# ==========================================
TAYYOR_XODIMLAR = [
    ("Umarbek", "9860170111767720", "4509"),
    ("AMIN", "4916990315067725", "7620"),
    ("Bexruz", "4916990312368134", "4679"),
    ("Komron", "5614680604909727", "5475"),
    ("Shabnam", "5614682214353536", "4305"),
    ("Kamilla", "5614682209607342", "5116"),
    ("Tarjimon", "9860030326540967", "6682"),
    ("Zilola-chan", "", "5263")
]

# ==========================================
# 3. MA'LUMOTLAR BAZASI (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    
    with db_lock:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                balance INTEGER DEFAULT 0,
                card_number TEXT,
                pin_code TEXT UNIQUE,
                role TEXT DEFAULT 'worker'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_logins (
                telegram_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                topic_id INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_projects (
                user_id INTEGER,
                project_id INTEGER,
                price INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        try: cursor.execute("ALTER TABLE user_projects ADD COLUMN price INTEGER DEFAULT 0")
        except: pass
        
        try:
            cursor.execute("SELECT id, telegram_id FROM users WHERE telegram_id IS NOT NULL")
            old_sessions = cursor.fetchall()
            for u_id, tg_id in old_sessions:
                cursor.execute("INSERT OR IGNORE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (tg_id, u_id))
        except: pass
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (name, pin_code, role) VALUES ('Rejissyor (Admin)', '7777', 'admin')")
            
        for ism, karta, pin in TAYYOR_XODIMLAR:
            try:
                cursor.execute("INSERT INTO users (name, card_number, pin_code, role) VALUES (?, ?, ?, 'worker')", (ism, karta, pin))
            except sqlite3.IntegrityError:
                pass

        conn.commit()
    return conn, cursor

conn, cursor = init_db()
admin_states = {}

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR (ZIRHLANGAN)
# ==========================================
def safe_delete(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

def delete_later(chat_id, message_id, delay=3):
    def task():
        time.sleep(delay)
        safe_delete(chat_id, message_id)
    threading.Thread(target=task).start()

def get_user(telegram_id):
    with db_lock:
        cursor.execute('''
            SELECT u.id, u.name, u.balance, u.card_number, u.role, u.pin_code 
            FROM users u
            JOIN active_logins al ON u.id = al.user_id
            WHERE al.telegram_id = ?
        ''', (telegram_id,))
        return cursor.fetchone()

# ==========================================
# YANGA FUNKSIYA: UMUMIY RASSILKA (/broadcast)
# ==========================================
@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user = get_user(message.chat.id)
    safe_delete(message.chat.id, message.message_id)
    
    if user and user[4] == 'admin':
        msg = bot.send_message(message.chat.id, "📢 <b>Barcha xodimlarga yuboriladigan xabarni yozing:</b>\n<i>(Bekor qilish uchun /cancel deb yozing)</i>")
        bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    safe_delete(message.chat.id, message.message_id)
    if message.text == '/cancel':
        ok = bot.send_message(message.chat.id, "❌ Rassilka bekor qilindi.")
        delete_later(message.chat.id, ok.message_id, 3)
        return
        
    broadcast_text = message.text
    count = 0
    with db_lock:
        cursor.execute("SELECT telegram_id FROM active_logins")
        users = cursor.fetchall()
        
    for tg in users:
        try:
            bot.send_message(tg[0], f"📢 <b>ADMINIDAN XABAR:</b>\n━━━━━━━━━━━━━━━━━━━━\n{broadcast_text}")
            count += 1
        except:
            pass
            
    ok = bot.send_message(message.chat.id, f"✅ Xabar tizimdagi faol {count} ta xodimga yuborildi.")
    delete_later(message.chat.id, ok.message_id, 5)

# ==========================================
# 5. TIZIMGA KIRISH (START) VA CHIQISH (EXIT)
# ==========================================
@bot.message_handler(commands=['exit_login'])
def exit_login_command(message):
    safe_delete(message.chat.id, message.message_id)
    with db_lock:
        cursor.execute("DELETE FROM active_logins WHERE telegram_id = ?", (message.chat.id,))
        conn.commit()
    
    text = "👋 <b>Tizimdan muvaffaqiyatli chiqdingiz.</b>\n━━━━━━━━━━━━━\n🛡 <b>Boshqa hisobga kirish:</b>\nDavom etish uchun maxsus <b>PIN-kodni</b> kiriting."
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, process_pin_code, msg.message_id)

@bot.message_handler(commands=['start'])
def start_command(message):
    user = get_user(message.chat.id)
    safe_delete(message.chat.id, message.message_id)
    
    if user:
        show_main_menu(message.chat.id, user[1], user[2])
    else:
        text = "<b>FENIKS STUDIO</b>\n━━━━━━━━━━━━━\n🛡 <b>Tizimga kirish:</b>\nDavom etish uchun maxsus <b>PIN-kodni</b> kiriting.\n\n<i>Agar kodingiz bo'lmasa, Adminga murojaat qiling.</i>"
        msg = bot.send_message(message.chat.id, text)
        bot.register_next_step_handler(msg, process_pin_code, msg.message_id)

def process_pin_code(message, prompt_msg_id):
    safe_delete(message.chat.id, message.message_id)
    safe_delete(message.chat.id, prompt_msg_id)
    
    if not message.text:
        err_msg = bot.send_message(message.chat.id, "❌ <b>Xatolik!</b> Iltimos, faqat PIN-kod (raqamlar) kiriting.")
        delete_later(message.chat.id, err_msg.message_id, 3)
        msg = bot.send_message(message.chat.id, "Davom etish uchun maxsus <b>PIN-kodni</b> kiriting.")
        bot.register_next_step_handler(msg, process_pin_code, msg.message_id)
        return

    pin = message.text.strip()
    with db_lock:
        cursor.execute("SELECT id, name, balance, role FROM users WHERE pin_code = ?", (pin,))
        user_data = cursor.fetchone()
        
        if user_data:
            cursor.execute("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?, ?)", (message.chat.id, user_data[0]))
            conn.commit()
            
    if user_data:
        show_main_menu(message.chat.id, user_data[1], user_data[2])
        if user_data[3] == 'admin':
            bot.send_message(message.chat.id, "👑 <i>Admin panelga kirish uchun /admin buyrug'ini yuboring.</i>")
    else:
        err_msg = bot.send_message(message.chat.id, "❌ <b>Xatolik!</b> PIN-kod noto'g'ri. Qaytadan /start bosing.")
        delete_later(message.chat.id, err_msg.message_id, 5)

def show_main_menu(chat_id, name, balance, message_id_to_edit=None):
    global CACHED_GIF_ID
    text = f"<b>FENIKS STUDIO TIZIMIGA XUSH KELIBSIZ!</b> 👋\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Xodim:</b> <code>{name}</code>\n💰 <b>Hisobingiz:</b> <code>{balance} so'm</code>\n━━━━━━━━━━━━━━━━━━━━\n<i>Amalni tanlang:</i>"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎙 Ovoz topshirish", callback_data="menu_submit_voice"),
        InlineKeyboardButton("👤 Shaxsiy kabinet", callback_data="menu_cabinet")
    )
    
    if message_id_to_edit:
        try: bot.edit_message_caption(chat_id=chat_id, message_id=message_id_to_edit, caption=text, reply_markup=markup)
        except: pass
    else:
        try:
            if CACHED_GIF_ID:
                bot.send_animation(chat_id, CACHED_GIF_ID, caption=text, reply_markup=markup)
            else:
                with open('feniks.mp4', 'rb') as f:
                    msg = bot.send_animation(chat_id, f, caption=text, reply_markup=markup)
                    if msg.animation: CACHED_GIF_ID = msg.animation.file_id
                    elif msg.video: CACHED_GIF_ID = msg.video.file_id
        except Exception as e:
            bot.send_message(chat_id, text + "\n\n⚠️ Diqqat: 'feniks.mp4' videoni bot papkasiga yuklang!", reply_markup=markup)

# ==========================================
# 6. REJISSYOR BOSHQRUVI (ADMIN PANEL)
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user = get_user(message.chat.id)
    safe_delete(message.chat.id, message.message_id)
    
    if user and user[4] == 'admin':
        text = "👑 <b>REJISSYOR PULTI (ADMIN PANEL)</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Kerakli bo'limni tanlang:</i>"
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("👥 Xodimlar boshqaruvi", callback_data="admin_workers"),
            InlineKeyboardButton("🎬 Loyihalar boshqaruvi", callback_data="admin_projects"),
            InlineKeyboardButton("❌ Yopish", callback_data="admin_close")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    cmd = call.data.split('_')[1]
    
    if cmd == "close":
        safe_delete(call.message.chat.id, call.message.message_id)
        
    elif cmd == "workers":
        with db_lock:
            cursor.execute("SELECT id, name, balance FROM users WHERE role != 'admin'")
            workers = cursor.fetchall()
        text = "👥 <b>XODIMLAR:</b>\n\n"
        markup = InlineKeyboardMarkup(row_width=2)
        if not workers: text += "<i>Hali xodimlar yo'q.</i>"
        else:
            for w in workers:
                text += f"👤 {w[1]} | 💰 {w[2]}\n"
                markup.add(InlineKeyboardButton(f"⚙️ {w[1]}", callback_data=f"admuser_{w[0]}"))
        markup.add(InlineKeyboardButton("➕ Yangi xodim qo'shish", callback_data="admin_addworker"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except: pass
        
    elif cmd == "addworker":
        text = "➕ <b>Yangi xodimning ismini yozing:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_workers"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except: pass
        bot.register_next_step_handler(call.message, admin_process_add_worker, call.message.message_id)

    elif cmd == "projects":
        with db_lock:
            cursor.execute("SELECT id, name FROM projects")
            projects = cursor.fetchall()
        text = "🎬 <b>LOYIHALAR:</b>\n\n"
        markup = InlineKeyboardMarkup(row_width=1)
        for p in projects:
            text += f"📌 {p[1]}\n"
            markup.add(InlineKeyboardButton(f"⚙️ {p[1]} (Sozlash / O'chirish)", callback_data=f"admproj_{p[0]}"))
        markup.add(InlineKeyboardButton("➕ Yangi loyiha yaratish", callback_data="admin_addproject"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except: pass
        
    elif cmd == "addproject":
        text = "➕ <b>Yangi loyiha nomini yozing:</b>\n<i>(Guruhda xuddi shu nom bilan avtomatik Topic ochiladi)</i>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_projects"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
        except: pass
        bot.register_next_step_handler(call.message, admin_process_add_project, call.message.message_id)

    elif cmd == "back":
        admin_panel(call.message)

def admin_process_add_worker(message, msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text:
        bot.send_message(message.chat.id, "Iltimos, faqat matn yuboring.")
        admin_callback(type('obj', (object,), {'data': 'admin_workers', 'message': type('obj', (object,), {'chat': message.chat, 'message_id': msg_id})}))
        return
        
    name = message.text
    pin = str(random.randint(1000, 9999))
    try:
        with db_lock:
            cursor.execute("INSERT INTO users (name, pin_code) VALUES (?, ?)", (name, pin))
            conn.commit()
        success = bot.send_message(message.chat.id, f"✅ <b>Xodim qo'shildi!</b>\n\n👤 Ism: {name}\n🔑 PIN-KOD: <code>{pin}</code>\n\n<i>Ushbu PIN-kodni xodimga bering.</i>")
        delete_later(message.chat.id, success.message_id, 8)
    except: pass
    admin_callback(type('obj', (object,), {'data': 'admin_workers', 'message': type('obj', (object,), {'chat': message.chat, 'message_id': msg_id})}))

@bot.callback_query_handler(func=lambda call: call.data.startswith('admuser_'))
def admin_user_menu(call):
    user_id = call.data.split('_')[1]
    with db_lock:
        cursor.execute("SELECT name, balance, card_number, pin_code FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        
    text = f"👤 <b>Xodim:</b> {u[0]}\n💰 <b>Balans:</b> {u[1]} so'm\n💳 <b>Karta:</b> <code>{u[2] or 'Kiritilmagan'}</code>\n🔑 <b>PIN:</b> {u[3]}\n\n<i>Amalni tanlang:</i>"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("💳 Maosh to'lash (Kartaga)", callback_data=f"admpay_{user_id}"),
        InlineKeyboardButton("💸 Balansni o'zgartirish (+ / -)", callback_data=f"admbal_{user_id}"),
        InlineKeyboardButton("❌ Xodimni o'chirish", callback_data=f"admdel_{user_id}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_workers")
    )
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('admdel_'))
def admin_delete_worker(call):
    user_id = call.data.split('_')[1]
    with db_lock:
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
    
    text = f"⚠️ <b>DIQQAT!</b>\n\nSiz rostdan ham <b>{u[0]}</b> ni tizimdan butunlay o'chirib tashlamoqchimisiz?\n<i>(Barcha loyihalari va balansi bazadan o'chadi)</i>"
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confdel_{user_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admuser_{user_id}")
    )
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('confdel_'))
def admin_confirm_delete(call):
    user_id = call.data.split('_')[1]
    with db_lock:
        cursor.execute("DELETE FROM active_logins WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_projects WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    
    ok = bot.send_message(call.message.chat.id, "✅ Xodim butunlay o'chirib yuborildi.")
    delete_later(call.message.chat.id, ok.message_id, 3)
    admin_callback(type('obj', (object,), {'data': 'admin_workers', 'message': call.message}))

@bot.callback_query_handler(func=lambda call: call.data.startswith('admpay_'))
def admin_pay_step1(call):
    user_id = call.data.split('_')[1]
    with db_lock:
        cursor.execute("SELECT name, balance, card_number FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
    
    if not u[2]:
        bot.answer_callback_query(call.id, "Bu xodim hali karta raqamini kiritmagan!", show_alert=True)
        return
        
    text = f"💳 <b>Maosh to'lash:</b> {u[0]}\n💰 <b>Joriy balansi:</b> {u[1]} so'm\n💳 <b>Karta raqami:</b> <code>{u[2]}</code>\n\n<i>Ushbu kartaga qancha pul tashlab bordingiz? Summani yozing (faqat raqam):</i>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admuser_{user_id}"))
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except: pass
    bot.register_next_step_handler(call.message, admin_pay_step2, user_id, u[0], u[2], call.message.message_id)

def admin_pay_step2(message, user_id, name, card, msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text or not message.text.isdigit():
        err = bot.send_message(message.chat.id, "❌ Faqat raqam yozing.")
        delete_later(message.chat.id, err.message_id, 3)
        return
        
    amount = int(message.text)
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
        conn.commit()
        cursor.execute("SELECT telegram_id FROM active_logins WHERE user_id = ?", (user_id,))
        tg_ids = cursor.fetchall()
        
    for tg in tg_ids:
        try: bot.send_message(tg[0], f"💸 <b>MAOSH TO'LANDI!</b>\n━━━━━━━━━━━━━━━━━━━━\nSizning hisobingizdan <b>{amount} so'm</b> yechildi va <code>{card}</code> raqamli kartangizga o'tkazib berildi.\n\n<i>Barakalla, ishingizda omad!</i>")
        except: pass
        
    ok = bot.send_message(message.chat.id, f"✅ {name} ning balansidan {amount} so'm yechildi va xabar yuborildi.")
    delete_later(message.chat.id, ok.message_id, 4)
    admin_user_menu(type('obj', (object,), {'data': f"admuser_{user_id}", 'message': type('obj', (object,), {'chat': message.chat, 'message_id': msg_id})}))

@bot.callback_query_handler(func=lambda call: call.data.startswith('admbal_'))
def admin_balance_step1(call):
    user_id = call.data.split('_')[1]
    text = "💸 <b>Qancha qo'shmoqchi yoki ayirmoqchisiz?</b>\n\n<i>Masalan: +50000 yoki -15000</i>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admuser_{user_id}"))
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except: pass
    bot.register_next_step_handler(call.message, admin_balance_step2, user_id, call.message.message_id)

def admin_balance_step2(message, target_user_id, msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text:
        err = bot.send_message(message.chat.id, "❌ Iltimos, faqat matn formatida kiriting.")
        delete_later(message.chat.id, err.message_id, 3)
        return

    val = message.text.replace(" ", "")
    if not (val.startswith('+') or val.startswith('-')) or not val[1:].isdigit():
        err = bot.send_message(message.chat.id, "❌ Xato format. Masalan: +10000 yoki -5000")
        delete_later(message.chat.id, err.message_id, 3)
        return
    admin_states[message.chat.id] = {'target_user': target_user_id, 'amount': int(val)}
    text = f"Qiymat: <b>{val}</b>\n\n<i>Xodimga bu haqida bildirishnoma yuborilsinmi?</i>"
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Ha (Sabab)", callback_data="admbalnotify_yes"),
        InlineKeyboardButton("❌ Yo'q", callback_data="admbalnotify_no")
    )
    try: bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text=text, reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('admbalnotify_'))
def admin_balance_step3(call):
    action = call.data.split('_')[1]
    state = admin_states.get(call.message.chat.id)
    if not state: return
    if action == "no":
        with db_lock:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (state['amount'], state['target_user']))
            conn.commit()
        ok = bot.send_message(call.message.chat.id, "✅ Balans jimgina o'zgartirildi.")
        delete_later(call.message.chat.id, ok.message_id, 3)
        admin_user_menu(type('obj', (object,), {'data': f"admuser_{state['target_user']}", 'message': call.message}))
    else:
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="📝 <b>Sababni yozing:</b>")
        except: pass
        bot.register_next_step_handler(call.message, admin_balance_step4, call.message.message_id)

def admin_balance_step4(message, msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text:
         bot.send_message(message.chat.id, "Iltimos, sababni yozma ravishda bildiring.")
         bot.register_next_step_handler(message, admin_balance_step4, msg_id)
         return

    reason = message.text
    state = admin_states.get(message.chat.id)
    
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (state['amount'], state['target_user']))
        conn.commit()
        cursor.execute("SELECT telegram_id FROM active_logins WHERE user_id = ?", (state['target_user'],))
        tg_ids = cursor.fetchall()
        
    sign = "+" if state['amount'] > 0 else ""
    for tg in tg_ids:
        try: bot.send_message(tg[0], f"🔔 <b>BALANSINGIZDA O'ZGARISH!</b>\n━━━━━━━━━━━━━━━━━━━━\nMiqdor: <code>{sign}{state['amount']} so'm</code>\nSabab: <i>{reason}</i>")
        except: pass
        
    ok = bot.send_message(message.chat.id, "✅ Balans o'zgardi va xabar ketdi.")
    delete_later(message.chat.id, ok.message_id, 3)
    admin_user_menu(type('obj', (object,), {'data': f"admuser_{state['target_user']}", 'message': type('obj', (object,), {'message_id': msg_id, 'chat': message.chat})}))

def admin_process_add_project(message, msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text:
         err = bot.send_message(message.chat.id, "❌ Iltimos, loyiha nomini matn ko'rinishida yozing.")
         delete_later(message.chat.id, err.message_id, 3)
         admin_callback(type('obj', (object,), {'data': 'admin_projects', 'message': type('obj', (object,), {'message_id': msg_id, 'chat': message.chat})}))
         return

    proj_name = message.text
    topic_id = None
    try:
        topic = bot.create_forum_topic(chat_id=ADMIN_GROUP_ID, name=proj_name)
        topic_id = topic.message_thread_id
    except Exception as e:
        err = bot.send_message(message.chat.id, f"⚠️ Topic yaratilmadi: {e}")
        delete_later(message.chat.id, err.message_id, 5)
    
    with db_lock:
        cursor.execute("INSERT INTO projects (name, topic_id) VALUES (?, ?)", (proj_name, topic_id))
        conn.commit()
        
    ok = bot.send_message(message.chat.id, f"✅ <b>Loyiha yaratildi!</b>")
    delete_later(message.chat.id, ok.message_id, 3)
    admin_callback(type('obj', (object,), {'data': 'admin_projects', 'message': type('obj', (object,), {'message_id': msg_id, 'chat': message.chat})}))

def show_cast_menu(chat_id, msg_id, proj_id):
    with db_lock:
        cursor.execute("SELECT name FROM projects WHERE id = ?", (proj_id,))
        p_name = cursor.fetchone()[0]
        cursor.execute("SELECT id, name FROM users WHERE role != 'admin'")
        users = cursor.fetchall()
        
        cast_dict = {}
        for u in users:
            cursor.execute("SELECT price FROM user_projects WHERE user_id = ? AND project_id = ?", (u[0], proj_id))
            res = cursor.fetchone()
            cast_dict[u[0]] = res[0] if res else None
            
    text = f"🎬 Loyiha: <b>{p_name}</b>\n\n<i>Aktyorni qo'shish uchun uning ismini bosing va to'lanadigan narxni belgilang:</i>"
    markup = InlineKeyboardMarkup(row_width=1)
    
    for u in users:
        price = cast_dict[u[0]]
        if price is not None: markup.add(InlineKeyboardButton(f"✅ {u[1]} ({price} so'm)", callback_data=f"togglecast_{proj_id}_{u[0]}"))
        else: markup.add(InlineKeyboardButton(f"❌ {u[1]}", callback_data=f"togglecast_{proj_id}_{u[0]}"))
        
    markup.add(InlineKeyboardButton("🗑 Loyihani o'chirish", callback_data=f"delproj_{proj_id}"))
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_projects"))
    
    try: bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('delproj_'))
def admin_delete_project(call):
    proj_id = call.data.split('_')[1]
    with db_lock:
        cursor.execute("SELECT name FROM projects WHERE id = ?", (proj_id,))
        p_name = cursor.fetchone()[0]
    
    text = f"⚠️ <b>DIQQAT!</b>\n\nRostdan ham <b>{p_name}</b> loyihasini butunlay o'chirib tashlamoqchimisiz?\n<i>(Barcha aktyorlarning bu loyihaga bog'liqligi tozalanadi)</i>"
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confdelproj_{proj_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admproj_{proj_id}")
    )
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('confdelproj_'))
def admin_confirm_delete_project(call):
    proj_id = call.data.split('_')[1]
    
    with db_lock:
        cursor.execute("DELETE FROM user_projects WHERE project_id = ?", (proj_id,))
        cursor.execute("DELETE FROM projects WHERE id = ?", (proj_id,))
        conn.commit()
    
    ok = bot.send_message(call.message.chat.id, "✅ Loyiha butunlay o'chirib yuborildi.")
    delete_later(call.message.chat.id, ok.message_id, 3)
    
    admin_callback(type('obj', (object,), {'data': 'admin_projects', 'message': call.message}))

@bot.callback_query_handler(func=lambda call: call.data.startswith('admproj_') or call.data.startswith('togglecast_'))
def admin_project_cast(call):
    if call.data.startswith('admproj_'):
        proj_id = call.data.split('_')[1]
        show_cast_menu(call.message.chat.id, call.message.message_id, proj_id)
    else:
        _, proj_id, user_id = call.data.split('_')
        with db_lock:
            cursor.execute("SELECT * FROM user_projects WHERE user_id = ? AND project_id = ?", (user_id, proj_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("DELETE FROM user_projects WHERE user_id = ? AND project_id = ?", (user_id, proj_id))
                conn.commit()
            else:
                cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
                u_name = cursor.fetchone()[0]
                
        if existing:
            show_cast_menu(call.message.chat.id, call.message.message_id, proj_id)
        else:
            text = f"💰 <b>{u_name}</b> uchun bu loyihada har bir qismga qancha to'lanadi?\n<i>(Faqat raqam yozing, masalan: 40000)</i>"
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admproj_{proj_id}"))
            try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
            except: pass
            bot.register_next_step_handler(call.message, process_actor_project_price, proj_id, user_id, call.message.message_id)

def process_actor_project_price(message, proj_id, user_id, menu_msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text or not message.text.isdigit():
        err = bot.send_message(message.chat.id, "❌ Faqat raqam yozing.")
        delete_later(message.chat.id, err.message_id, 3)
        show_cast_menu(message.chat.id, menu_msg_id, proj_id)
        return
    price = int(message.text)
    
    with db_lock:
        cursor.execute("INSERT INTO user_projects (user_id, project_id, price) VALUES (?, ?, ?)", (user_id, proj_id, price))
        conn.commit()
        
    show_cast_menu(message.chat.id, menu_msg_id, proj_id)

# ==========================================
# 7. ASOSIY MENYU VA OVOZ TOPSHIRISH (XODIM)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def callback_menu(call):
    user = get_user(call.message.chat.id)
    if not user: return
    if call.data == "menu_cabinet":
        text = "👤 <b>Shaxsiy kabinet.</b> Kerakli bo'limni tanlang:"
        # SHU YERGA "ISMNI TAHRIRLASH" TUGMASI QO'SHILDI
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("📂 Loyihalarim", callback_data="cab_projects"), 
            InlineKeyboardButton("💳 Karta raqami", callback_data="cab_card"),
            InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="cab_editname"), 
            InlineKeyboardButton("💬 Adminga yozish", callback_data="cab_support"), 
            InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_main")
        )
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass
    elif call.data == "menu_main":
        show_main_menu(call.message.chat.id, user[1], user[2], call.message.message_id)
    elif call.data == "menu_submit_voice":
        with db_lock:
            cursor.execute('SELECT p.id, p.name FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?', (user[0],))
            projects = cursor.fetchall()
            
        if not projects:
            bot.answer_callback_query(call.id, "Sizda hozircha faol loyihalar yo'q.", show_alert=True)
            return
        text = "🎬 <b>Qaysi loyiha uchun ovoz muhrlayapsiz?</b>\n\n<i>Ro'yxatdan o'zingizga kerakli loyihani tanlang:</i>"
        markup = InlineKeyboardMarkup(row_width=1)
        for proj in projects: markup.add(InlineKeyboardButton(proj[1], callback_data=f"proj_{proj[0]}_{proj[1]}"))
        markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('proj_'))
def select_project(call):
    _, proj_id, proj_name = call.data.split('_', 2)
    text = "🔢 <b>Ajoyib! Endi qism raqamini yozing.</b>\n\n<i>Masalan: 12 (Faqat raqam kiriting)</i>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
    try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
    except: pass
    bot.register_next_step_handler(call.message, process_episode_number, proj_id, proj_name, call.message.message_id)

def process_episode_number(message, proj_id, proj_name, menu_msg_id):
    safe_delete(message.chat.id, message.message_id) 
    
    if not message.text or not message.text.isdigit():
        err = bot.send_message(message.chat.id, "❌ Faqat raqam kiriting.")
        delete_later(message.chat.id, err.message_id, 3)
        bot.register_next_step_handler(message, process_episode_number, proj_id, proj_name, menu_msg_id)
        return
        
    episode = message.text
    text = "📤 <b>Tayyor faylni (Audio yoki Video) shu yerga yuboring.</b>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main"))
    try: bot.edit_message_caption(chat_id=message.chat.id, message_id=menu_msg_id, caption=text, reply_markup=markup)
    except: pass
    bot.register_next_step_handler(message, process_media_file, proj_id, proj_name, episode, menu_msg_id)

def process_media_file(message, proj_id, proj_name, episode, menu_msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not (message.audio or message.voice or message.video or message.document):
        err = bot.send_message(message.chat.id, "❌ Faqat Media fayl yuboring.")
        delete_later(message.chat.id, err.message_id, 3)
        bot.register_next_step_handler(message, process_media_file, proj_id, proj_name, episode, menu_msg_id)
        return

    user = get_user(message.chat.id)
    
    with db_lock:
        cursor.execute('SELECT up.price, p.topic_id FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE p.id = ? AND up.user_id = ?', (proj_id, user[0]))
        p_data = cursor.fetchone()
        price, topic_id = p_data[0], p_data[1]
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user[0]))
        conn.commit()
    
    success_text = f"✅ <b>Fayl muvaffaqiyatli qabul qilindi!</b>\n━━━━━━━━━━━━━━━━━━━━\n🎬 <b>Loyiha:</b> <code>{proj_name}</code> | 🔢 <b>Qism:</b> <code>{episode}</code>\n💰 <b>To'lov:</b> <code>+ {price} so'm</code> hisobingizga qo'shildi!\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Bosh menyuga qaytish", callback_data="menu_main"))
    try: bot.edit_message_caption(chat_id=message.chat.id, message_id=menu_msg_id, caption=success_text, reply_markup=markup)
    except: pass

    admin_text = f"🔔 <b>YANGI ISH TOPSHIRILDI!</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Xodim:</b> <code>{user[1]}</code>\n🎬 <b>Loyiha:</b> <code>{proj_name}</code> | 🔢 <b>Qism:</b> <code>{episode}</code>\n💰 <b>To'langan summa:</b> <code>{price} so'm</code>\n"
    admin_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Rad etish (O'chirish)", callback_data=f"reject_{user[0]}_{price}_{proj_id}_{episode}"))
    
    try:
        if message.audio: bot.send_audio(ADMIN_GROUP_ID, message.audio.file_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        elif message.voice: bot.send_voice(ADMIN_GROUP_ID, message.voice.file_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        elif message.video: bot.send_video(ADMIN_GROUP_ID, message.video.file_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
        else: bot.send_document(ADMIN_GROUP_ID, message.document.file_id, caption=admin_text, reply_markup=admin_markup, message_thread_id=topic_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Fayl guruhga bormadi. Topic bilan xatolik: {e}")

# ==========================================
# 9. ADMIN RAD ETISH FUNKSIYASI 
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_submission(call):
    _, user_id, price, proj_id, episode = call.data.split('_', 4)
    user_id = int(user_id)
    price = int(price)
    
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
        conn.commit()
        cursor.execute("SELECT name FROM projects WHERE id = ?", (proj_id,))
        proj_name = cursor.fetchone()[0]
        cursor.execute("SELECT telegram_id FROM active_logins WHERE user_id = ?", (user_id,))
        tg_ids = cursor.fetchall()
        
    new_caption = call.message.caption + "\n\n❌ <b>Ushbu ish rad etildi va to'lov bekor qilindi.</b>"
    try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=new_caption)
    except: pass
    
    for tg in tg_ids:
        try: bot.send_message(tg[0], f"⚠️ <b>DIQQAT: ISHINGIZ RAD ETILDI!</b>\n━━━━━━━━━━━━━━━━━━━━\n🎬 <b>Loyiha:</b> <code>{proj_name}</code> | 🔢 <b>Qism:</b> <code>{episode}</code>\n📉 <b>Hisobingizdan {price} so'm chegirib qolindi.</b>")
        except: pass

# ==========================================
# 10. SHAXSIY KABINET (Ism tahrirlash qismi qo'shildi)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('cab_'))
def cabinet_handler(call):
    user = get_user(call.message.chat.id)
    if call.data == "cab_projects":
        with db_lock:
            cursor.execute("SELECT p.name, up.price FROM projects p JOIN user_projects up ON p.id = up.project_id WHERE up.user_id = ?", (user[0],))
            projects = cursor.fetchall()
            
        text = "📂 <b>SIZGA BIRIKTIRILGAN LOYIHALAR:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, p in enumerate(projects, 1): text += f"{i}. <code>{p[0]}</code> <i>({p[1]} so'm/qism)</i>\n"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_cabinet"))
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass

    elif call.data == "cab_card":
        if user[3]: text = f"💳 <b>Sizning joriy kartangiz:</b> <code>{user[3][:4]} **** **** {user[3][-4:]}</code>\n\n<i>Yangilash uchun yangi karta raqamini yuboring.</i>"
        else: text = "💳 <b>Sizda hali karta raqami saqlanmagan.</b>\n\n<i>16 xonali karta raqamingizni yuboring (masalan: 8600123456789012):</i>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass
        bot.register_next_step_handler(call.message, process_card_number, call.message.message_id)

    # --- YANGI: ISMNI TAHRIRLASH ---
    elif call.data == "cab_editname":
        text = "✏️ <b>Yangi ism va familiyangizni kiriting:</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass
        bot.register_next_step_handler(call.message, process_edit_name, call.message.message_id)

    elif call.data == "cab_support":
        text = "💬 <b>Rejissyorga xabaringizni yozib qoldiring.</b>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_cabinet"))
        try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except: pass
        bot.register_next_step_handler(call.message, process_support_msg, call.message.message_id)

def process_edit_name(message, menu_msg_id):
    safe_delete(message.chat.id, message.message_id)
    if not message.text:
        err = bot.send_message(message.chat.id, "❌ Iltimos, faqat matn kiriting.")
        delete_later(message.chat.id, err.message_id, 3)
        return
        
    new_name = message.text
    user = get_user(message.chat.id)
    with db_lock:
        cursor.execute("UPDATE users SET name = ? WHERE id = ?", (new_name, user[0]))
        conn.commit()
        
    ok = bot.send_message(message.chat.id, f"✅ Ismingiz muvaffaqiyatli **{new_name}** ga o'zgartirildi!")
    delete_later(message.chat.id, ok.message_id, 4)
    callback_menu(type('obj', (object,), {'data': 'menu_cabinet', 'message': type('obj', (object,), {'chat': message.chat, 'message_id': menu_msg_id})}))

def process_card_number(message, menu_msg_id):
    safe_delete(message.chat.id, message.message_id)
    
    if not message.text:
         err = bot.send_message(message.chat.id, "❌ Iltimos, karta raqamini matn shaklida kiriting.")
         delete_later(message.chat.id, err.message_id, 3)
         bot.register_next_step_handler(message, process_card_number, menu_msg_id)
         return
         
    user = get_user(message.chat.id)
    card = message.text.replace(" ", "")
    if len(card) == 16 and card.isdigit():
        with db_lock:
            cursor.execute("UPDATE users SET card_number = ? WHERE id = ?", (card, user[0]))
            conn.commit()
            
        ok = bot.send_message(message.chat.id, "✅ Karta muvaffaqiyatli saqlandi!")
        delete_later(message.chat.id, ok.message_id, 3)
        callback_menu(type('obj', (object,), {'data': 'menu_cabinet', 'message': type('obj', (object,), {'chat': message.chat, 'message_id': menu_msg_id}), 'id': 1}))
    else:
        err = bot.send_message(message.chat.id, "❌ Karta raqami 16 ta raqamdan iborat bo'lishi kerak.")
        delete_later(message.chat.id, err.message_id, 3)
        bot.register_next_step_handler(message, process_card_number, menu_msg_id)

def process_support_msg(message, menu_msg_id):
    safe_delete(message.chat.id, message.message_id)
    user = get_user(message.chat.id)
    text_prefix = f"#murojaat\n👤 <b>Xodim:</b> {user[1]}\n\n"
    if message.text: bot.send_message(ADMIN_GROUP_ID, text_prefix + message.text)
    elif message.voice: bot.send_voice(ADMIN_GROUP_ID, message.voice.file_id, caption=text_prefix)
    elif message.photo: bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=text_prefix + (message.caption or ''))
    
    ok = bot.send_message(message.chat.id, "✅ Xabaringiz Rejissyorga yetkazildi.")
    delete_later(message.chat.id, ok.message_id, 3)
    callback_menu(type('obj', (object,), {'data': 'menu_cabinet', 'message': type('obj', (object,), {'chat': message.chat, 'message_id': menu_msg_id}), 'id': 1}))

# ==========================================
# 11. RENDER UCHUN SOXTA VEB-SERVER VA ISHGA TUSHIRISH
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Feniks Bot ishlashda davom etmoqda!")

def run_dummy_server():
    # Render avtomatik beradigan portni topamiz
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"Render uchun soxta server {port}-portda ishga tushdi...")
    server.serve_forever()

# Veb-serverni alohida oqimda (thread) ishga tushiramiz
threading.Thread(target=run_dummy_server, daemon=True).start()

# ------------------------------------------
# BOTNI ISHGA TUSHIRISH (Xatolardan himoyalangan)
# ------------------------------------------
print("Kutish vaqti (Render'dagi qolib ketgan nusxalar o'lishini kutamiz)...")
time.sleep(5) 
print("Feniks Studio boti ishga tushirildi!")

while True:
    try:
        # Botni ishga tushiramiz
        bot.infinity_polling(skip_pending=True)
        break 
    except Exception as e:
        print(f"Xatolik yuz berdi (409 yoki internet): {e}")
        print("Boshqa nusxa o'chishini 10 soniya kutib, qayta ulanamiz...")
        time.sleep(10)
