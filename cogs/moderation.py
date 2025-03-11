import disnake
from disnake.ext import commands
from disnake import Option
from utils.helpers import send_log_message, warn_user, apply_timeout, get_user_warnings, save_warning_to_memory, get_user_statistics
from config import SUPPORT_LOG_CHANNEL_ID, BLOCKED_ROLE_ID, ADMIN_LOG_CHANNEL_ID

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(description="Выдать предупреждение пользователю.")
    async def warn(
        self,
        inter: disnake.ApplicationCommandInteraction,
        пользователь: disnake.Member,
        причина: str = Option(name="причина", description="Выберите причину", choices=[
            "спам", "оскорбление", "нецензурные выражения", "разжигание конфликтов", "нарушение правил сервера"
        ])
    ):
        warns_count = get_user_warnings(пользователь.id) + 1
        save_warning_to_memory(пользователь.id, причина)

        await warn_user(self.bot, пользователь, причина)
        await send_log_message(self.bot, SUPPORT_LOG_CHANNEL_ID, f"@{inter.author} выдал предупреждение @{пользователь} по причине: {причина}")

        await apply_timeout(пользователь, warns_count)

        await inter.response.send_message(f"Вы выдали предупреждение пользователю @{пользователь} по причине: {причина}", ephemeral=True)

    @commands.slash_command(description="Выдать мут.")
    async def mute(
        self,
        inter: disnake.ApplicationCommandInteraction,
        пользователь: disnake.Member,
        причина: str = Option(name="причина", description="Выберите причину", choices=[
            "спам", "оскорбление", "нецензурные выражения", "разжигание конфликтов", "нарушение правил сервера"
        ])
    ):
        await send_log_message(self.bot, SUPPORT_LOG_CHANNEL_ID, f"@{inter.author} замутил @{пользователь} по причине: {причина}")
        await apply_timeout(пользователь, 1)

        try:
            await пользователь.send(f"Вы получили мут по причине: {причина}")
        except disnake.HTTPException:
            pass

        await inter.response.send_message(f"Вы заблокировали пользователя @{пользователь} по причине: {причина}", ephemeral=True)

    @commands.slash_command(description="Посмотреть статистику предупреждений.")
    async def stats(
        self,
        inter: disnake.ApplicationCommandInteraction,
        пользователь: disnake.Member = None
    ):
        пользователь = пользователь or inter.author

        statistics = get_user_statistics(пользователь.id)

        статистика = f"""
        Статистика пользователя @{пользователь}:
        - Количество предупреждений за 1 день: {statistics['warns_1d']}
        - Количество предупреждений за 7 дней: {statistics['warns_7d']}
        - Количество предупреждений за 1 месяц: {statistics['warns_1m']}
        - Количество предупреждений за все время: {statistics['warns_all']}
        - Количество разобранных обращений за 1 день: {statistics['appeals_1d']}
        - Количество разобранных обращений за 7 дней: {statistics['appeals_7d']}
        - Количество разобранных обращений за 1 месяц: {statistics['appeals_1m']}
        - Количество разобранных обращений за все время: {statistics['appeals_all']}
        """

        await inter.response.send_message(статистика, ephemeral=True)

    @commands.slash_command(description="Обработка апелляций.")
    async def appeal(
        self,
        inter: disnake.ApplicationCommandInteraction,
        пользователь: disnake.Member,
        appeal_type: str = Option(name="тип_апелляции", description="Тип апелляции", choices=[
            "полная", "первый раз"
        ])
    ):
        await send_log_message(self.bot, ADMIN_LOG_CHANNEL_ID, f"Пользователь @{пользователь} подал апелляцию. Тип апелляции: {appeal_type}")
        await inter.response.send_message(f"Пользователь @{пользователь} подал апелляцию. Тип апелляции: {appeal_type}", ephemeral=True)

        if appeal_type == "полная":
            try:
                await пользователь.send("Вы получили полную блокировку. Вы можете подать апелляцию.")
            except disnake.HTTPException:
                pass

def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))
