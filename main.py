import os
import logging
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai

# ------------------ إعدادات التسجيل واللوج ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------ إعدادات الاتصال ------------------
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

# ------------------ إعدادات ديسكورد ------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------ خريطة الرومات الثابتة (IDs) ------------------
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

# ذاكرة النظام
channel_histories = {}
welcomed_channels = set()
admin_store_status = {"maintenance_notes": "لا توجد صيانات حالياً، جميع الأقسام تعمل بكفاءة."}

# ------------------ واجهة الأزرار ------------------
class SupportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استفسار عن الحسابات", style=discord.ButtonStyle.primary, emoji="🛒")
    async def stock_inquiry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"حالة الخدمات الحالية: {admin_store_status['maintenance_notes']}", ephemeral=False)

    @discord.ui.button(label="طلب الإدارة / الدعم", style=discord.ButtonStyle.danger, emoji="🚨")
    async def call_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🚨 تم إرسال تنبيه للإدارة، يرجى انتظار الرد من أحد الموظفين.", ephemeral=False)

    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 جاري إغلاق التكت، شكراً لتواصلك معنا.", ephemeral=True)
        await interaction.channel.delete()

# ------------------ دالة جلب السياق من الرومات ------------------
async def fetch_server_context(guild):
    context_data = ""
    for key, ch_id in CHANNEL_MAP.items():
        if key == "admin_config": continue
        channel = guild.get_channel(ch_id)
        if channel:
            try:
                messages = [msg async for msg in channel.history(limit=15)]
                content = "\n".join([m.content for m in messages if m.content.strip()])
                context_data += f"\n[محتوى القناة: {channel.name}]\n{content}\n"
            except Exception as e:
                logger.warning(f"تعذر قراءة القناة {key}: {e}")
    return context_data

# ------------------ الأحداث (Events) ------------------
@bot.event
async def on_ready():
    logger.info(f'تم تسجيل دخول البوت بنجاح باسم: {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot: return

    # تحكم الأونر في حالة البوت (بدون تعديل كود)
    if message.channel.id == CHANNEL_MAP["admin_config"]:
        admin_store_status["maintenance_notes"] = message.content
        await message.reply(f"✅ تم تحديث الحالة في سجلات البوت:\n> {message.content}")
        return

    # التفاعل في التكتات أو الدعم العام
    if "ticket" in message.channel.name.lower() or message.channel.id == CHANNEL_MAP["general_support"]:
        
        # الترحيب المبدئي للتكتات
        if "ticket" in message.channel.name.lower() and message.channel.id not in welcomed_channels:
            welcomed_channels.add(message.channel.id)
            await message.channel.send("حياك الله طال عمرك، كيف أقدر أخدمك بخصوص خدماتنا اليوم؟", view=SupportView())

        # معالجة ذكية للردود
        async with message.channel.typing():
            context = await fetch_server_context(message.guild)
            system_instruction = (
                "أنت المساعد الرسمي للمتجر، تتحدث بلهجة سعودية عميقة ووصف دقيق.\n"
                "تستخدم المعلومات من القنوات الرسمية: " + context + "\n"
                "حالة المتجر الحالية: " + admin_store_status['maintenance_notes'] + "\n"
                "تعليمات: لا تألف معلومات، إذا لم تجد الإجابة في القنوات، اعتذر بأدب واطلب فتح تذكرة مع الدعم الفني."
            )
            
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[system_instruction, message.content]
            )
            
            await message.reply(response.text)

# ------------------ تشغيل البوت ------------------
if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
