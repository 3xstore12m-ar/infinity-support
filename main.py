# -*- coding: utf-8 -*-
"""
بوت دعم فني ذكي لمتجر رقمي على ديسكورد - النسخة المُحسَّنة مع تشخيص
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from flask import Flask, render_template_string
import google.generativeai as genai
from dotenv import load_dotenv

# ========== تحميل المتغيرات البيئية ==========
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN or not GEMINI_API_KEY:
    raise ValueError("يجب تعيين DISCORD_TOKEN و GEMINI_API_KEY في متغيرات البيئة")

# ========== تكوين السجلات ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TechSupportBot")

# ========== تكوين نموذج Gemini ==========
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-lite",
    generation_config={
        "temperature": 0.3,
        "top_p": 0.9,
        "max_output_tokens": 200,
    }
)

# ========== تعريف المعرفات الثابتة ==========
# تأكد من صحة هذه المعرفات، خاصة general_support
CHANNEL_IDS = {
    "terms": 1539273868072722543,
    "about_us": 1539274113699418142,
    "payment_methods": 1539370503192449044,
    "products_1": 1539378969336483850,
    "products_2": 1539379063888548033,
    "products_3": 1539379107807240316,
    "announcements": 1539383061475622943,
    "exchange_ads": 1539383578385977364,
    "admin_control": 1539589182702493776,
    "general_support": 1001478744445296715,  # تحقق من هذا المعرف
}

# ========== إعدادات البوت ==========
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========== متغيرات الذاكرة ==========
maintenance_status: Dict[str, str] = {
    "قسم المنتجات 1": "",
    "قسم المنتجات 2": "",
    "قسم المنتجات 3": "",
}
cached_content: Dict[str, str] = {}
last_cache_update: Optional[datetime] = None
CACHE_TTL_SECONDS = 300

# ========== دوال RAG ==========
async def fetch_channel_content(channel_id: int, limit: int = 10) -> str:
    cache_key = str(channel_id)
    global last_cache_update
    if (last_cache_update and
        (datetime.now() - last_cache_update).total_seconds() < CACHE_TTL_SECONDS and
        cache_key in cached_content):
        return cached_content[cache_key]

    channel = bot.get_channel(channel_id)
    if not channel:
        logger.warning(f"القناة ذات المعرف {channel_id} غير موجودة")
        return ""

    try:
        messages = []
        async for msg in channel.history(limit=limit):
            if msg.content and not msg.content.startswith("!"):
                messages.append(msg.content.strip())
        content = "\n".join(messages)
        cached_content[cache_key] = content
        if not last_cache_update:
            last_cache_update = datetime.now()
        return content
    except Exception as e:
        logger.error(f"خطأ في جلب رسائل القناة {channel_id}: {e}")
        return ""

async def build_context_from_channels() -> str:
    context_parts = []
    for name, cid in CHANNEL_IDS.items():
        if name in ["admin_control", "general_support"]:
            continue
        content = await fetch_channel_content(cid)
        if content:
            context_parts.append(f"--- محتوى {name} ---\n{content}")
    maintenance_lines = [f"{k}: {v}" for k, v in maintenance_status.items() if v]
    if maintenance_lines:
        context_parts.append("--- حالة الصيانة ---\n" + "\n".join(maintenance_lines))
    return "\n\n".join(context_parts)

async def generate_smart_response(user_query: str, context: str) -> str:
    system_prompt = (
        "أنت بوت دعم فني لمتجر حسابات وخدمات رقمية على ديسكورد. "
        "يجب أن ترد بلهجة سعودية أصيلة، مختصر جداً، مباشر، ووافٍ من أول مرة. "
        "امنع الإطالة والتفاصيل غير الضرورية (ممنوع الجرائد). "
        "إذا كانت المعلومات غير موجودة في السياق، قل بوضوح 'المعلومة غير متوفرة حالياً' ولا تختلق. "
        "أجب بناءً على المحتوى التالي فقط:\n\n"
    )
    full_prompt = system_prompt + context + "\n\nسؤال الزبون: " + user_query
    try:
        response = gemini_model.generate_content(full_prompt)
        reply = response.text.strip()
        if len(reply) > 500:
            reply = reply[:500] + "..."
        return reply
    except Exception as e:
        logger.error(f"خطأ في توليد الرد: {e}")
        return "عذراً، حدث خلل في الذكاء الاصطناعي. الرجاء المحاولة لاحقاً."

# ========== أحداث البوت ==========
@bot.event
async def on_ready():
    logger.info(f"✅ البوت متصل باسم {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    logger.info("✅ تم مزامنة الأوامر العالمية")
    global last_cache_update
    last_cache_update = None
    await build_context_from_channels()
    logger.info("تم بناء السياق الأولي")

@bot.event
async def on_message(message: discord.Message):
    # نتجاهل رسائل البوت نفسه
    if message.author.bot:
        return

    # ====== تسجيل تفصيلي لكل رسالة ======
    logger.info(f"رسالة من {message.author} في قناة {message.channel.name} (ID: {message.channel.id})")
    logger.info(f"محتوى الرسالة: {message.content[:100]}...")

    # ====== نظام التحكم للأونر ======
    if message.channel.id == CHANNEL_IDS["admin_control"]:
        logger.info("دخل في شرط admin_control")
        if message.author.guild_permissions.administrator:
            content = message.content.strip()
            for section in maintenance_status.keys():
                if section in content:
                    parts = content.split(section, 1)
                    if len(parts) > 1:
                        status_text = parts[1].strip()
                        if not status_text or "طبيعي" in status_text:
                            maintenance_status[section] = ""
                        else:
                            maintenance_status[section] = status_text
                        await message.add_reaction("✅")
                        global last_cache_update
                        last_cache_update = None
                        await build_context_from_channels()
                        logger.info(f"تحديث حالة الصيانة: {section} -> {maintenance_status[section]}")
                        return
        else:
            await message.channel.send("❌ هذا الروم مخصص للأونر فقط.")
        return

    # ====== الدعم الفني العام ======
    if message.channel.id == CHANNEL_IDS["general_support"]:
        logger.info("دخل في شرط general_support")
        if message.content.startswith("!"):
            logger.info("الرسالة أمر، نمررها إلى process_commands")
            await bot.process_commands(message)
            return

        async with message.channel.typing():
            context = await build_context_from_channels()
            reply = await generate_smart_response(message.content, context)
            await message.reply(reply, mention_author=False)
            logger.info("تم الرد على الرسالة في general_support")
        return

    # ====== أي رسالة أخرى ======
    logger.info("الرسالة ليست في روم التحكم ولا في الدعم العام، نمررها للأوامر فقط")
    await bot.process_commands(message)

# ========== أوامر البوت ==========
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """أمر لفحص استجابة البوت"""
    await ctx.send(f"🏓 بونغ! زمن الاستجابة: {round(bot.latency * 1000)}ms")

@bot.command(name="id")
async def get_channel_id(ctx: commands.Context):
    """يعرض معرف القناة الحالية"""
    await ctx.send(f"معرف هذه القناة: `{ctx.channel.id}`")

@bot.command(name="تحديث_السياق")
@commands.has_permissions(administrator=True)
async def force_update_context(ctx: commands.Context):
    async with ctx.typing():
        global last_cache_update
        last_cache_update = None
        await build_context_from_channels()
    await ctx.send("✅ تم تحديث السياق بنجاح.")

# ========== تكتات (اختصار) ==========
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 استفسار عن الحسابات", style=discord.ButtonStyle.primary, custom_id="ticket_accounts")
    async def ticket_accounts(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "استفسار عن الحسابات")

    @discord.ui.button(label="🛠 طلب الإدارة", style=discord.ButtonStyle.danger, custom_id="ticket_admin")
    async def ticket_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "طلب إدارة")

    async def create_ticket(self, interaction: discord.Interaction, reason: str):
        guild = interaction.guild
        member = interaction.user
        category = discord.utils.get(guild.categories, name="التكتات")
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            category = await guild.create_category("التكتات", overwrites=overwrites)
        channel_name = f"تكت-{member.name}-{datetime.now().strftime('%d%m%Y%H%M')}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"تكت من {member} - السبب: {reason}"
        )
        embed = discord.Embed(
            title="📌 تكت الدعم الفني",
            description=f"مرحباً {member.mention}،\nسيتم الرد على استفسارك في أقرب وقت.\n**السبب:** {reason}",
            color=discord.Color.blue()
        )
        embed.set_footer(text="استخدم زر الإغلاق لإنهاء التكت")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🔒 إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="ticket_close"))
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ تم إنشاء تكتك: {channel.mention}", ephemeral=True)

@bot.command(name="تكت")
async def create_ticket_command(ctx: commands.Context):
    view = TicketView()
    embed = discord.Embed(
        title="🆘 فتح تكت دعم",
        description="اختر نوع التكت من الأزرار أدناه:",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=view)

# ========== Flask ==========
app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("""
    <html><body><h1>✅ البوت يعمل</h1><p>الحالة: مستقر</p></body></html>
    """)

@app.route('/health')
def health():
    return {"status": "ok"}

async def run_bot():
    from threading import Thread
    def run_flask():
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    await bot.start(TOKEN)

def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت")
    except Exception as e:
        logger.critical(f"خطأ فادح: {e}")
        raise

if __name__ == "__main__":
    main()
