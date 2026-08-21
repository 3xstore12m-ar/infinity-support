# -*- coding: utf-8 -*-
"""
بوت دعم فني ذكي لمتجر رقمي على ديسكورد
الإصدار النهائي - يعمل على Render مع Flask
تم تطويره وفقاً للمواصفات الدقيقة في وثيقة المشروع
جميع الحقوق محفوظة © 2026
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord
from discord import app_commands
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

# ========== تكوين السجلات (Logging) ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TechSupportBot")

# ========== تكوين نموذج Gemini ==========
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-lite",  # ملاحظة: الإصدار المطلوب gemini-3.5-flash-lite غير موجود حالياً، نستخدم الأقرب
    generation_config={
        "temperature": 0.3,
        "top_p": 0.9,
        "max_output_tokens": 200,
    }
)

# ========== تعريف المعرفات الثابتة ==========
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
    "general_support": 1001478744445296715,
}

# ========== إعدادات البوت ==========
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========== متغيرات الذاكرة الداخلية ==========
# لتخزين حالة الصيانة لكل قسم (يتم تحديثها من روم التحكم)
maintenance_status: Dict[str, str] = {
    "قسم المنتجات 1": "",
    "قسم المنتجات 2": "",
    "قسم المنتجات 3": "",
}

# ذاكرة مؤقتة لآخر محتوى تم قراءته من الرومات (لتجنب الاستدعاء المتكرر)
cached_content: Dict[str, str] = {}
last_cache_update: Optional[datetime] = None
CACHE_TTL_SECONDS = 300  # 5 دقائق


# ========== دالة استرجاع المحتوى من الرومات (RAG) ==========
async def fetch_channel_content(channel_id: int, limit: int = 10) -> str:
    """
    تسحب آخر الرسائل من قناة معينة وترجعها كنص مترابط.
    تستخدم cache لتقليل استدعاءات API.
    """
    # التحقق من الكاش
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
            if msg.content and not msg.content.startswith("!"):  # نتجاهل الأوامر
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
    """
    يبني سياقاً شاملاً من جميع الرومات المحددة باستخدام المعرفات الثابتة.
    """
    context_parts = []
    # نأخذ المحتوى من كل روم
    for name, cid in CHANNEL_IDS.items():
        if name == "admin_control" or name == "general_support":
            continue  # نستثني روم التحكم والدعم العام من سياق RAG
        content = await fetch_channel_content(cid)
        if content:
            context_parts.append(f"--- محتوى {name} ---\n{content}")

    # نضيف حالة الصيانة الحالية
    maintenance_lines = [f"{k}: {v}" for k, v in maintenance_status.items() if v]
    if maintenance_lines:
        context_parts.append("--- حالة الصيانة ---\n" + "\n".join(maintenance_lines))

    return "\n\n".join(context_parts)


# ========== دالة توليد الرد الذكي ==========
async def generate_smart_response(user_query: str, context: str) -> str:
    """
    تستخدم Gemini لتوليد رد مختصر، مفيد، بلهجة سعودية، بناءً على السياق.
    """
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
        # إذا كان الرد طويلاً جداً، نقوم بتقصيره
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
    # نقوم بتحديث الكاش عند البدء
    global last_cache_update
    last_cache_update = None
    await build_context_from_channels()


@bot.event
async def on_message(message: discord.Message):
    # نتجاهل رسائل البوت نفسه
    if message.author.bot:
        return

    # ====== نظام التحكم للأونر (روم التحكم) ======
    if message.channel.id == CHANNEL_IDS["admin_control"]:
        # نتحقق من أن المرسل هو الأونر (permissions administrator)
        if message.author.guild_permissions.administrator:
            content = message.content.strip()
            # نتوقع صيغة مثل: "قسم المنتجات 1 في صيانة مؤقتة"
            # أو "قسم المنتجات 2 يعمل بشكل طبيعي"
            # نقوم بتحديث حالة الصيانة بناءً على النص
            for section in maintenance_status.keys():
                if section in content:
                    # نستخرج الجزء بعد اسم القسم كحالة
                    parts = content.split(section, 1)
                    if len(parts) > 1:
                        status_text = parts[1].strip()
                        # إذا كان النص فارغاً أو كلمة "طبيعي" نزيل الصيانة
                        if not status_text or "طبيعي" in status_text:
                            maintenance_status[section] = ""
                        else:
                            maintenance_status[section] = status_text
                        await message.add_reaction("✅")
                        # نحدّث الكاش ليأخذ الحالة الجديدة
                        global last_cache_update
                        last_cache_update = None
                        await build_context_from_channels()
                        logger.info(f"تحديث حالة الصيانة: {section} -> {maintenance_status[section]}")
                        return
        else:
            await message.channel.send("❌ هذا الروم مخصص للأونر فقط.")
        return  # لا نعالج الرسائل الأخرى في روم التحكم

    # ====== الدعم الفني العام (بدون تكت) ======
    if message.channel.id == CHANNEL_IDS["general_support"]:
        # نتجنب الرد على الرسائل التي تبدأ بأمر
        if message.content.startswith("!"):
            await bot.process_commands(message)
            return

        # نرسل إشارة كتابة
        async with message.channel.typing():
            # نبني السياق
            context = await build_context_from_channels()
            # نولد الرد
            reply = await generate_smart_response(message.content, context)
            # نرسل الرد مع ذكر المصدر (اختياري)
            await message.reply(reply, mention_author=False)
        return

    # ====== معالجة الأوامر العادية ======
    await bot.process_commands(message)


# ========== أوامر التكتات (Support Tickets) ==========
class TicketView(discord.ui.View):
    """عرض الأزرار التفاعلية للتكت"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 استفسار عن الحسابات", style=discord.ButtonStyle.primary, custom_id="ticket_accounts")
    async def ticket_accounts(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "استفسار عن الحسابات")

    @discord.ui.button(label="🛠 طلب الإدارة", style=discord.ButtonStyle.danger, custom_id="ticket_admin")
    async def ticket_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "طلب إدارة")

    @discord.ui.button(label="🔒 إغلاق التكت", style=discord.ButtonStyle.secondary, custom_id="ticket_close")
    async def ticket_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # هذا الزر يستخدم داخل التكت نفسه، وليس في رسالة البداية
        await interaction.response.send_message("سيتم إغلاق هذه القناة خلال 5 ثوانٍ.", ephemeral=False)
        await asyncio.sleep(5)
        channel = interaction.channel
        if channel:
            await channel.delete()

    async def create_ticket(self, interaction: discord.Interaction, reason: str):
        """إنشاء قناة تكت جديدة"""
        guild = interaction.guild
        member = interaction.user

        # نبحث عن فئة التكتات (يمكن تعديلها)
        category = discord.utils.get(guild.categories, name="التكتات")
        if not category:
            # إنشاء الفئة إذا لم توجد
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            category = await guild.create_category("التكتات", overwrites=overwrites)

        # اسم القناة
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

        # نرسل رسالة الترحيب مع أزرار الإغلاق
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


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """معالجة الأزرار التفاعلية (بما فيها إغلاق التكت)"""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "ticket_close":
            # نتحقق من أن المستخدم لديه صلاحية أو هو صاحب التكت
            if interaction.channel and interaction.user.permissions_in(interaction.channel).administrator:
                await interaction.response.send_message("🔒 جارٍ حذف القناة...", ephemeral=False)
                await asyncio.sleep(3)
                await interaction.channel.delete()
            else:
                await interaction.response.send_message("❌ ليس لديك صلاحية لإغلاق هذا التكت.", ephemeral=True)
        # باقي الأزرار يتم التعامل معها في TicketView، لكننا نضيفها هنا للكمال
        elif custom_id in ["ticket_accounts", "ticket_admin"]:
            # نبحث عن الـ View المناسب
            # ولكن نظراً لأننا نستخدم view في الرسالة، سنتركها تعمل هناك
            pass


# ========== أمر فتح تكت (كأمر نصي) ==========
@bot.command(name="تكت")
async def create_ticket_command(ctx: commands.Context):
    """يفتح تكت دعم جديد (أمر اختياري)"""
    view = TicketView()
    embed = discord.Embed(
        title="🆘 فتح تكت دعم",
        description="اختر نوع التكت من الأزرار أدناه:",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=view)


# ========== أمر يدوي لتحديث السياق (للأونر) ==========
@bot.command(name="تحديث_السياق")
@commands.has_permissions(administrator=True)
async def force_update_context(ctx: commands.Context):
    """يقوم بتحديث الكاش يدوياً (للأونر فقط)"""
    async with ctx.typing():
        global last_cache_update
        last_cache_update = None
        await build_context_from_channels()
    await ctx.send("✅ تم تحديث السياق بنجاح.")


# ========== فلاسك ويب سيرفر (لـ Render) ==========
app = Flask(__name__)

@app.route('/')
def home():
    """صفحة رئيسية بسيطة لمراقبة الحالة"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>بوت الدعم الفني</title></head>
    <body>
        <h1>✅ البوت يعمل بكفاءة</h1>
        <p>تم تشغيل البوت بنجاح. استخدم ديسكورد للتفاعل.</p>
        <p>الحالة: <strong>مستقر</strong></p>
        <p>وقت التشغيل: {{ now }}</p>
    </body>
    </html>
    """, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/health')
def health():
    """نقطة نهاية للتحقق من الصحة (لـ Render)"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ========== التشغيل الأساسي (متزامن مع Flask) ==========
async def run_bot():
    """تشغيل البوت مع Flask في نفس العملية"""
    # نبدأ Flask في thread منفصل
    from threading import Thread
    def run_flask():
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # نبدأ البوت
    await bot.start(TOKEN)


def main():
    """الدالة الرئيسية لتشغيل كل شيء"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.critical(f"خطأ فادح: {e}")
        raise


if __name__ == "__main__":
    main()
