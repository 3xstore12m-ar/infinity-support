"""
Discord Bot for a Digital Store – Full Implementation
Features:
- Ticket system with interactive buttons
- AI‑powered responses (Gemini) using RAG from official channels
- Admin configuration via admin_config channel
- Flask health‑check server for hosting (Render)
- All channel IDs are hard‑coded for stability
"""

import os
import asyncio
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, jsonify

# Google GenAI
from google import genai
from google.genai import types

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Constants – Channel IDs (hard‑coded for reliability)
# ----------------------------------------------------------------------
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
    "general_support": 1001478744445296715,
}

# Store statuses (updated by admin_config messages)
admin_store_status: Dict[str, str] = {
    "store1": "🟢 متاح",
    "store2": "🟢 متاح",
    "store3": "🟢 متاح",
}

# Global reference to the bot for use in views
bot: commands.Bot = None

# ----------------------------------------------------------------------
# Flask server (health‑check for Render)
# ----------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
@flask_app.route("/health")
def health():
    return jsonify({"status": "alive", "timestamp": datetime.utcnow().isoformat()})

def run_flask():
    """Run Flask in a separate thread."""
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ----------------------------------------------------------------------
# Discord Bot Setup
# ----------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------------------------------------------------
# AI Client (Google GenAI)
# ----------------------------------------------------------------------
GENAI_MODEL = "gemini-3.5-flash-lite"  # المتفق عليه
# دعم كلا الاسمين للمفتاح لضمان عدم حدوث مشاكل في البيئة
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not GENAI_API_KEY:
    logger.warning("مفتاح الذكاء الاصطناعي (GEMINI_API_KEY) غير مسجل في متغيرات البيئة!")

genai_client = genai.Client(api_key=GENAI_API_KEY) if GENAI_API_KEY else None

# ----------------------------------------------------------------------
# RAG – Fetch context from official channels
# ----------------------------------------------------------------------
async def fetch_channel_context(channel_id: int, limit: int = 10) -> str:
    """
    Fetch the last `limit` messages from a given channel ID.
    Returns a concatenated string of message content.
    """
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found.")
            return ""
        messages = []
        async for msg in channel.history(limit=limit, oldest_first=False):
            if msg.author == bot.user:
                continue
            messages.append(f"{msg.author.display_name}: {msg.content}")
        return "\n".join(messages) if messages else ""
    except discord.Forbidden:
        logger.error(f"Missing permissions to read channel {channel_id}")
        return ""
    except Exception as e:
        logger.error(f"Error reading channel {channel_id}: {e}")
        return ""

async def build_rag_context() -> str:
    context_parts = []
    rag_channels = [
        "terms", "about", "payments", "store1",
        "store2", "store3", "announcements", "exchange"
    ]
    for key in rag_channels:
        cid = CHANNEL_MAP.get(key)
        if not cid:
            continue
        content = await fetch_channel_context(cid, limit=8)
        if content:
            context_parts.append(f"--- {key.upper()} ---\n{content}")

    return "\n\n".join(context_parts)

# ----------------------------------------------------------------------
# AI Response Generator (ردود مختصرة بلهجة سعودية ودقيقة)
# ----------------------------------------------------------------------
async def generate_ai_response(user_query: str, ticket_channel: discord.TextChannel) -> str:
    if not genai_client:
        return "⚠️ الذكاء الاصطناعي غير متوفر حالياً. يرجى التواصل مع الإدارة."

    try:
        rag_context = await build_rag_context()

        store_status_text = "\n".join(
            [f"- {k}: {v}" for k, v in admin_store_status.items()]
        )
        
        system_prompt = (
            "أنت مساعد متجر رقمي سعودي.\n"
            "تعليمات صارمة للردود:\n"
            "1. ممنوع نهائياً كتابة ردود طويلة أو سرد تفاصيل غير مهمة (لا تكتب جرائد).\n"
            "2. كن مختصراً، مباشراً، وواضحاً جداً، ورد بكلمات قليلة ومفيدة تغني عن كثرة الأسئلة.\n"
            "3. تحدث باللهجة السعودية الطبيعية والمهذبة.\n"
            "4. اعتمد حصرياً على معلومات السيرفر الرسمية وحالة المتجر.\n\n"
            f"حالة المتجر حالياً:\n{store_status_text}\n\n"
            f"السياق الرسمي من قنوات المتجر:\n{rag_context}"
        )

        user_message = f"سؤال المستخدم: {user_query}"

        response = genai_client.models.generate_content(
            model=GENAI_MODEL,
            contents=[
                types.Content(role="system", parts=[types.Part(text=system_prompt)]),
                types.Content(role="user", parts=[types.Part(text=user_message)]),
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=200,
                top_p=0.95,
            )
        )

        if response.candidates:
            return response.candidates[0].content.parts[0].text.strip()
        else:
            return "عذراً طال عمرك، جرب مرة ثانية."

    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return "حدث خطأ بسيط، يرجى المحاولة لاحقاً."

# ----------------------------------------------------------------------
# Ticket Views (Interactive Buttons)
# ----------------------------------------------------------------------
class TicketView(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel, user: discord.Member):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.user = user

    @discord.ui.button(label="📄 استفسار عن الحسابات", style=discord.ButtonStyle.primary, custom_id="ticket_accounts")
    async def accounts_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"حالة الخدمات الحالية:\n> {admin_store_status.get('store1', 'متاحة')}",
            ephemeral=False
        )

    @discord.ui.button(label="👑 طلب الإدارة", style=discord.ButtonStyle.danger, custom_id="ticket_admin")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        admins = [m for m in guild.members if m.guild_permissions.administrator]
        if admins:
            mention = " ".join([m.mention for m in admins[:3]])
            await interaction.response.send_message(
                f"{mention} تم طلب الإدارة في هذا التكت.",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                "تم إرسال التنبيه للإدارة.",
                ephemeral=False
            )

    @discord.ui.button(label="🔒 إغلاق التكت", style=discord.ButtonStyle.secondary, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ فقط صاحب التكت أو الإدارة يمكنهم إغلاقه.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 سيتم إغلاق هذا التكت وحذف القناة...", ephemeral=False)
        await asyncio.sleep(3)
        try:
            await self.ticket_channel.delete()
        except Exception as e:
            logger.error(f"Failed to delete ticket channel: {e}")

# ----------------------------------------------------------------------
# Slash Commands
# ----------------------------------------------------------------------
@bot.tree.command(name="ticket", description="فتح تكت جديد للدعم")
async def ticket_command(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("هذا الأمر يعمل فقط في السيرفر.", ephemeral=True)
        return

    user = interaction.user
    category = discord.utils.get(guild.categories, name="تذاكر الدعم")
    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        category = await guild.create_category("تذاكر الدعم", overwrites=overwrites)

    channel_name = f"تكت-{user.display_name.lower()}"
    if len(channel_name) > 100:
        channel_name = channel_name[:100]

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    for member in guild.members:
        if member.guild_permissions.administrator:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    try:
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"تكت من {user.display_name}"
        )
    except Exception as e:
        logger.error(f"Failed to create ticket channel: {e}")
        await interaction.response.send_message("حدث خطأ أثناء إنشاء التكت.", ephemeral=True)
        return

    view = TicketView(ticket_channel=channel, user=user)
    embed = discord.Embed(
        title="🎫 تذكرة دعم جديدة",
        description=f"حياك الله {user.mention}!\nكيف أقدر أخدمك اليوم بخصوص منتجاتنا؟",
        color=discord.Color.green()
    )
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ تم فتح التكت بنجاح: {channel.mention}", ephemeral=True)

# ----------------------------------------------------------------------
# Event: on_ready
# ----------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

# ----------------------------------------------------------------------
# Event: on_message – AI responses & Admin config
# ----------------------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # 1. Handle Admin Config Channel
    if message.channel.id == CHANNEL_MAP["admin_config"]:
        content = message.content.strip()
        if not content:
            return
        
        admin_store_status["store1"] = content
        logger.info(f"تم تحديث حالة المتجر بواسطة الأونر: {content}")
        await message.reply(f"✅ **تم تحديث الحالة بنجاح:**\n> {content}")
        return

    # 2. Handle AI responses in ticket channels or general support
    is_ticket = message.channel.category and message.channel.category.name == "تذاكر الدعم"
    is_general_support = message.channel.id == CHANNEL_MAP["general_support"]

    if is_ticket or is_general_support:
        if message.content.startswith("!"):
            await bot.process_commands(message)
            return

        async with message.channel.typing():
            response = await generate_ai_response(message.content, message.channel)
            await message.reply(response, mention_author=True)
        return

    await bot.process_commands(message)

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on background thread.")

    token = os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("توكن البوت (DISCORD_TOKEN) غير مسجل في متغيرات البيئة!")
        return

    try:
        bot.run(token)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
