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

# ذاكرة مؤقتة لحفظ سجلات المحادثة لكل تكت
channel_histories = {}
# مجموعة لتتبع التكتات التي تم إرسال رسالة الترحيب لها لمنع تكرارها
welcomed_channels = set()

# ------------------ Interactive Buttons View ------------------
class SupportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استفسار عن الحسابات", style=discord.ButtonStyle.primary, emoji="🛒")
    async def stock_inquiry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "حياك الله! يمكنك الاطلاع على أقسام المنتجات تحت فئة (STORE & PRODUCTS)، حالياً هي قيد التجهيز والصيانة وستتوفر قريباً.",
            ephemeral=False
        )

    @discord.ui.button(label="طلب الإدارة / الدعم", style=discord.ButtonStyle.danger, emoji="🚨")
    async def call_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        target_role = discord.utils.get(guild.roles, name="Support") or discord.utils.get(guild.roles, name="الدعم الفني") or discord.utils.get(guild.roles, name="▴|  𝗔𝗱𝗺𝗶𝗻")
        
        mention_text = target_role.mention if target_role else "@admin"
        await interaction.response.send_message(
            f"🚨 تنبيه للإدارة: {mention_text}، يوجد عميل بحاجة لمساعدتكم في هذا التكت، يرجى كتابة تفاصيل استفسارك ليتم خدمتك فوراً!",
            ephemeral=False
        )

    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 جاري إغلاق التكت وحفظ السجلات...", ephemeral=True)
        try:
            channel = interaction.channel
            guild = interaction.guild
            channel_id = channel.id

            log_channel = discord.utils.get(guild.text_channels, name="▵سجلات-التذاكر") or discord.utils.get(guild.text_channels, name="سجلات-التذاكر")

            if channel_id in channel_histories and channel_histories[channel_id]:
                log_content = "\n".join(channel_histories[channel_id])
            else:
                log_content = "لم يتم تسجيل محادثة مفصلة داخل هذا التكت."

            if log_channel:
                embed = discord.Embed(
                    title=f"🔒 تقرير إغلاق تكت: {channel.name}",
                    color=discord.Color.red()
                )
                embed.add_field(name="بواسطة", value=interaction.user.mention, inline=False)
                
                if len(log_content) > 1024:
                    log_content = log_content[-1021:] + "..."
                embed.add_field(name="ملخص المحادثة", value=log_content, inline=False)
                
                await log_channel.send(embed=embed)

            await channel.delete(reason="تم إغلاق التكت وحفظ السجل.")
            
            if channel_id in channel_histories:
                del channel_histories[channel_id]
            if channel_id in welcomed_channels:
                welcomed_channels.remove(channel_id)

        except Exception as e:
            logger.error(f"Error handling ticket closure and logs: {e}")

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

    channel_id = message.channel.id
    user_content = message.content.strip()
    
    if channel_id not in channel_histories:
        channel_histories[channel_id] = []

    # إذا كان هذا اول تفاعل بالروم ولم يتم الترحيب بعد، نرسل رسالة الترحيب مع الأزرار أولاً
    if channel_id not in welcomed_channels:
        welcomed_channels.add(channel_id)
        welcome_text = "حياك الله طال عمرك في متجرنا! 🤝\nكيف أقدر أخدمك بخصوص حسابات المتجر والخدمات العامة اليوم؟ تفضل بطلبك أو اختر من الأزرار أدناه:"
        channel_histories[channel_id].append(f"البوت (ترحيب): {welcome_text}")
        
        view = SupportView()
        await message.channel.send(welcome_text, view=view)

    if user_content:
        channel_histories[channel_id].append(f"الزبون ({message.author.name}): {user_content}")
        if len(channel_histories[channel_id]) > 30:
            channel_histories[channel_id].pop(0)

    async with message.channel.typing():
        try:
            if not user_content:
                return

            guild = message.guild
            category_info = "قسم المنتجات الأساسي (STORE & PRODUCTS) يحتوي على أقسام الحسابات، وهي قيد التجهيز والصيانة حالياً."

            history_text = "\n".join(channel_histories[channel_id])

            system_prompt = (
                "أنت موظف دعم فني ذكي ورسمي لمتجر حسابات عامة وخدمات رقمية داخل سيرفر ديسكورد فقط.\n"
                "قواعد صارمة جداً:\n"
                "1. ممنوع نهائياً ذكر أي 'موقع إلكتروني' أو زيارة رابط خارجي خارج الديسكورد.\n"
                "2. لا تجاوب بأي أجوبة عشوائية. حالة المنتجات في السيرفر: " + category_info + "\n"
                "   إذا سأل عن الحسابات أو المنتجات، وجهه إلى فئة (STORE & PRODUCTS) وأخبره أنها قيد التجهيز حالياً.\n"
                "3. تحدث باللهجة السعودية الرسمية والمهذبة، وبدون إطالة.\n"
                "4. تذكر سياق المحادثة السابقة بينك وبينه تماماً.\n"
                "5. إذا طلب الزبون التحدث مع الإدارة أو الدعم الفني، انهِ ردك بكلمة [CALL_ADMIN] في نهاية الجملة.\n\n"
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

            need_admin_call = False
            if "[CALL_ADMIN]" in reply:
                need_admin_call = True
                reply = reply.replace("[CALL_ADMIN]", "").strip()

            if reply:
                if len(reply) > 2000:
                    reply = reply[:1997] + "..."
                
                channel_histories[channel_id].append(f"البوت: {reply}")
                
                # الرد النصي الخالص بدون أزرار متكررة
                await message.reply(reply)

                if need_admin_call:
                    target_role = discord.utils.get(guild.roles, name="Support") or discord.utils.get(guild.roles, name="الدعم الفني") or discord.utils.get(guild.roles, name="▴|  𝗔𝗱𝗺𝗶𝗻")
                    if target_role:
                        await message.channel.send(f"🚨 تنبيه للإدارة: {target_role.mention}، يوجد عميل بحاجة لمساعدتكم، يرجى كتابة تفاصيل استفسارك ليتم خدمتك فوراً!")
                    else:
                        await message.channel.send("🚨 تنبيه للإدارة: @admin، يوجد عميل بحاجة لمساعدتكم!")

            else:
                await message.reply("حياك الله، تفضل بطلبك وسأقوم بمساعدتك.")

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
