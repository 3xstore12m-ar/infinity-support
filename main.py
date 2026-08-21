import os
import logging
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai

# ---------------------------------------------------------------------------
# 1. إعدادات التسجيل واللوج (Logging Setup)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2. إعدادات الاتصال والمفاتيح (Environment & API Clients)
# ---------------------------------------------------------------------------
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    logger.error("تحذير: مفاتيح البيئة (DISCORD_TOKEN أو GEMINI_API_KEY) غير مسجلة بشكل صحيح!")

client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# 3. إعدادات ديسكورد والصلاحيات (Discord Intents & Bot Setup)
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------------------------
# 4. الخريطة الثابتة للرومات باستخدام الأيديات (IDs Mapping)
# ---------------------------------------------------------------------------
CHANNEL_MAP = {
    "terms": 1539273868072722543,
    "about": 1539274113699418142,
    "payments": 1539370503192449044,
    "store1": 1539378969336483850,
    "store2": 1539379063888548033,
    "store3": 1539379107807240316,
    "announcements": 1539383061475622943,
    "exchange": 1539383578385977364,
    "admin_config": 1539589182702493776,
    "general_support": 1001478744445296715
}

# ---------------------------------------------------------------------------
# 5. الذاكرة المؤقتة وحالة النظام (System Memory & State)
# ---------------------------------------------------------------------------
welcomed_channels = set()
admin_store_status = {
    "maintenance_notes": "لا توجد صيانات حالياً، جميع الأقسام والخدمات تعمل بكفاءة تامة."
}

# ---------------------------------------------------------------------------
# 6. واجهة الأزرار التفاعلية للتكتات والدعم (Interactive UI Views)
# ---------------------------------------------------------------------------
class SupportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استفسار عن الحسابات", style=discord.ButtonStyle.primary, emoji="🛒")
    async def stock_inquiry(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"تم الضغط على زر استفسار الحسابات بواسطة العضو: {interaction.user}")
        await interaction.response.send_message(
            f"حالة الخدمات الحالية:\n> {admin_store_status['maintenance_notes']}", 
            ephemeral=False
        )

    @discord.ui.button(label="طلب الإدارة / الدعم", style=discord.ButtonStyle.danger, emoji="🚨")
    async def call_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.warning(f"تم طلب الإدارة من قبل العضو: {interaction.user} في القناة: {interaction.channel.name}")
        await interaction.response.send_message(
            "🚨 تم إرسال تنبيه عاجل لفريق الإدارة، يرجى انتظار الرد.", 
            ephemeral=False
        )

    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"طلب إغلاق التكت من قبل: {interaction.user} في القناة: {interaction.channel.name}")
        await interaction.response.send_message("🔒 جاري إغلاق التكت وحفظ السجلات...", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"تم إغلاق التكت بواسطة {interaction.user}")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء محاولة حذف قناة التكت: {e}")

# ---------------------------------------------------------------------------
# 7. دالة جلب السياق والبيانات من رومات السيرفر (Server Context Retrieval)
# ---------------------------------------------------------------------------
async def fetch_server_context(guild):
    context_data = ""
    if not guild:
        return context_data

    for key, ch_id in CHANNEL_MAP.items():
        if key == "admin_config":
            continue
        
        channel = guild.get_channel(ch_id)
        if channel:
            try:
                messages = [msg async for msg in channel.history(limit=10)]
                content = "\n".join([m.content for m in messages if m.content and m.content.strip()])
                context_data += f"\n[محتوى قناة {channel.name}]:\n{content}\n"
            except Exception as e:
                logger.warning(f"تعذر قراءة محتوى القناة ذات المعرف {ch_id}: {e}")
                
    return context_data

# ---------------------------------------------------------------------------
# 8. أحداث البوت الأساسية (Bot Events)
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f'تم تسجيل دخول البوت بنجاح باسم: {bot.user.name} (ID: {bot.user.id})')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # أ) روم إعدادات البوت والتحكم بالحالة
    if message.channel.id == CHANNEL_MAP["admin_config"]:
        admin_store_status["maintenance_notes"] = message.content
        logger.info(f"تم تحديث حالة المتجر بواسطة الأونر: {message.content}")
        await message.reply(f"✅ **تم تحديث الحالة بنجاح:**\n> {message.content}", mention_author=True)
        return

    # ب) معالجة الرسائل في الدعم الفني أو التكتات
    is_ticket = "ticket" in message.channel.name.lower()
    is_general_support = message.channel.id == CHANNEL_MAP["general_support"]

    if is_ticket or is_general_support:
        if is_ticket and message.channel.id not in welcomed_channels:
            welcomed_channels.add(message.channel.id)
            await message.channel.send("حياك الله طال عمرك! كيف أقدر أخدمك اليوم؟", view=SupportView())

        async with message.channel.typing():
            try:
                server_context = await fetch_server_context(message.guild)
                
                # تعليمات صارمة تمنع الجرائد وتطلب الاختصار المفيد بلهجة سعودية
                system_instruction = (
                    "أنت مساعد الدعم الفني لمتجر رقمي.\n"
                    "قواعدك الصارمة للرد:\n"
                    "1. ممنوع نهائياً كتابة ردود طويلة أو سرد تفاصيل غير مهمة (لا تكتب جرائد).\n"
                    "2. كن مختصراً، مباشراً، وواضحاً جداً، ورد بكلمات قليلة ومفيدة تغني عن كثرة الأسئلة.\n"
                    "3. تحدث باللهجة السعودية الطبيعية والمهذبة.\n"
                    "4. اعتمد على معلومات السيرفر التالية:\n" + server_context + "\n"
                    "5. حالة المتجر الحالية:\n" + admin_store_status['maintenance_notes']
                )
                
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=[system_instruction, message.content]
                )
                
                await message.reply(response.text, mention_author=True)
                
            except Exception as e:
                logger.error(f"خطأ في توليد الرد: {e}")
                await message.reply("عذراً طال عمرك، صار فيه ضغط بسيط. جرب مرة ثانية.", mention_author=True)

# ---------------------------------------------------------------------------
# 9. خادم الـ Flask لإبقاء البوت مستيقظاً (Flask Server)
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Infinity Support Bot is Online 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"تشغيل خادم الـ Flask على البورت: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ---------------------------------------------------------------------------
# 10. التشغيل الرئيسي (Main Entry Point)
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(DISCORD_TOKEN)
