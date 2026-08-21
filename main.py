import os
import logging
import threading
import discord
from discord.ext import commands
from flask import Flask
from openai import OpenAI

# ------------------ Logging ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------ Environment Variables ------------------
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in environment variables.")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

# ------------------ DeepSeek API Setup ------------------
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# System prompt – موجه النظام لدعم متجر الألعاب
SYSTEM_PROMPT = (
    "أنت مساعد دعم فني ودود ومختص لمتجر حسابات ألعاب في السعودية. "
    "أجب باللهجة السعودية أو بالعربية الفصحى حسب السياق، وكن مفيداً ومختصراً. "
    "لا تقدم أي معلومات غير متعلقة بالمتجر أو حسابات الألعاب. "
    "إذا طُلب منك شيء خارج نطاق عملك، اعتذر بلطف ووجّه المستخدم للتواصل مع فريق الدعم البشري."
)

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

    # الرد فقط داخل قنوات التذاكر التي تحتوي على كلمة ticket
    if not message.channel.name or "ticket" not in message.channel.name.lower():
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            user_content = message.content.strip()
            if not user_content:
                return

            # إرسال الطلب إلى DeepSeek
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                stream=False
            )

            reply = response.choices[0].message.content.strip()

            if len(reply) > 2000:
                reply = reply[:1997] + "..."

            await message.reply(reply)

        except Exception as e:
            logger.error(f"DeepSeek API error: {e}", exc_info=True)
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
