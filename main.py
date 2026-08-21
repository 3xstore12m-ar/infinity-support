import os
import logging
import threading
import discord
from discord.ext import commands
from flask import Flask
import google.generativeai as genai

# ------------------ Logging ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------ Environment Variables ------------------
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in environment variables.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in environment variables.")

# ------------------ Google Gemini Setup ------------------
genai.configure(api_key=GEMINI_API_KEY)
# Use a model that supports system instructions if available, otherwise we will prepend.
# For Gemini 1.5 Pro/Flash you can pass system_instruction directly, but for 1.0 we simulate.
# We'll use a generic model name that works on most accounts.
MODEL_NAME = "gemini-1.5-flash"  # or "gemini-pro" – choose one that works for you
model = genai.GenerativeModel(MODEL_NAME)

# System prompt – the assistant is a friendly, concise support agent for a Saudi game-account store.
SYSTEM_PROMPT = (
    "أنت مساعد دعم فني ودود ومختص لمتجر حسابات ألعاب في السعودية. "
    "أجب باللهجة السعودية أو بالعربية الفصحى حسب السياق، وكن مفيداً ومختصراً. "
    "لا تقدم أي معلومات غير متعلقة بالمتجر أو حسابات الألعاب. "
    "إذا طُلب منك شيء خارج نطاق عملك، اعتذر بلطف ووجّه المستخدم للتواصل مع فريق الدعم البشري."
)

# ------------------ Discord Bot Setup ------------------
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.members = True          # Optional but useful

# تم التعديل هنا لاستخدام commands.Bot بدلاً من discord.Client
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself and from other bots
    if message.author.bot:
        return

    # Only respond in channels whose name contains "ticket" (case-insensitive)
    if not message.channel.name or "ticket" not in message.channel.name.lower():
        await bot.process_commands(message)
        return

    # Optionally, you could also check for a ticket number pattern, but we keep it simple.

    # Let the user know we are processing
    async with message.channel.typing():
        try:
            # Build the prompt: system instruction + user's message
            user_content = message.content.strip()
            if not user_content:
                await message.reply("الرجاء كتابة سؤالك بوضوح.")
                return

            full_prompt = f"{SYSTEM_PROMPT}\n\nالمستخدم: {user_content}\nالمساعد:"

            # Call Gemini API
            response = model.generate_content(full_prompt)

            # Extract the reply text
            if response and response.text:
                reply = response.text.strip()
            else:
                reply = "عذراً، لم أستطع معالجة طلبك. حاول مرة أخرى."

            # If the reply is too long for Discord (2000 chars), truncate
            if len(reply) > 2000:
                reply = reply[:1997] + "..."

            await message.reply(reply)

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            # Send a clear, user‑friendly error message
            await message.reply(
                "حدث خطأ تقني مؤقت. يرجى المحاولة بعد قليل. إذا استمرت المشكلة، تواصل مع فريق الدعم البشري."
            )

    await bot.process_commands(message)

# ------------------ Flask Keep‑Alive Thread ------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running"

def run_flask():
    # Run on port 8080 as required by Render
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def start_flask():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask keep‑alive thread started on port 8080")

# ------------------ Main Entry Point ------------------
if __name__ == '__main__':
    # Start the Flask server in a background thread
    start_flask()
    # Run the Discord bot (blocking)
    bot.run(DISCORD_TOKEN)
