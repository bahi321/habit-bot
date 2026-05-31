import os
import json
import logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)

# ─── إعدادات ───────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN", "ضع_توكن_البوت_هنا")
DATA_FILE = "habits_data.json"

# ─── العادات اليومية ────────────────────────────────────────
HABITS = [
    {"id": "fajr",    "name": "🌅 صلاة الفجر"},
    {"id": "dhuhr",   "name": "☀️ صلاة الظهر"},
    {"id": "asr",     "name": "🌤️ صلاة العصر"},
    {"id": "maghrib", "name": "🌇 صلاة المغرب"},
    {"id": "isha",    "name": "🌙 صلاة العشاء"},
    {"id": "quran",   "name": "📖 قراءة القرآن"},
    {"id": "morning", "name": "🌿 أذكار الصباح"},
    {"id": "evening", "name": "🌙 أذكار المساء"},
    {"id": "reading", "name": "📚 قراءة عامة"},
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── قاعدة البيانات (ملف JSON) ─────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"history": {}}
    return data[uid]

def today_str():
    return date.today().isoformat()

def get_today_habits(data, user_id):
    user = get_user(data, user_id)
    today = today_str()
    if today not in user["history"]:
        user["history"][today] = {h["id"]: False for h in HABITS}
    return user["history"][today]

# ─── لوحة مفاتيح العادات ───────────────────────────────────
def build_keyboard(checked: dict):
    keyboard = []
    for habit in HABITS:
        hid = habit["id"]
        icon = "✅" if checked.get(hid) else "⬜"
        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {habit['name']}",
                callback_data=f"toggle_{hid}"
            )
        ])
    keyboard.append([
        InlineKeyboardButton("📊 تقرير الأسبوع", callback_data="weekly"),
        InlineKeyboardButton("💾 حفظ اليوم", callback_data="save_day"),
    ])
    return InlineKeyboardMarkup(keyboard)

# ─── الأوامر ────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"السلام عليكم {name} 👋\n\n"
        "أنا بوتك لتتبع العادات اليومية 📋\n\n"
        "الأوامر المتاحة:\n"
        "• /check — تشيك العادات اليومية\n"
        "• /report — تقرير الأسبوع\n"
        "• /streak — سلسلة الإنجاز\n\n"
        "سيسألك البوت كل يوم بعد صلاة العشاء 🌙"
    )

async def check_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    today = get_today_habits(data, user_id)
    save_data(data)

    done = sum(1 for v in today.values() if v)
    total = len(HABITS)
    bar = progress_bar(done, total)

    await update.message.reply_text(
        f"📋 *عاداتك اليوم — {today_str()}*\n"
        f"{bar} {done}/{total}\n\n"
        "اضغط على العادة لتحديدها ✅",
        reply_markup=build_keyboard(today),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    user_id = query.from_user.id
    action = query.data

    if action.startswith("toggle_"):
        hid = action.replace("toggle_", "")
        today = get_today_habits(data, user_id)
        today[hid] = not today.get(hid, False)
        save_data(data)

        done = sum(1 for v in today.values() if v)
        total = len(HABITS)
        bar = progress_bar(done, total)

        await query.edit_message_text(
            f"📋 *عاداتك اليوم — {today_str()}*\n"
            f"{bar} {done}/{total}\n\n"
            "اضغط على العادة لتحديدها ✅",
            reply_markup=build_keyboard(today),
            parse_mode="Markdown"
        )

    elif action == "save_day":
        today = get_today_habits(data, user_id)
        done = sum(1 for v in today.values() if v)
        total = len(HABITS)
        msg = generate_day_summary(today, done, total)
        save_data(data)
        await query.edit_message_text(msg, parse_mode="Markdown")

    elif action == "weekly":
        msg = generate_weekly_report(data, user_id)
        await query.edit_message_text(msg, parse_mode="Markdown")

# ─── تقرير يومي ─────────────────────────────────────────────
def generate_day_summary(today: dict, done: int, total: int) -> str:
    lines = [f"📅 *ملخص اليوم — {today_str()}*\n"]
    for habit in HABITS:
        icon = "✅" if today.get(habit["id"]) else "❌"
        lines.append(f"{icon} {habit['name']}")
    percent = int(done / total * 100)
    bar = progress_bar(done, total)
    lines.append(f"\n{bar}")
    lines.append(f"*الإنجاز: {done}/{total} ({percent}%)*")
    if percent == 100:
        lines.append("\n🌟 ما شاء الله! يوم مكتمل!")
    elif percent >= 70:
        lines.append("\n👍 أداء جيد، واصل!")
    else:
        lines.append("\n💪 لا تيأس، غداً فرصة جديدة!")
    return "\n".join(lines)

# ─── تقرير أسبوعي ───────────────────────────────────────────
async def report_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    msg = generate_weekly_report(data, update.effective_user.id)
    await update.message.reply_text(msg, parse_mode="Markdown")

def generate_weekly_report(data: dict, user_id: int) -> str:
    user = get_user(data, user_id)
    history = user.get("history", {})
    dates = sorted(history.keys())[-7:]

    lines = ["📊 *تقرير الأسبوع الأخير*\n"]
    total_habits = len(HABITS)

    for d in dates:
        day_data = history[d]
        done = sum(1 for v in day_data.values() if v)
        percent = int(done / total_habits * 100)
        stars = "⭐" * (done // 2)
        lines.append(f"📅 `{d}` — {done}/{total_habits} ({percent}%) {stars}")

    if not dates:
        return "لا يوجد سجل بعد، ابدأ بـ /check ✅"

    # إحصاء كل عادة
    lines.append("\n📈 *أداء كل عادة:*")
    for habit in HABITS:
        hid = habit["id"]
        count = sum(1 for d in dates if history.get(d, {}).get(hid))
        bar = "█" * count + "░" * (len(dates) - count)
        lines.append(f"{habit['name']}: [{bar}] {count}/{len(dates)}")

    return "\n".join(lines)

# ─── سلسلة الإنجاز Streak ──────────────────────────────────
async def streak_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = get_user(data, update.effective_user.id)
    history = user.get("history", {})
    dates = sorted(history.keys(), reverse=True)

    streak = 0
    for d in dates:
        day_data = history[d]
        done = sum(1 for v in day_data.values() if v)
        if done == len(HABITS):
            streak += 1
        else:
            break

    if streak == 0:
        msg = "🔥 سلسلتك: 0 يوم\nأكمل كل العادات ليوم واحد لتبدأ السلسلة!"
    else:
        fire = "🔥" * min(streak, 10)
        msg = f"{fire}\n*سلسلة الأيام المكتملة: {streak} يوم متواصل!*\n\nواصل الثبات، لا تكسر السلسلة! 💪"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── تذكير يومي تلقائي ──────────────────────────────────────
async def daily_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    for user_id in data.keys():
        try:
            today = get_today_habits(data, int(user_id))
            done = sum(1 for v in today.values() if v)
            total = len(HABITS)
            bar = progress_bar(done, total)

            await ctx.bot.send_message(
                chat_id=int(user_id),
                text=(
                    f"🌙 *تذكير المساء*\n\n"
                    f"كيف كان يومك؟ {bar} {done}/{total}\n\n"
                    "سجّل عاداتك الآن 👇"
                ),
                reply_markup=build_keyboard(today),
                parse_mode="Markdown"
            )
            save_data(data)
        except Exception as e:
            logger.error(f"Error sending reminder to {user_id}: {e}")

# ─── شريط التقدم ─────────────────────────────────────────────
def progress_bar(done: int, total: int) -> str:
    filled = int((done / total) * 10)
    return "█" * filled + "░" * (10 - filled)

# ─── تشغيل البوت ────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    # تذكير يومي الساعة 22:00 (توقيت الجزائر = UTC+1)
    job_queue: JobQueue = app.job_queue
    job_queue.run_daily(
        daily_reminder,
        time=datetime.strptime("21:00", "%H:%M").time(),  # 22:00 الجزائر = 21:00 UTC
    )

    logger.info("✅ البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
