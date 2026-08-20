import os
import discord
from discord.ext import commands
import google.generativeai as genai

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"البوت جاهز وشغال باسم {bot.user}")

@bot.event
async def on_message(message):
    # تجاهل رسائل البوت نفسه عشان ما يدخل في ردود لا نهائية
    if message.author.bot:
        return
    
    # التحقق من أن القناة تخص التذاكر (سواء فيها ticket أو رقم تذكرة)
    if "ticket" in message.channel.name.lower():
        try:
            # إرسال النص لجيميناي واستقبال الرد
            prompt = f"أنت مساعد دعم فني لمتجر حسابات ألعاب. رد بشكل مختصر وودود وسريع على العميل: {message.content}"
            response = model.generate_content(prompt)
            
            # إرسال الرد مباشرة بدون تعليق
            await message.channel.send(response.text)
        except Exception as e:
            print(f"خطأ: {e}")
            await message.channel.send("أهلاً بك، تم استلام رسالتك وسيتم خدمتك من قبل الإدارة قريباً.")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
