"""
Telegram bot — Kirim/Chiqim (Daromad/Xarajat) hisobchisi
=========================================================

Foydalanish (chatda yozish):
    +50000 Maosh          -> kirim qo'shadi
    -20000 Taksi          -> chiqim qo'shadi

Buyruqlar:
    /start    - botni boshlash
    /balance  - joriy qoldiq
    /report   - umumiy hisobot (kirim, chiqim, kategoriya bo'yicha)
    /history  - so'nggi amallar
    /reset    - barcha ma'lumotlarni tozalash (ehtiyot bo'ling!)

Ishga tushirish:
    1) pip install -r requirements.txt
    2) BOT_TOKEN muhit o'zgaruvchisini o'rnating (yoki pastda TOKEN ga yozing)
    3) python bot.py
"""

import os
import re
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ------------------------------------------------------------------
# SOZLAMALAR
# ------------------------------------------------------------------
TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")

# ------------------------------------------------------------------
# BAZA
# ------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def add_transaction(user_id: int, amount: float, category: str, ttype: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions (user_id, amount, category, type, created_at) VALUES (?,?,?,?,?)",
        (user_id, amount, category, ttype, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_balance(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) FROM transactions WHERE user_id=?",
        (user_id,),
    )
    balance = cur.fetchone()[0]
    conn.close()
    return balance


def get_totals(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='income'",
        (user_id,),
    )
    income = cur.fetchone()[0]
    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='expense'",
        (user_id,),
    )
    expense = cur.fetchone()[0]
    conn.close()
    return income, expense


def get_expense_by_category(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE user_id=? AND type='expense'
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_history(user_id: int, limit: int = 10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT amount, category, type, created_at
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def reset_user(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def fmt(n: float) -> str:
    """Raqamni chiroyli formatlash: 1234567 -> 1 234 567"""
    return f"{n:,.0f}".replace(",", " ")


# ------------------------------------------------------------------
# BUYRUQLAR
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Assalomu alaykum! 👋\n\n"
        "Men sizning kirim-chiqimingizni hisoblab boraman.\n\n"
        "📥 *Kirim qo'shish*: `+50000 Maosh`\n"
        "📤 *Chiqim qo'shish*: `-20000 Taksi`\n\n"
        "Buyruqlar:\n"
        "/balance — joriy qoldiq\n"
        "/report — to'liq hisobot\n"
        "/history — so'nggi amallar\n"
        "/reset — barcha ma'lumotlarni o'chirish"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(f"💰 Joriy qoldiq: *{fmt(balance)}* so'm", parse_mode="Markdown")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    income, expense = get_totals(user_id)
    balance = income - expense
    categories = get_expense_by_category(user_id)

    lines = [
        "📊 *Hisobot*",
        f"📥 Umumiy kirim: {fmt(income)} so'm",
        f"📤 Umumiy chiqim: {fmt(expense)} so'm",
        f"💰 Qoldiq: {fmt(balance)} so'm",
    ]

    if categories:
        lines.append("\n📂 *Chiqim kategoriyalar bo'yicha:*")
        for cat, total in categories:
            percent = (total / expense * 100) if expense else 0
            lines.append(f"  • {cat}: {fmt(total)} so'm ({percent:.0f}%)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_history(user_id, 10)
    if not rows:
        await update.message.reply_text("Hali hech qanday amal yo'q.")
        return

    lines = ["🧾 *So'nggi amallar:*"]
    for amount, category, ttype, created_at in rows:
        icon = "📥" if ttype == "income" else "📤"
        sign = "+" if ttype == "income" else "-"
        date_str = created_at.replace("T", " ")
        lines.append(f"{icon} {sign}{fmt(amount)} — {category} ({date_str})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_user(user_id)
    await update.message.reply_text("✅ Barcha ma'lumotlar tozalandi.")


# ------------------------------------------------------------------
# ODDIY XABARLARNI QAYTA ISHLASH (+summa kategoriya / -summa kategoriya)
# ------------------------------------------------------------------
TRANSACTION_RE = re.compile(r"^([+-])\s*([\d\s.,]+)\s*(.*)$")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = TRANSACTION_RE.match(text)

    if not match:
        await update.message.reply_text(
            "Tushunmadim 🤔\n"
            "Kirim uchun: `+50000 Maosh`\n"
            "Chiqim uchun: `-20000 Taksi`",
            parse_mode="Markdown",
        )
        return

    sign, amount_str, category = match.groups()
    amount_str = amount_str.replace(" ", "").replace(",", "").replace(".", "")

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("Summani to'g'ri kiriting. Masalan: +50000 Maosh")
        return

    category = category.strip() or ("Boshqa kirim" if sign == "+" else "Boshqa chiqim")
    ttype = "income" if sign == "+" else "expense"
    user_id = update.effective_user.id

    add_transaction(user_id, amount, category, ttype)
    balance = get_balance(user_id)

    icon = "📥" if ttype == "income" else "📤"
    await update.message.reply_text(
        f"{icon} {'Kirim' if ttype == 'income' else 'Chiqim'} qo'shildi: "
        f"*{fmt(amount)}* so'm — {category}\n"
        f"💰 Joriy qoldiq: *{fmt(balance)}* so'm",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------
# ASOSIY FUNKSIYA
# ------------------------------------------------------------------
def main():
    if TOKEN == "SIZNING_BOT_TOKENINGIZ":
        print("❗ BOT_TOKEN o'rnatilmagan. Muhit o'zgaruvchisi orqali bering:")
        print("   export BOT_TOKEN='123456:ABC-DEF...'")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
