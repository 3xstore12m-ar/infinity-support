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
            f"حالة الخدمات الحالية في المتجر:\n> {admin_store_status['maintenance_notes']}", 
            ephemeral=False
        )

    @discord.ui.button(label="طلب الإدارة / الدعم", style=discord.ButtonStyle.danger, emoji="🚨")
    async def call_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.warning(f"تم طلب الإدارة من قبل العضو: {interaction.user} في القناة: {interaction.channel.name}")
        await interaction.response.send_message(
            "🚨 تم إرسال تنبيه عاجل لفريق الإدارة، يرجى انتظار الرد من أحد الموظفين المختصين.", 
            ephemeral=False
        )

    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"طلب إغلاق التكت من قبل: {interaction.user} في القناة: {interaction.channel.name}")
        await interaction.response.send_message("🔒 جاري إغلاق التكت وحفظ السجلات، شكراً لتواصلك معنا.", ephemeral=True)
        
        # حذف القناة بعد إغلاق التكت
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
                messages = [msg async for msg in channel.history(limit=15)]
                content = "\n".join([m.content for m in messages if m.content and m.content.strip()])
                context_data += f"\n====================\n[محتوى قناة: {channel.name}]\n====================\n{content}\n"
            except Exception as e:
                logger.warning(f"تعذر قراءة محتوى القناة ذات المعرف {ch_id} (المفتاح: {key}): {e}")
                
    return context_data

# ---------------------------------------------------------------------------
# 8. أحداث البوت الأساسية (Bot Events)
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f'--------------------------------------------------')
    logger.info(f'تم تسجيل دخول البوت بنجاح تام!')
    logger.info(f'اسم البوت: {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'--------------------------------------------------')

@bot.event
async def on_message(message):
    # تجاهل رسائل البوتات لكي لا يحدث تداخل أو حلقة لا نهائية
    if message.author.bot:
        return

    # ---------------------------------------------------------------------------
    # أ) روم إعدادات البوت والتحكم بالحالة (Admin Configuration Room)
    # ---------------------------------------------------------------------------
    if message.channel.id == CHANNEL_MAP["admin_config"]:
        # التحقق من صلاحيات الكاتب (يمكنك إضافة فحص رتبة هنا لو أحببت مستقبلاً)
        admin_store_status["maintenance_notes"] = message.content
        logger.info(f"تم تحديث حالة المتجر بواسطة الأونر/الإدارة في روم الإعدادات: {message.content}")
        await message.reply(
            f"✅ **تم تحديث حالة المتجر بنجاح في سجلات البوت:**\n> {message.content}",
            mention_author=True
        )
        return

    # ---------------------------------------------------------------------------
    # ب) معالجة الرسائل في الدعم الفني العام أو تذاكر الدعم (Support & Tickets)
    # ---------------------------------------------------------------------------
    is_ticket = "ticket" in message.channel.name.lower()
    is_general_support = message.channel.id == CHANNEL_MAP["general_support"]

    if is_ticket or is_general_support:
        
        # الترحيب التلقائي بأول رسالة في التكتات الجديدة
        if is_ticket and message.channel.id not in welcomed_channels:
            welcomed_channels.add(message.channel.id)
            logger.info(f"تم إرسال رسالة الترحيب والأزرار للتكت الجديد: {message.channel.name}")
            await message.channel.send(
                "حياك الله طال عمرك، نورتنا! كيف أقدر أخدمك بخصوص خدماتنا ومنتجاتنا اليوم؟", 
                view=SupportView()
            )

        # استخراج السياق والرد عبر نموذج الذكاء الاصطناعي بعمق ودقة
        async with message.channel.typing():
            try:
                server_context = await fetch_server_context(message.guild)
                
                system_instruction = (
                    "أنت المساعد الذكي والرمسي لمتجر خدمات الديسكورد والأقسام.\n"
                    "تحدث دائماً بلهجة سعودية أصيلة، وكن دقيقاً، عميقاً في الوصف، وغير عشوائي أبداً.\n"
                    "استخدم حصرياً المعلومات الواردة في الأقسام الرسمية التالية:\n"
                    f"{server_context}\n\n"
                    "حالة المتجر والصيانة الحالية المعتمدة من الإدارة:\n"
                    f"{admin_store_status['maintenance_notes']}\n\n"
                    "تعليمات صارمة:\n"
                    "1. لا تقم بتأليف أي معلومات غير موجودة في السياق.\n"
                    "2. إذا كانت الإجابة غير متوفرة في السياق، اعتذر بكل أدب واطلب من العميل فتح تذكرة أو انتظار توجيه الإدارة.\n"
                    "3. اجعل ردودك منسقة واحترافية تماماً."
                )
                
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=[system_instruction, message.content]
                )
                
                await message.reply(response.text, mention_author=True)
                
            except Exception as e:
                logger.error(f"حدث خطأ أثناء توليد الرد من نموذج الذكاء الاصطناعي: {e}")
                await message.reply(
                    "عذراً طال عمرك، واجهنا خلل مؤقت في معالجة طلبك. يرجى المحاولة بعد قليل أو التواصل مع الإدارة مباشرة.",
                    mention_author=True
                )

# ---------------------------------------------------------------------------
# 9. خادم الـ Flask المخصص لإبقاء البوت مستيقظاً على Render (Flask Server)
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Infinity Support Bot is Online and Running Successfully 24/7!"

def run_flask():
    # قراءة المنفذ بشكل ديناميكي ليتوافق تماماً مع متطلبات منصة Render ويحل مشكلة Port Binding
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"تشغيل خادم الـ Flask على المنفذ المحلي: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ---------------------------------------------------------------------------
# 10. تشغيل النظام المتزامن (Main Entry Point)
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("جاري بدء تشغيل خادم الـ Flask في خلفية النظام...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logger.info("جاري الاتصال بخوادم ديسكورد عبر البوت...")
    bot.run(DISCORD_TOKEN)
