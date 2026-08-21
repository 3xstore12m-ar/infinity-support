import os
import logging
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai

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

# ------------------ Gemini API Setup ------------------
client = genai.Client(api_key=GEMINI_API_KEY)

# ------------------ Discord Bot Setup ------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.channel.name or "ticket" not in message.channel.name.lower():
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            user_content = message.content.strip()
            if not user_content:
                return

            prompt = (
                "أنت مساعد دعم فني لمتجر حسابات ألعاب في السعودية. "
                "أجب باللهجة السعودية أو العربية الفصحى باختصار وبدون تعقيد على الرسالة التالية:\n"
                f"{user_content}"
            )

            # استخدام النموذج المطلوب: gemini-3.5-flash-lite
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )

            reply = ""
            if hasattr(response, 'text') and response.text:
                reply = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts:
                reply = response.candidates[0].content.parts[0].text.strip()

            if reply:
                if len(reply) > 2000:
                    reply = reply[:1997] + "..."
                await message.reply(reply)
            else:
                await message.reply("حياك الله، تفضل بطلبك أو تواصل مع الدعم البشري للمساعدة.")

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
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
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def start_flask():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask keep‑alive thread started on port 8080")

# ------------------ Main Entry Point ------------------
if __name__ == '__main__':
    start_flask()
    bot.run(DISCORD_TOKEN)
