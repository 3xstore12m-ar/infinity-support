import os
import discord
from discord.ext import commands
import google.generativeai as genai

# استبدل الرموز أدناه بالـ Tokens الخاصة بك
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # البوت بيرد فقط إذا كانت الرسالة في قناة باسمها ticket
    if "ticket" in message.channel.name.lower():
        async with message.channel.typing():
            response = model.generate_content(f"أنت مساعد متجر إنفنتي. رد على العميل: {message.content}")
            await message.reply(response.text)

bot.run(DISCORD_TOKEN)
