import disnake
from disnake.ext import commands
from disnake.ui import Button, View, Select, Modal, TextInput
from utils.constants import CREATE_VOICE_CHANNEL_ID, CATEGORY_ID

class RenameChannelModal(Modal):
    def __init__(self, channel_id):
        self.channel_id = channel_id
        components = [TextInput(label="Новое имя канала", placeholder="Введите новое имя", custom_id="channel_name_input")]
        super().__init__(title="Переименовать канал", components=components)
    
    async def callback(self, interaction: disnake.ModalInteraction):
        new_name = interaction.text_values["channel_name_input"]
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            try:
                await channel.edit(name=new_name)
                await interaction.response.send_message(f"Канал был переименован в {new_name}.", ephemeral=True)
            except Exception as e:
                print(f"Ошибка при переименовании канала: {e}")
                await interaction.response.send_message("Что-то пошло не так. Попробуйте снова.", ephemeral=True)
        else:
            await interaction.response.send_message("Канал не найден.", ephemeral=True)


class VoiceChannelControlView(View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

        # First row
        self.add_item(Button(label="", emoji="<:limit:1357828278970351698>", style=disnake.ButtonStyle.secondary, custom_id="set_user_limit")) 
        self.add_item(Button(label="", emoji="<:ban:1357828274868322475>", style=disnake.ButtonStyle.secondary, custom_id="block_user"))
        self.add_item(Button(label="", emoji="<:access:1357828276969799831>", style=disnake.ButtonStyle.secondary, custom_id="manage_access"))
        self.add_item(Button(label="", emoji="<:visib:1357828280425644114>", style=disnake.ButtonStyle.secondary, custom_id="visibility_settings"))

        # Second row
        self.add_item(Button(label="", emoji="<:bitrate:1357828282979979273>", style=disnake.ButtonStyle.secondary, custom_id="set_bitrate_and_region"))
        self.add_item(Button(label="", emoji="<:mute:1357828284804628641>", style=disnake.ButtonStyle.secondary, custom_id="mute_user"))
        self.add_item(Button(label="", emoji="<:name:1357828288256413866>", style=disnake.ButtonStyle.secondary, custom_id="rename_channel"))
        self.add_item(Button(label="", emoji="<:beta:1357828286394138795>", style=disnake.ButtonStyle.secondary, custom_id="beta_button", disabled=True))


    async def interaction_check(self, interaction: disnake.Interaction):
        return interaction.user == self.channel.guild.owner

    async def on_timeout(self):
        if self.message:
            await self.message.delete()

    async def kick_user(self, interaction: disnake.MessageInteraction):
        select = Select(
            placeholder="Выберите пользователя для кика",
            options=[disnake.SelectOption(label=member.display_name, value=str(member.id)) for member in self.channel.members]
        )

        async def select_callback(interaction: disnake.MessageInteraction):
            member_id = int(select.values[0])
            member = self.channel.guild.get_member(member_id)
            await member.move_to(None)
            await interaction.response.send_message(f"{member.display_name} был кикнут из голосового канала.", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Выберите пользователя для кика:", view=view, ephemeral=True)

    async def block_user(self, interaction: disnake.MessageInteraction):
        members = self.channel.members
        
        # Button view for choosing between blocking and unblocking
        block_button = Button(label="Заблокировать пользователя", style=disnake.ButtonStyle.danger)
        unblock_button = Button(label="Разблокировать пользователя", style=disnake.ButtonStyle.success)
        
        async def show_block_select(interaction: disnake.MessageInteraction):
            if not members:
                await interaction.response.send_message("В канале нет пользователей для блокировки.", ephemeral=True)
                return
                
            block_select = Select(
                placeholder="Выберите пользователя для блокировки",
                options=[disnake.SelectOption(label=member.display_name, value=str(member.id)) for member in members[:25]]
            )
            
            async def block_select_callback(interaction: disnake.MessageInteraction):
                member_id = int(block_select.values[0])
                member = self.channel.guild.get_member(member_id)
                
                try:
                    # Сначала исключаем пользователя из голосового канала
                    if member in self.channel.members:
                        await member.move_to(None)
                    
                    # Затем обновляем права доступа
                    overwrites = self.channel.overwrites
                    overwrites[member] = disnake.PermissionOverwrite(connect=False)
                    await self.channel.edit(overwrites=overwrites)
                    
                    await interaction.response.send_message(f"{member.display_name} был заблокирован в голосовом канале.", ephemeral=True)
                except Exception as e:
                    print(f"Ошибка при блокировке пользователя {member.display_name}: {e}")
                    await interaction.response.send_message(f"Произошла ошибка при блокировке пользователя: {str(e)}", ephemeral=True)
            
            block_select.callback = block_select_callback
            view = View()
            view.add_item(block_select)
            await interaction.response.send_message("Выберите пользователя для блокировки:", view=view, ephemeral=True)
        
        async def show_unblock_select(interaction: disnake.MessageInteraction):
            # Получаем всех пользователей сервера, у которых есть индивидуальные разрешения для канала
            banned_members = []
            
            # Проверяем все переопределения разрешений канала
            for target, overwrite in self.channel.overwrites.items():
                # Проверяем, что это пользователь (а не роль) и что у него запрещено подключение
                if isinstance(target, disnake.Member):
                    # Проверяем значение connect (False = запрещено)
                    if overwrite.connect is False:
                        banned_members.append(target)
            
            # Если список пуст, сообщаем об этом
            if not banned_members:
                # Дополнительно проверяем, есть ли в канале переопределения разрешений
                if not self.channel.overwrites:
                    await interaction.response.send_message("В канале нет переопределений разрешений.", ephemeral=True)
                else:
                    await interaction.response.send_message("В канале нет заблокированных пользователей.", ephemeral=True)
                return
            
            # Создаем список опций для выпадающего списка
            options = []
            for member in banned_members[:25]:  # Ограничиваем до 25 пользователей из-за ограничений Discord
                option = disnake.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"ID: {member.id}"
                )
                options.append(option)
            
            # Если список опций пуст, сообщаем об этом
            if not options:
                await interaction.response.send_message("Не удалось создать список заблокированных пользователей.", ephemeral=True)
                return
                
            # Создаем выпадающий список
            unblock_select = Select(
                placeholder="Выберите пользователя для разблокировки",
                options=options
            )
            
            async def unblock_select_callback(interaction: disnake.MessageInteraction):
                member_id = int(unblock_select.values[0])
                member = self.channel.guild.get_member(member_id)
                
                # Get current overwrites and modify them
                overwrites = self.channel.overwrites
                if member in overwrites:
                    # If there are other permissions, preserve them but enable connect
                    overwrites[member].connect = None
                    
                    # If all permissions are None after this change, remove the overwrite entirely
                    if all(getattr(overwrites[member], attr) is None for attr in dir(overwrites[member]) if not attr.startswith('_')):
                        del overwrites[member]
                
                await self.channel.edit(overwrites=overwrites)
                await interaction.response.send_message(f"{member.display_name} был разблокирован и теперь может войти в голосовой канал.", ephemeral=True)
            
            unblock_select.callback = unblock_select_callback
            view = View()
            view.add_item(unblock_select)
            await interaction.response.send_message("Выберите пользователя для разблокировки:", view=view, ephemeral=True)
        
        # Assign callbacks to buttons
        block_button.callback = show_block_select
        unblock_button.callback = show_unblock_select
        
        # Create main view with block/unblock options
        view = View()
        view.add_item(block_button)
        view.add_item(unblock_button)
        await interaction.response.send_message("Выберите действие:", view=view, ephemeral=True)

    async def manage_access(self, interaction: disnake.MessageInteraction):
        add_moderator_button = Button(label="Добавить модератора", style=disnake.ButtonStyle.primary)
        transfer_ownership_button = Button(label="Передать канал", style=disnake.ButtonStyle.primary, custom_id="transfer_ownership")

        async def add_moderator_callback(interaction: disnake.MessageInteraction):
            select = Select(
                placeholder="Выберите пользователя для добавления модератора",
                options=[disnake.SelectOption(label=member.display_name, value=str(member.id)) for member in self.channel.guild.members if member != interaction.user]
            )

            async def select_callback(interaction: disnake.MessageInteraction):
                member_id = int(select.values[0])
                member = self.channel.guild.get_member(member_id)
                overwrites = self.channel.overwrites
                overwrites[member] = disnake.PermissionOverwrite(connect=True, manage_channels=True)
                await self.channel.edit(overwrites=overwrites)
                await interaction.response.send_message(f"{member.display_name} был добавлен как модератор канала.", ephemeral=True)

            select.callback = select_callback
            view = View()
            view.add_item(select)
            await interaction.response.send_message("Выберите пользователя для добавления модератора:", view=view, ephemeral=True)

        async def transfer_ownership_callback(interaction: disnake.MessageInteraction):
            select = Select(
                placeholder="Выберите пользователя для передачи канала",
                options=[disnake.SelectOption(label=member.display_name, value=str(member.id)) for member in self.channel.guild.members if member != interaction.user]
            )

            async def select_callback(interaction: disnake.MessageInteraction):
                member_id = int(select.values[0])
                member = self.channel.guild.get_member(member_id)
                overwrites = self.channel.overwrites
                overwrites[interaction.user] = disnake.PermissionOverwrite(connect=True)
                overwrites[member] = disnake.PermissionOverwrite(connect=True, manage_channels=True)
                await self.channel.edit(overwrites=overwrites)
                await interaction.response.send_message(f"Канал был передан {member.display_name}.", ephemeral=True)

            select.callback = select_callback
            view = View()
            view.add_item(select)
            await interaction.response.send_message("Выберите пользователя для передачи канала:", view=view, ephemeral=True)

        add_moderator_button.callback = add_moderator_callback
        transfer_ownership_button.callback = transfer_ownership_callback
        view = View()
        view.add_item(add_moderator_button)
        view.add_item(transfer_ownership_button)
        await interaction.response.send_message("Настройки доступа к управлению:", view=view, ephemeral=True)

    async def visibility_settings(self, interaction: disnake.MessageInteraction):
        options = [
            disnake.SelectOption(label="Открытый", value="open"),
            disnake.SelectOption(label="Закрытый", value="closed"),
            disnake.SelectOption(label="Скрытый", value="hidden")
        ]
        select = Select(placeholder="Выберите видимость канала", options=options)

        async def select_callback(interaction: disnake.MessageInteraction):
            value = select.values[0]
            overwrites = self.channel.overwrites
            if value == "open":
                overwrites[self.channel.guild.default_role] = disnake.PermissionOverwrite(view_channel=True)
            elif value == "closed":
                overwrites[self.channel.guild.default_role] = disnake.PermissionOverwrite(view_channel=False)
                # Снимаем мут со всех пользователей
                for member in self.channel.members:
                    await member.edit(mute=False)
            elif value == "hidden":
                overwrites[self.channel.guild.default_role] = disnake.PermissionOverwrite(view_channel=False)
                overwrites[self.channel.guild.me] = disnake.PermissionOverwrite(view_channel=True)
            await self.channel.edit(overwrites=overwrites)
            await interaction.response.send_message(f"Видимость канала установлена на {value}.", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Выберите видимость канала:", view=view, ephemeral=True)

    async def set_bitrate_and_region(self, interaction: disnake.MessageInteraction):
        bitrate_options = [
            disnake.SelectOption(label="64 Kbps", value="64000"),
            disnake.SelectOption(label="96 Kbps", value="96000"),
            disnake.SelectOption(label="128 Kbps", value="128000"),
            disnake.SelectOption(label="256 Kbps", value="256000"),
            disnake.SelectOption(label="384 Kbps", value="384000"),
            disnake.SelectOption(label="512 Kbps", value="512000"),
            disnake.SelectOption(label="768 Kbps", value="768000"),
        ]
        region_options = [
            disnake.SelectOption(label="Авто", value="auto"),
            disnake.SelectOption(label="Бразилия", value="brazil"),
            disnake.SelectOption(label="Гонконг", value="hongkong"),
            disnake.SelectOption(label="Индия", value="india"),
            disnake.SelectOption(label="Япония", value="japan"),
            disnake.SelectOption(label="Русский", value="russia"),
            disnake.SelectOption(label="Сингапур", value="singapore"),
            disnake.SelectOption(label="Южная Африка", value="southafrica"),
            disnake.SelectOption(label="США Восток", value="us-east"),
            disnake.SelectOption(label="США Центральный", value="us-central"),
            disnake.SelectOption(label="США Запад", value="us-west"),
            disnake.SelectOption(label="США Юг", value="us-south"),
        ]

        bitrate_select = Select(placeholder="Выберите битрейт", options=bitrate_options)
        region_select = Select(placeholder="Выберите регион", options=region_options)

        async def bitrate_callback(interaction: disnake.MessageInteraction):
            bitrate = int(bitrate_select.values[0])
            await self.channel.edit(bitrate=bitrate)
            await interaction.response.send_message(f"Битрейт канала установлен на {bitrate // 1000} Kbps.", ephemeral=True)

        async def region_callback(interaction: disnake.MessageInteraction):
            region = region_select.values[0]
            await self.channel.edit(rtc_region=region)
            await interaction.response.send_message(f"Регион канала установлен на {region}.", ephemeral=True)

        bitrate_select.callback = bitrate_callback
        region_select.callback = region_callback
        view = View()
        view.add_item(bitrate_select)
        view.add_item(region_select)
        await interaction.response.send_message("Выберите битрейт и регион канала:", view=view, ephemeral=True)

    async def mute_user(self, interaction: disnake.MessageInteraction):
        select = Select(
            placeholder="Выберите пользователя для мута",
            options=[disnake.SelectOption(label=member.display_name, value=str(member.id)) for member in self.channel.members]
        )

        async def select_callback(interaction: disnake.MessageInteraction):
            member_id = int(select.values[0])
            member = self.channel.guild.get_member(member_id)
            await member.edit(mute=True)
            await interaction.response.send_message(f"{member.display_name} был замучен в голосовом канале.", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Выберите пользователя для мута:", view=view, ephemeral=True)

    async def rename_channel(self, interaction: disnake.MessageInteraction):
        # Используем предопределенный класс модального окна
        modal = RenameChannelModal(channel_id=self.channel.id)
        await interaction.response.send_modal(modal)

    async def set_user_limit(self, interaction: disnake.MessageInteraction):
        # Создаем класс модального окна на месте для более надежной работы
        class UserLimitModal(Modal):
            def __init__(self, channel):
                self.channel = channel
                components = [
                    TextInput(
                        label="Лимит пользователей", 
                        placeholder="Введите лимит", 
                        custom_id="user_limit_input",
                        min_length=1,
                        max_length=2
                    )
                ]
                super().__init__(title="Установить лимит пользователей", components=components)
            
            async def callback(self, interaction: disnake.ModalInteraction):
                user_limit = int(interaction.text_values["user_limit_input"])
                await self.channel.edit(user_limit=user_limit)
                await interaction.response.send_message(f"Лимит пользователей установлен на {user_limit}.", ephemeral=True)
        
        modal = UserLimitModal(channel=self.channel)
        await interaction.response.send_modal(modal)

class VoiceChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def remove_mute(self, member):
        try:
            await member.edit(mute=False)
        except Exception as e:
            print(f"Ошибка при снятии мута с пользователя {member.display_name}: {e}")

    @commands.Cog.listener()
    async def on_voice_channel_empty(self, channel):
        if channel.category_id == CATEGORY_ID and channel.id != CREATE_VOICE_CHANNEL_ID and len(channel.members) == 0:
            for member in channel.members:
                await self.remove_mute(member)
            await channel.delete()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Проверяем, если пользователь перешел из одного канала в другой
        if before.channel and after.channel and before.channel != after.channel:
            # Снимаем мут с пользователя при переходе между каналами
            if member.voice and member.voice.mute:
                await self.remove_mute(member)
        
        # Проверяем, если канал пуст и нужно его удалить
        if before.channel:
            try:
                # Проверяем, что канал все еще существует и пуст
                channel = self.bot.get_channel(before.channel.id)
                if channel and channel.id != CREATE_VOICE_CHANNEL_ID and channel.category_id == CATEGORY_ID and len(channel.members) == 0:
                    await self.check_and_delete_channel(channel)
            except Exception as e:
                print(f"Ошибка при проверке/удалении канала: {e}")

        # Создаем новый канал, если пользователь зашел в канал создания
        if after.channel and after.channel.id == CREATE_VOICE_CHANNEL_ID:
            try:
                category = self.bot.get_channel(CATEGORY_ID)
                new_channel = await category.create_voice_channel(name=f"Канал {member.display_name}", user_limit=10)
                await member.move_to(new_channel)
                view = VoiceChannelControlView(new_channel)

                embed = disnake.Embed(
                    title="Настройки управления каналом",
                    description=""
                )
                embed.set_image(url="https://images-ext-1.discordapp.net/external/ifMuRBC67wdmv3qNn27a2WkBob8C6AuaqQyIr3nKMGg/https/message.style/cdn/images/20ad00844f868764e02ebe7d966414c0cb9c4d3f4723a384c2f1a18c148fc360.png?format=webp&quality=lossless")

                control_message = await new_channel.send(embed=embed, view=view)
                view.message = control_message
            except Exception as e:
                print(f"Ошибка при создании нового канала: {e}")

    async def check_and_delete_channel(self, channel):
        if channel and channel.category_id == CATEGORY_ID and channel.id != CREATE_VOICE_CHANNEL_ID and len(channel.members) == 0:
            # Unmute members before deletion (even though there shouldn't be any)
            for member in channel.members:
                await self.remove_mute(member)
            
            # Safely delete channel with error handling
            try:
                await channel.delete()
            except disnake.errors.NotFound:
                # Channel already deleted or not found, just log and continue
                print(f"Канал {channel.id} не найден при попытке удаления.")
            except Exception as e:
                # Handle any other exceptions
                print(f"Ошибка при удалении канала {channel.id}: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.MessageInteraction):
        if not hasattr(interaction, 'data') or not interaction.data.get('custom_id'):
            return
            
        custom_id = interaction.data.get('custom_id')
        if custom_id in [
            "kick_user", "block_user", "manage_access", "visibility_settings", 
            "set_bitrate_and_region", "mute_user", "rename_channel", "set_user_limit"
        ]:
            channel_id = interaction.channel_id
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("Канал не найден.", ephemeral=True)
                return
                
            view = VoiceChannelControlView(channel)
            method = getattr(view, custom_id, None)
            if method:
                await method(interaction)
            else:
                print(f"Метод {custom_id} не найден в VoiceChannelControlView")
                await interaction.response.send_message("Эта функция находится в разработке.", ephemeral=True)

def setup(bot):
    bot.add_cog(VoiceChannelCog(bot))