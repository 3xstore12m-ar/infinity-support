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

# ذاكرة مؤقتة لحفظ سياق المحادثة لكل تكت
channel_histories = {}

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # التفاعل فقط داخل رومات التكتات
    if not message.channel.name or "ticket" not in message.channel.name.lower():
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            user_content = message.content.strip()
            if not user_content:
                return

            channel_id = message.channel.id
            guild = message.guild

            # فحص رومات قسم المنتجات وقراءة آخر المحتوى لمعرفة الحالة الدقيقة
            product_status_info = "لا توجد رومات منتجات واضحة."
            for channel in guild.text_channels:
                if "قسم-المنتجات" in channel.name or "stock" in channel.name:
                    try:
                        async for hist_msg in channel.history(limit=3):
                            if "جاري العمل عليها" in hist_msg.content:
                                product_status_info = f"رومات المنتجات موجودة ({channel.name}) ولكن حالتها حالياً: جاري العمل عليها وتجهيزها."
                                break
                            elif hist_msg.content:
                                product_status_info = f"رومات المنتجات موجودة ({channel.name}) وتحتوي على تحديثات."
                    except Exception:
                        pass

            # إدارة ذاكرة المحادثة للتكت الحالي
            if channel_id not in channel_histories:
                channel_histories[channel_id] = []

            channel_histories[channel_id].append(f"الزبون: {user_content}")
            if len(channel_histories[channel_id]) > 10:
                channel_histories[channel_id].pop(0)

            history_text = "\n".join(channel_histories[channel_id])

            # التعليمات الصارمة للبوت (شاملة لجميع أنواع الحسابات العامة وليس الألعاب فقط)
            system_prompt = (
                "أنت موظف دعم فني ذكي ورسمي لمتجر حسابات عامة وخدمات رقمية داخل سيرفر ديسكورد فقط.\n"
                "قواعد صارمة جداً:\n"
                "1. ممنوع نهائياً ذكر أي 'موقع إلكتروني' أو زيارة رابط خارجي خارج الديسكورد.\n"
                "2. لا تجاوب بأي أجوبة عشوائية. حالة المنتجات الحقيقية في السيرفر هي: " + product_status_info + "\n"
                "3. تحدث باللهجة السعودية الرسمية والمهذبة، وبدون إطالة.\n"
                "4. تذكر سياق المحادثة السابقة بينك وبينه تماماً.\n"
                "5. إذا طلب الزبون التحدث مع الإدارة أو الدعم الفني بشدة، أو وافق على أن يكلمه أحد، انهِ ردك بكلمة [CALL_ADMIN] في نهاية الجملة واطلب منه يكتب تفاصيل مشكلته ليراها المشرفون.\n\n"
                f"سجل المحادثة السابقة:\n{history_text}\n\n"
                "رد على آخر رسالة للزبون بناءً على التعليمات السابقة:"
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

            # التحقق إذا طلب البوت استدعاء الإدارة
            need_admin_call = False
            if "[CALL_ADMIN]" in reply:
                need_admin_call = True
                reply = reply.replace("[CALL_ADMIN]", "").strip()

            if reply:
                if len(reply) > 2000:
                    reply = reply[:1997] + "..."
                
                channel_histories[channel_id].append(f"البوت: {reply}")
                await message.reply(reply)

                # إذا وافق الزبون، يقوم البوت بمنشن رتبة الدعم الفني المخصصة في السيرفر
                if need_admin_call:
                    target_role_name = "support" # اسم الرتبة المخصصة للدعم الفني
                    role_to_mention = discord.utils.get(guild.roles, name=target_role_name)
                    
                    if not role_to_mention:
                        role_to_mention = discord.utils.get(guild.roles, name="الدعم الفني")

                    if role_to_mention:
                        await message.channel.send(f"🚨 تنبيه لفريق الدعم: {role_to_mention.mention}، يوجد عميل بحاجة لمساعدتكم، يرجى كتابة تفاصيل استفسارك ليتم خدمتك فوراً!")
                    else:
                        admin_role = discord.utils.get(guild.roles, name="▴|  𝗔𝗱𝗺𝗶𝗻")
                        if admin_role:
                            await message.channel.send(f"🚨 تنبيه للإدارة: {admin_role.mention}، يوجد عميل بحاجة لمساعدتكم، يرجى كتابة تفاصيل استفسارك!")
                        else:
                            await message.channel.send("⚠️ تنبيه: لم يتم العثور على رتبة الدعم المخصصة، يرجى متابعة التكت من الإدارة.")

            else:
                await message.reply("حياك الله، تفضل بطلبك أو انتظر أحد الإدارة يخدمك.")

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            await message.reply(
                "عذراً، حدث ضغط بسيط. يرجى الانتظار قليلاً وسيتم خدمتك."
            )
    
    await bot.process_commands(message)

# ------------------ Flask Keep‑Alive Thread ------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running"

def start_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ------------------ Main Entry Point ------------------
if __name__ == '__main__':
    threading.Thread(target=start_flask, daemon=True).start()
    bot.run(DISCORD_TOKEN)
