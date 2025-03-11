import disnake
from disnake.ext import commands
from config import TOKEN, GUILD_ID, EXTENSIONS

intents = disnake.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, test_guilds=[GUILD_ID])

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user.name}.")

for ext in EXTENSIONS:
    bot.load_extension(ext)

bot.run(TOKEN)
