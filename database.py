import pandas as pd
import os
import random
from config import *

# 1. ASOSIY XODIMLAR BAZASINI YUKLASH (YANGILANGAN)
def load_data():
    if not os.path.exists(DB_FILE):
        if os.path.exists("feniks_v11.csv"):
            df = pd.read_csv("feniks_v11.csv")
            if "Karta" not in df.columns: df["Karta"] = "Kiritilmagan"
            if "Lavozim" not in df.columns: df["Lavozim"] = "Aktyor"
            if "Oxirgi_Loyiha" not in df.columns: df["Oxirgi_Loyiha"] = "Topshirmagan"
            if "Oxirgi_Qism" not in df.columns: df["Oxirgi_Qism"] = "-"
            
            df.loc[df["Ism"] == "Feniks", "Lavozim"] = "Admin"
            df.loc[df["Ism"] == "Tarjimon", "Lavozim"] = "Tarjimon"
            df.to_csv(DB_FILE, index=False)
        else:
            actors = ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"]
            df = pd.DataFrame({
                "Ism": actors, "Ishladi": [0]*len(actors), "To'landi": [0]*len(actors),
                "Telegram_ID": [0]*len(actors), "Parol": [str(random.randint(1000, 9999)) for _ in range(len(actors))],
                "Karta": ["Kiritilmagan"]*len(actors), "Lavozim": ["Aktyor"]*len(actors),
                "Oxirgi_Loyiha": ["Topshirmagan"]*len(actors), # YANGI USTUN
                "Oxirgi_Qism": ["-"]*len(actors)                # YANGI USTUN
            })
            df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
            df.loc[df["Ism"] == "Feniks", "Lavozim"] = "Admin"
            df.to_csv(DB_FILE, index=False)
            
    # Xavfsiz yangilash: Agar eski baza bo'lsa-yu, yangi ustunlari yo'q bo'lsa, xato bermasdan ularni qo'shadi
    df = pd.read_csv(DB_FILE)
    changed = False
    if "Oxirgi_Loyiha" not in df.columns:
        df["Oxirgi_Loyiha"] = "Topshirmagan"
        changed = True
    if "Oxirgi_Qism" not in df.columns:
        df["Oxirgi_Qism"] = "-"
        changed = True
        
    if changed:
        df.to_csv(DB_FILE, index=False)
        
    return df

# 2. LOYIHALAR BAZASINI YUKLASH
def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        df = pd.DataFrame(columns=["Loyiha", "Aktyor", "Narx"])
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

# 3. MAXSUS MENYULAR BAZASINI YUKLASH
def load_custom_menu():
    if not os.path.exists(MENU_FILE):
        df = pd.DataFrame(columns=["Tugma_Nomi", "Xabar"])
        df.to_csv(MENU_FILE, index=False)
    return pd.read_csv(MENU_FILE)

# 4. VAZIFALAR BAZASINI YUKLASH (YANGILANGAN: Xodim bo'yicha ajratilgan)
def load_tasks():
    if not os.path.exists(TASKS_FILE):
        # Qaysi xodimga kim tegishliligini ko'rsatuvchi "Kimga" ustuni qo'shildi
        df = pd.DataFrame(columns=["ID", "Matn", "Kimga"])
        df.to_csv(TASKS_FILE, index=False)
    return pd.read_csv(TASKS_FILE)

# 5. MATNLAR BAZASINI YUKLASH
def load_texts():
    if not os.path.exists(TEXTS_FILE):
        defaults = {
            "moliya": "📊 **FENIKS STUDIO UMUMIY HISOBOTI**",
            "parol": "🔑 **Xodimlar PIN-kodlari:**",
            "ovoz": "📥 **Material topshirish qo'llanmasi:**\n\nFayl yuboring, bot avtomatik loyihani so'raydi!",
            "vazifa_yoq": "🎉 Hozircha yangi vazifalar yo'q. Dam oling!",
            "vazifa_bor": "📌 **Sizga ajratilgan maxsus vazifalar:**",
            "start_admin": "👑 Xush kelibsiz, Rejissyor!",
            "start_actor": "🎧 Salom! Ishga tayyormisiz?"
        }
        df = pd.DataFrame(list(defaults.items()), columns=["Key", "Matn"])
        df.to_csv(TEXTS_FILE, index=False)
    return pd.read_csv(TEXTS_FILE)

def get_text(key):
    try: return load_texts().loc[load_texts()["Key"] == key, "Matn"].values[0]
    except: return "Matn topilmadi"

# UMUMIY SAQLASH FUNKSIYASI
def save_df(df, file):
    df.to_csv(file, index=False)

