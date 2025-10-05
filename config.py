import os
import random
import asyncio
import aiosqlite
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_PATH = "four_letter_game.db"
MAX_ATTEMPTS = 30

# 4-letter words list
WORDS = [
    "CODE","PLAY","WORD","BOTS","GAME","CHAT","NOTE","TASK","TIME","FIRE",
    "LAMP","TREE","BOOK","KING","QUEE","FISH","MOON","STAR","FORK","COIN"
]

app = Client("four_letter_multiplayer", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------- DB setup ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            name TEXT,
            score INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            word TEXT,
            attempts INTEGER DEFAULT 0,
            hint_used INTEGER DEFAULT 0
        )""")
        await db.commit()

# ---------- helper functions ----------
def check_guess(guess, word):
    feedback = []
    for g, w in zip(guess.upper(), word.upper()):
        if g == w:
            feedback.append("✅")
        elif g in word:
            feedback.append("⚪")
        else:
            feedback.append("❌")
    return "".join(feedback)

async def ensure_user(user_id, name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (tg_id, name) VALUES (?, ?)", (user_id, name))
        await db.commit()

async def start_session(user_id):
    word = random.choice(WORDS)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO sessions (user_id, word) VALUES (?, ?)", (user_id, word))
        await db.commit()

async def get_session(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, word, attempts, hint_used FROM sessions WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row  # id, word, attempts, hint_used

async def update_session_attempts(session_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sessions SET attempts = attempts + 1 WHERE id = ?", (session_id,))
        await db.commit()

async def delete_session(session_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()

async def update_score(user_id, win=True):
    async with aiosqlite.connect(DB_PATH) as db:
        if win:
            await db.execute("UPDATE users SET score = score + 1, streak = streak + 1 WHERE tg_id = ?", (user_id,))
        else:
            await db.execute("UPDATE users SET streak = 0 WHERE tg_id = ?", (user_id,))
        await db.commit()

# ---------- start command ----------
@app.on_message(filters.command("start"))
async def start(m, c):
    await ensure_user(m.from_user.id, m.from_user.first_name)

    # Replace with your links
    DEVELOPER_LINK = "https://t.me/HYE_BABU"
    CHANNEL_LINK = "https://t.me/shizuka_bots"
    SUPPORT_GROUP_LINK = "https://t.me/shizuka_support"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Developer", url=DEVELOPER_LINK)],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("🛠 Support", url=SUPPORT_GROUP_LINK)]
    ])

    image_path = "welcome_image.jpg"  # replace with your image file path or URL
    caption = (
        "👋 *Welcome to 4-Letter Multiplayer Word Guessing Bot!*\n\n"
        "🎮 Guess the word, get feedback:\n"
        "✅ Correct letter & position\n"
        "⚪ Letter exists but wrong position\n"
        "❌ Letter not in the word\n\n"
        "Use the buttons below to contact Developer, join Channel or Support group."
    )

    await m.reply_photo(
        photo=image_path,
        caption=caption,
        parse_mode="markdown",
        reply_markup=buttons
    )

# ---------- hint command ----------
@app.on_message(filters.command("hint"))
async def hint(m, c):
    user_id = m.from_user.id
    session = await get_session(user_id)
    if not session:
        await m.reply_text("Start a game first with /play")
        return
    session_id, word, attempts, hint_used = session
    if hint_used:
        await m.reply_text("You already used your hint for this game!")
        return
    letter = random.choice(word)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sessions SET hint_used = 1 WHERE id = ?", (session_id,))
        await db.commit()
    await m.reply_text(f"💡 Hint: The word contains the letter '{letter}'.")

# ---------- leaderboard ----------
@app.on_message(filters.command("leaderboard"))
async def leaderboard(m, c):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = await cur.fetchall()
    text = "🏆 Top Players:\n" + "\n".join([f"{i+1}. {row[0]} - {row[1]}" for i, row in enumerate(rows)])
    await m.reply_text(text)

# ---------- play command ----------
@app.on_message(filters.command("play"))
async def play(m, c):
    user_id = m.from_user.id
    await ensure_user(user_id, m.from_user.first_name)
    session = await get_session(user_id)
    if session:
        await m.reply_text("You already have a game running! Start guessing.")
    else:
        await start_session(user_id)
        await m.reply_text("🎮 Game started! Guess a 4-letter word.")

# ---------- end command ----------
@app.on_message(filters.command("end"))
async def end_game(m, c):
    user_id = m.from_user.id
    session = await get_session(user_id)
    if not session:
        await m.reply_text("You don't have any active game.")
        return
    session_id, word, attempts, hint_used = session
    await delete_session(session_id)
    await update_score(user_id, win=False)
    await m.reply_text(f"❌ Game ended by user. The word was {word}. Game Over!")

# ---------- guess handling ----------
@app.on_message(filters.text & ~filters.command)
async def guess(m, c):
    user_id = m.from_user.id
    text = m.text.strip().upper()
    if len(text) != 4:
        await m.reply_text("Please guess a 4-letter word.")
        return
    session = await get_session(user_id)
    if not session:
        await m.reply_text("Start a game first with /play")
        return
    session_id, word, attempts, hint_used = session

    await update_session_attempts(session_id)
    attempts += 1

    feedback = check_guess(text, word)

    if text == word:
        await m.reply_text(f"🎉 Correct! The word was {word} in {attempts} attempts.")
        await update_score(user_id, win=True)
        await delete_session(session_id)
    elif attempts >= MAX_ATTEMPTS:
        await m.reply_text(f"❌ Maximum attempts reached! The word was {word}. Game Over!")
        await update_score(user_id, win=False)
        await delete_session(session_id)
    else:
        await m.reply_text(f"{feedback} | Attempts: {attempts}/{MAX_ATTEMPTS}")

# ---------- startup ----------
async def main():
    await init_db()
    await app.start()
    print("Bot started.")
    await idle()
    await app.stop()

if __name__ == "__main__":
    from pyrogram import idle
    asyncio.run(main())
