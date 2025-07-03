
import logging
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# === Настройки ===

BOT_TOKEN = "7518061806:AAFbwc3UmUaYxaRd2GJtTargLA9E0mJDLgo"
ADMIN_IDS = [8064681880]  # ← замени на свой Telegram ID
CARD_NUMBER = "2200 7009 0060 1229 (т банк Михаил)"

# === База данных ===

conn = sqlite3.connect("tournaments.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    fee INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    tournament_id INTEGER,
    team TEXT DEFAULT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS winrates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    wins INTEGER
)
""")

conn.commit()

# === Логгирование ===

logging.basicConfig(level=logging.INFO)

# === Команды ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_photo(
            photo="https://i.ibb.co/4wNtnnVM/start.jpg",
            caption=(
                "👋 Привет! Я Бронебой Бот."
                "Команды"
                "/tournaments — активные турниры"
                "/winrate — статистика игроков"
            )
        )
    except:
        await update.message.reply_text(
            "👋 Привет! Я Бронебой Бот."
            "Команды:"
            "/tournaments — активные турниры"
            "/winrate — статистика игроков"
        )

async def tournaments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT * FROM tournaments")
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Нет активных турниров.")
        return

    for row in rows:
        tournament_id, name, fee = row
        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Индивидуально", callback_data=f"register_{tournament_id}_solo"),
                InlineKeyboardButton("👥 Командой", callback_data=f"register_{tournament_id}_team")
            ]
        ])
        fee_text = f"💰 Взнос: {fee}₽" if fee else "🎉 Бесплатно"
        await update.message.reply_text(
            f"🏆 Турнир: {name} {fee_text}",
            reply_markup=btn
        )

async def winrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, wins FROM winrates ORDER BY wins DESC")
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Нет данных по winrate.")
        return

    text = "🏆 Winrate игроков:"
    for username, wins in rows:
        name = f"@{username}" if username else "Без username"
        text += f"{name} — {wins} побед(ы)"
    await update.message.reply_text(text)

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Спасибо! Организатор скоро проверит оплату.")

# === Админ-панель ===

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    cursor.execute("SELECT id, name FROM tournaments")
    rows = cursor.fetchall()
    if rows:
        buttons = [[InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_tourn_{id}")] for id, name in rows]
        await update.message.reply_text("🗑 Удалить турнир:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("Нет турниров для удаления.")

    cursor.execute("SELECT id, username, wins FROM winrates")
    winrate_rows = cursor.fetchall()
    for row_id, username, wins in winrate_rows:
        user_display = f"@{username}" if username else "Без username"
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_winrate_{row_id}")]
        ])
        await update.message.reply_text(f"{user_display}: {wins} побед(ы)", reply_markup=btn)

    await update.message.reply_text(
        "⚙️ Админ-панель:"
        "/add_tournament — добавить турнир"
        "/list_players — список участников"
        "/edit_winrate — добавить/обновить победы игрока"
    )

async def add_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    await update.message.reply_text(
        "Введите название турнира и взнос через запятую:"
        "Пример:`Летний Турнир, 0` — бесплатный"
        "`Кубок, 300` — платный", parse_mode="Markdown"
    )
    context.user_data['add_tournament'] = True

async def list_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    cursor.execute("""
        SELECT r.id, r.username, t.name FROM registrations r
        JOIN tournaments t ON r.tournament_id = t.id
    """)
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Нет регистраций.")
        return

    for reg_id, username, t_name in rows:
        user_display = f"@{username}" if username else "Без username"
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"del_user_{reg_id}")]
        ])
        await update.message.reply_text(
            f"{user_display} — {t_name}",
            reply_markup=btn
        )

async def edit_winrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    await update.message.reply_text(
        "Введите имя пользователя и кол-во побед через запятую:"
        "Пример: `xret, 2`", parse_mode="Markdown"
    )
    context.user_data['edit_winrate'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('add_tournament'):
        try:
            text = update.message.text
            parts = [x.strip() for x in text.split(",")]
            name = parts[0]
            fee = int(parts[1]) if len(parts) > 1 else 0
            cursor.execute("INSERT INTO tournaments (name, fee) VALUES (?, ?)", (name, fee))
            conn.commit()
            await update.message.reply_text(f"✅ Турнир «{name}» добавлен.")
        except:
            await update.message.reply_text("⚠️ Ошибка. Формат: `название, сумма`")
        context.user_data['add_tournament'] = False

    elif context.user_data.get('edit_winrate'):
        try:
            text = update.message.text.strip()
            if 'edit_winrate_id' in context.user_data:
                winrate_id = context.user_data.pop('edit_winrate_id')
                wins = int(text)
                cursor.execute("UPDATE winrates SET wins = ? WHERE id = ?", (wins, winrate_id))
                conn.commit()
                await update.message.reply_text(f"✅ Победы обновлены: {wins}")
            else:
                username, wins = [x.strip() for x in text.split(",")]
                wins = int(wins)
                cursor.execute("INSERT INTO winrates (username, wins) VALUES (?, ?) ON CONFLICT(username) DO UPDATE SET wins = ?", (username, wins, wins))
                conn.commit()
                await update.message.reply_text(f"✅ Winrate обновлён: @{username} — {wins} побед(ы)")
        except:
            await update.message.reply_text("⚠️ Ошибка. Формат: `username, победы`")
        context.user_data['edit_winrate'] = False

async def register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data.startswith("register_"):
        parts = data.split("_")
        tournament_id = int(parts[1])
        mode = parts[2] if len(parts) > 2 else "solo"

        cursor.execute("SELECT name, fee FROM tournaments WHERE id = ?", (tournament_id,))
        tournament = cursor.fetchone()
        if not tournament:
            await query.edit_message_text("❌ Турнир не найден.")
            return

        name, fee = tournament

        if mode == "solo":
            cursor.execute("""SELECT * FROM registrations WHERE user_id = ? AND tournament_id = ?""", (user.id, tournament_id))
            if cursor.fetchone():
                await query.edit_message_text("✅ Вы уже зарегистрированы.")
                return
            cursor.execute("INSERT INTO registrations (user_id, username, tournament_id) VALUES (?, ?, ?)", (user.id, user.username or "", tournament_id))
            conn.commit()
            if fee > 0:
                await query.edit_message_text(
                    f"✅ Вы зарегистрированы на турнир: {name}!"
                    f"💰 Взнос: {fee}₽"
                    f"💳 Переведите сумму на карту:`{CARD_NUMBER}`"
                    "📸 После оплаты отправьте скрин и команду /confirm для подтверждения.",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(f"🎉 Вы зарегистрированы на турнир: {name}!")
        elif mode == "team":
            context.user_data['team_register'] = tournament_id
            await query.edit_message_text("Введите 3 username участников команды через запятую (например: `user1, user2, user3`)")

    elif data.startswith("del_tourn_"):
        tournament_id = int(data.split("_")[2])
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM registrations WHERE tournament_id = ?", (tournament_id,))
        conn.commit()
        await query.edit_message_text("❌ Турнир удалён.")

    elif data.startswith("del_user_"):
        reg_id = int(data.split("_")[2])
        cursor.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
        conn.commit()
        await query.edit_message_text("🗑️ Участник удалён.")

    elif data.startswith("edit_winrate_"):
        winrate_id = int(data.split("_")[2])
        cursor.execute("SELECT username FROM winrates WHERE id = ?", (winrate_id,))
        row = cursor.fetchone()
        if not row:
            await query.edit_message_text("❌ Запись не найдена.")
            return

        username = row[0]
        context.user_data['edit_winrate_id'] = winrate_id
        context.user_data['edit_winrate'] = True
        await query.edit_message_text(f"Введите новое значение побед для @{username} (например: `3`)", parse_mode="Markdown")

    elif context.user_data.get('team_register'):
        try:
            tournament_id = context.user_data.pop('team_register')
            usernames = [u.strip() for u in update.callback_query.message.text.split(",")]
            if len(usernames) != 3:
                await query.edit_message_text("⚠️ Нужно указать 3 username через запятую.")
                return

            team_name = "_".join(usernames)
            for u in usernames:
                cursor.execute("INSERT INTO registrations (user_id, username, tournament_id, team) VALUES (?, ?, ?, ?)",
                               (0, u, tournament_id, team_name))
            conn.commit()
            await update.callback_query.message.reply_text("✅ Команда зарегистрирована.")
        except:
            await update.callback_query.message.reply_text("⚠️ Ошибка при регистрации команды.")

# === Запуск ===

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tournaments", tournaments))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("add_tournament", add_tournament))
    app.add_handler(CommandHandler("list_players", list_players))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("winrate", winrate))
    app.add_handler(CommandHandler("edit_winrate", edit_winrate))
    app.add_handler(CallbackQueryHandler(register_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
