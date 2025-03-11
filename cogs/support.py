import disnake
from disnake.ext import commands
from disnake.ui import Button, View, Modal, TextInput
from utils.constants import CREATE_TICKET_CHANNEL_ID, TICKET_CATEGORY_ID,SUPPORT_ROLE_ID , LOG_CHANNEL_ID 

ticket_counter = 0

class TicketModal(Modal):
    def __init__(self, ticket_type: str):
        self.ticket_type = ticket_type
        global ticket_counter
        ticket_counter += 1
        self.ticket_id = ticket_counter
        components = [
            TextInput(label="Опишите вашу проблему", style=disnake.TextInputStyle.long, custom_id="description")
        ]
        super().__init__(title=f"Создание обращения: {ticket_type}", components=components)

    async def callback(self, interaction: disnake.ModalInteraction):
        description = interaction.text_values["description"]
        guild = interaction.guild
        category = disnake.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
        overwrites = {
            guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            interaction.user: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
            disnake.utils.get(guild.roles, id=SUPPORT_ROLE_ID): disnake.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        channel = await guild.create_text_channel(name=f"{self.ticket_type}-{self.ticket_id}", category=category, overwrites=overwrites)
        await channel.send(
            embed=disnake.Embed(description=f"Тип обращения: {self.ticket_type}\nПользователь: {interaction.user.mention}\nОписание: {description}")
                .set_image(url="https://images-ext-1.discordapp.net/external/kV0gPLPk4HZAZtAzJFITzgz14cfExk7VgoWydVgB2-U/https/message.style/cdn/images/37c2f757a10ac49daf5b4236893fac64e5bcd675b1c8abf2ea9b0ff229dc0228.png?format=webp&quality=lossless"),
            view=TicketControlView(ticket_id=self.ticket_id)
        )
        await interaction.response.send_message(f"Ваше обращение типа {self.ticket_type} создано в канале {channel.mention}!", ephemeral=True)

class TicketControlView(View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @disnake.ui.button(label="Взять тикет", style=disnake.ButtonStyle.primary)
    async def take_ticket(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if SUPPORT_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("Только агенты поддержки могут брать тикеты.", ephemeral=True)
            return
        overwrites = interaction.channel.overwrites
        overwrites[interaction.guild.default_role] = disnake.PermissionOverwrite(read_messages=False)
        overwrites[interaction.user] = disnake.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.response.send_message(f"{interaction.user.mention} взял тикет!", ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} взял тикет!", view=RelinquishTicketView(ticket_id=self.ticket_id))

    @disnake.ui.button(label="Закрыть тикет", style=disnake.ButtonStyle.danger)
    async def close_ticket(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.send_message(
            "Вы уверены, что хотите закрыть тикет?",
            view=ConfirmCloseView(ticket_id=self.ticket_id, channel=interaction.channel),
            ephemeral=True
        )

class ConfirmCloseView(View):
    def __init__(self, ticket_id: int, channel: disnake.TextChannel):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.channel = channel

    @disnake.ui.button(label="Закрыть", style=disnake.ButtonStyle.danger)
    async def confirm_close(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        log_channel = disnake.utils.get(interaction.guild.text_channels, id=LOG_CHANNEL_ID)
        messages = [f"Тикет {self.ticket_id} закрыт {interaction.user.mention}\n"]
        async for message in self.channel.history(limit=None):
            messages.append(f"{message.author}: {message.content}")
        log_content = "\n".join(messages)
        await log_channel.send(log_content)
        await self.channel.delete()
        await interaction.response.send_message("Тикет закрыт и журнал сохранен в логах.", ephemeral=True)

    @disnake.ui.button(label="Отмена", style=disnake.ButtonStyle.secondary)
    async def cancel_close(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.send_message("Закрытие тикета отменено.", ephemeral=True)

class RelinquishTicketView(View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @disnake.ui.button(label="Отказаться от тикета", style=disnake.ButtonStyle.secondary)
    async def relinquish_ticket(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        overwrites = interaction.channel.overwrites
        overwrites[interaction.guild.default_role] = disnake.PermissionOverwrite(read_messages=False)
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.response.send_message(f"{interaction.user.mention} отказался от тикета.", ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} отказался от тикета.", view=TicketControlView(ticket_id=self.ticket_id))

class TicketTypeButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Вопрос", style=disnake.ButtonStyle.success)
    async def question_ticket(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.send_modal(modal=TicketModal(ticket_type="вопрос"))

    @disnake.ui.button(label="Жалоба", style=disnake.ButtonStyle.danger)
    async def complaint_ticket(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.send_modal(modal=TicketModal(ticket_type="жалоба"))

class Support(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(CREATE_TICKET_CHANNEL_ID)
        # Удалим все сообщения из канала
        await channel.purge(limit=100)

        # Отправим новое сообщение с кнопками
        embed = disnake.Embed(title="", description="")
        embed.set_image(url="https://images-ext-1.discordapp.net/external/pIfCwNN50sIYLZH5hzflJVHq1xIGxR7lwNufYXYVcbM/https/message.style/cdn/images/57e50e2cd86cff4b7c287220eb3e44312d2fb5116474afee9b5554dd390f5fa0.png?format=webp&quality=lossless")
        await channel.send(embed=embed, view=TicketTypeButtonView())

    @commands.slash_command(description="Создать тикет.")
    async def create_ticket(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message("Выберите тип обращения:", view=TicketTypeButtonView(), ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(Support(bot))
