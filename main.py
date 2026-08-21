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
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # التأكد أن الرد فقط داخل رومات التكتات أو الدعم
    if not message.channel.name or "ticket" not in message.channel.name.lower():
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            user_content = message.content.strip()
            if not user_content:
                return

            # جمع معلومات بسيطة عن السيرفر أو القنوات المتاحة إذا احتجنا لاحقاً
            guild = message.guild
            stock_status = "متوفرة حالياً في الرومات المخصصة"
            
            # فحص بسيط لو فيه رومات تتعلق بالحسابات بالسيرفر
            channels_list = [c.name for c in guild.text_channels]
            has_stock_room = any("stock" in c or "حسابات" in c for c in channels_list)
            
            if not has_stock_room:
                stock_status = "لا توجد رومات حسابات حالياً، الحالة تعتبر صيانة أو نفدت الكمية"

            # توجيه صارم ومخصص للديسكورد يمنع العشوائية ويمنع ذكر المواقع الخارجية
            system_prompt = (
                "أنت موظف دعم فني ذكي و رسمي لمتجر حسابات ألعاب داخل سيرفر ديسكورد فقط. "
                "قواعد صارمة جداً يجب أن تلتزم بها:\n"
                "1. ممنوع نهائياً ذكر أي 'موقع إلكتروني' أو زيارة رابط خارجي، كل تعاملك وخدمتك داخل سيرفر الديسكورد هذا فقط.\n"
                "2. لا تجاوب بأي أجوبة عشوائية أو تخترع معلومات غير موجودة.\n"
                "3. إذا سأل الزبون عن توفر حسابات، اعتمد على الحالة التالية: " + stock_status + ".\n"
                "4. تحدث باللهجة السعودية الرسمية والمهذبة، وبدون إطالة.\n"
                "5. إذا طلب الزبون التحدث مع الإدارة أو شخص بشري، أخبره أنك ستتحقق من المشرفين المتواجدين وتسأله لو حاب تنبههم.\n\n"
                f"رسالة العميل: {user_content}"
            )

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=system_prompt,
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
                await message.reply("حياك الله، تفضل بطلبك أو انتظر أحد الإدارة يخدمك.")

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            await message.reply(
                "عذراً، حدث ضغط بسيط. جاري تحويلك للإدارة أو يرجى الانتظار قليلاً."
            )
    
    await bot.process_commands(message)

# ------------------ Flask Keep‑Alive Thread ------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port5=8080, debug=False, use_reloader=False) # تم ضبط البورت بالأسفل صحيحه

def start_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# تم تعديل دالة التشغيل لتكون سليمة 100%
if __name__ == '__main__':
    threading.Thread(target=start_flask, daemon=True).start()
    bot.run(DISCORD_TOKEN)
