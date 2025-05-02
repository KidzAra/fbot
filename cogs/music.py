import asyncio
import random
import disnake
from disnake.ext import commands
import yt_dlp
from collections import deque
from config import FFMPEG_OPTIONS, MUSIC_CONTROL_CHANNEL_ID

# YT-DLP configuration
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

class Song:
    """Класс, представляющий песню в очереди"""
    def __init__(self, source, title, url, duration, requested_by):
        self.source = source
        self.title = title
        self.url = url
        self.duration = duration
        self.requested_by = requested_by

    @classmethod
    async def create(cls, search, requester, bot):
        """Создает объект Song из поискового запроса или URL"""
        loop = bot.loop or asyncio.get_event_loop()
        
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(search, download=False))
                
                if 'entries' in info:
                    # Берем первый результат из плейлиста
                    info = info['entries'][0]
                    
                title = info['title']
                url = info['webpage_url']
                source = info['url']
                
                # Форматируем длительность в минутах:секундах
                duration_seconds = info.get('duration', 0)
                minutes, seconds = divmod(duration_seconds, 60)
                duration = f"{minutes}:{seconds:02d}"
                
                return cls(source, title, url, duration, requester)
        except Exception as e:
            raise commands.CommandError(f"Ошибка при обработке трека: {str(e)}")

class MusicPlayer:
    """Класс для управления воспроизведением музыки для сервера"""
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.queue = deque()
        self.current = None
        self.voice_client = None
        self.loop = False  # Повторять ли текущий трек
        self.control_message = None

    def next(self):
        """Воспроизводит следующий трек в очереди"""
        if self.voice_client and self.voice_client.is_connected():
            if self.loop and self.current:
                # Если включен режим повтора, добавляем текущий трек в начало очереди
                self.queue.appendleft(self.current)
            
            if self.queue:
                self.current = self.queue.popleft()
                audio = disnake.FFmpegPCMAudio(self.current.source, **FFMPEG_OPTIONS)
                self.voice_client.play(audio, after=lambda e: self.play_next(e))
                return True
            else:
                self.current = None
                # Планируем отключение бота после задержки, если больше нет песен
                asyncio.run_coroutine_threadsafe(self.disconnect_after_timeout(300), self.bot.loop)
                return False

    def play_next(self, error=None):
        """Обратный вызов по окончании трека"""
        if error:
            print(f"Ошибка воспроизведения: {error}")
        
        if not self.next() and self.control_message:
            # Если больше нет треков, обновляем панель управления
            asyncio.run_coroutine_threadsafe(self.update_control_panel(), self.bot.loop)

    async def update_control_panel(self):
        """Обновляет панель управления"""
        if not self.control_message:
            return
            
        try:
            embed = self.create_queue_embed()
            await self.control_message.edit(embed=embed)
        except Exception as e:
            print(f"Ошибка обновления панели управления: {e}")

    def create_queue_embed(self):
        """Создает embed для текущей очереди"""
        embed = disnake.Embed(title="🎵 Музыкальный плеер", color=disnake.Color.blurple())
        
        # Текущий трек
        if self.current:
            embed.add_field(
                name="🔊 Сейчас играет",
                value=f"[{self.current.title}]({self.current.url}) | `{self.current.duration}` | {self.current.requested_by.mention}",
                inline=False
            )
        else:
            embed.add_field(name="🔊 Сейчас играет", value="Ничего не воспроизводится", inline=False)
        
        # Очередь
        if self.queue:
            queue_text = "\n".join([
                f"`{i+1}.` [{song.title}]({song.url}) | `{song.duration}` | {song.requested_by.mention}"
                for i, song in enumerate(list(self.queue)[:5])
            ])
            
            if len(self.queue) > 5:
                queue_text += f"\n\n... и еще {len(self.queue) - 5} треков"
                
            embed.add_field(name="📋 Очередь", value=queue_text, inline=False)
        else:
            embed.add_field(name="📋 Очередь", value="Очередь пуста", inline=False)
        
        # Статус
        status = []
        if self.loop:
            status.append("🔁 Повтор: Включен")
        else:
            status.append("🔁 Повтор: Выключен")
            
        if self.voice_client and self.voice_client.is_paused():
            status.append("⏸️ Статус: Пауза")
        elif self.current:
            status.append("▶️ Статус: Воспроизведение")
        else:
            status.append("⏹️ Статус: Остановлено")
            
        embed.add_field(name="⚙️ Статус", value="\n".join(status), inline=False)
        
        return embed

    async def disconnect_after_timeout(self, timeout):
        """Отключает бота от голосового канала после указанного тайм-аута, если ничего не воспроизводится"""
        await asyncio.sleep(timeout)
        if self.voice_client and self.voice_client.is_connected() and not self.voice_client.is_playing():
            await self.voice_client.disconnect()
            if self.control_message:
                await self.update_control_panel()

class MusicControlView(disnake.ui.View):
    """Представление для кнопок панели управления музыкой"""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @disnake.ui.button(emoji="⏯️", style=disnake.ButtonStyle.primary, custom_id="music:playpause")
    async def playpause_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = self.cog.get_player(interaction.guild)
        if not player or not player.voice_client:
            return await interaction.followup.send("Бот не подключен к голосовому каналу!", ephemeral=True)
        
        if player.voice_client.is_paused():
            await self.cog.resume_command(interaction)
        else:
            await self.cog.pause_command(interaction)
    
    @disnake.ui.button(emoji="⏭️", style=disnake.ButtonStyle.primary, custom_id="music:skip")
    async def skip_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.skip_command(interaction)
    
    @disnake.ui.button(emoji="⏹️", style=disnake.ButtonStyle.danger, custom_id="music:stop")
    async def stop_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.stop_command(interaction)
    
    @disnake.ui.button(emoji="🔁", style=disnake.ButtonStyle.secondary, custom_id="music:loop")
    async def loop_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = self.cog.get_player(interaction.guild)
        if not player or not player.voice_client:
            return await interaction.followup.send("Бот не подключен к голосовому каналу!", ephemeral=True)
        
        player.loop = not player.loop
        await interaction.followup.send(f"Режим повтора {'включен' if player.loop else 'выключен'}", ephemeral=True)
        await player.update_control_panel()
    
    @disnake.ui.button(emoji="🔀", style=disnake.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = self.cog.get_player(interaction.guild)
        if not player or not player.voice_client:
            return await interaction.followup.send("Бот не подключен к голосовому каналу!", ephemeral=True)
        
        if not player.queue:
            return await interaction.followup.send("В очереди нет треков для перемешивания!", ephemeral=True)
        
        queue_list = list(player.queue)
        random.shuffle(queue_list)
        player.queue = deque(queue_list)
        
        await interaction.followup.send("Очередь перемешана!", ephemeral=True)
        await player.update_control_panel()

class MusicCog(commands.Cog):
    """Музыкальные команды для Discord бота"""
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.control_view = MusicControlView(self)
        
        # Регистрируем постоянное представление
        bot.add_view(self.control_view)
    
    def get_player(self, guild):
        """Получает или создает MusicPlayer для сервера"""
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]
    
    async def ensure_voice(self, interaction: disnake.Interaction):
        """Проверяет, что бот подключен к голосовому каналу и пользователь находится в том же канале"""
        player = self.get_player(interaction.guild)
        
        if not interaction.author.voice:
            raise commands.CommandError("Вы должны находиться в голосовом канале, чтобы использовать эту команду!")
        
        if not player.voice_client:
            player.voice_client = await interaction.author.voice.channel.connect()
        elif player.voice_client.channel != interaction.author.voice.channel:
            raise commands.CommandError("Вы должны находиться в том же голосовом канале, что и бот!")
        
        return player
    
    @commands.slash_command(name="play", description="Воспроизводит трек с YouTube")
    async def play_command(self, interaction: disnake.Interaction, query: str):
        await interaction.response.defer()
        
        try:
            player = await self.ensure_voice(interaction)
            
            # Создаем объект трека
            song = await Song.create(query, interaction.author, self.bot)
            player.queue.append(song)
            
            await interaction.followup.send(f"Добавлено в очередь: **{song.title}**")
            
            # Если ничего не воспроизводится, начинаем воспроизведение
            if not player.voice_client.is_playing() and not player.voice_client.is_paused():
                player.next()
            
            # Обновляем панель управления, если она существует
            if player.control_message:
                await player.update_control_panel()
            
        except commands.CommandError as e:
            await interaction.followup.send(f"Ошибка: {str(e)}")
        except Exception as e:
            print(f"Ошибка команды play: {e}")
            await interaction.followup.send("Произошла ошибка при обработке вашего запроса.")
    
    @commands.slash_command(name="pause", description="Ставит текущий трек на паузу")
    async def pause_command(self, interaction: disnake.Interaction):
        try:
            player = await self.ensure_voice(interaction)
            
            if not player.voice_client.is_playing():
                return await interaction.response.send_message("Сейчас ничего не воспроизводится!", ephemeral=True)
            
            if player.voice_client.is_paused():
                return await interaction.response.send_message("Музыка уже на паузе!", ephemeral=True)
            
            player.voice_client.pause()
            await interaction.response.send_message("Воспроизведение приостановлено ⏸️", ephemeral=True)
            
            # Обновляем панель управления
            await player.update_control_panel()
            
        except commands.CommandError as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
    
    @commands.slash_command(name="resume", description="Возобновляет воспроизведение текущего трека")
    async def resume_command(self, interaction: disnake.Interaction):
        try:
            player = await self.ensure_voice(interaction)
            
            if not player.voice_client.is_paused():
                return await interaction.response.send_message("Музыка не на паузе!", ephemeral=True)
            
            player.voice_client.resume()
            await interaction.response.send_message("Воспроизведение возобновлено ▶️", ephemeral=True)
            
            # Обновляем панель управления
            await player.update_control_panel()
            
        except commands.CommandError as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
    
    @commands.slash_command(name="skip", description="Пропускает текущий трек")
    async def skip_command(self, interaction: disnake.Interaction):
        try:
            player = await self.ensure_voice(interaction)
            
            if not player.voice_client.is_playing() and not player.voice_client.is_paused():
                return await interaction.response.send_message("Сейчас ничего не воспроизводится!", ephemeral=True)
            
            player.voice_client.stop()
            await interaction.response.send_message("Трек пропущен ⏭️", ephemeral=True)
            
        except commands.CommandError as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
    
    @commands.slash_command(name="stop", description="Останавливает воспроизведение и очищает очередь")
    async def stop_command(self, interaction: disnake.Interaction):
        try:
            player = await self.ensure_voice(interaction)
            
            if player.queue:
                player.queue.clear()
            
            if player.voice_client.is_playing() or player.voice_client.is_paused():
                player.voice_client.stop()
                player.current = None
                
            await interaction.response.send_message("Воспроизведение остановлено и очередь очищена ⏹️", ephemeral=True)
            
            # Обновляем панель управления
            await player.update_control_panel()
            
        except commands.CommandError as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
    
    @commands.slash_command(name="queue", description="Показывает текущую очередь треков")
    async def queue_command(self, interaction: disnake.Interaction):
        player = self.get_player(interaction.guild)
        
        if not player.current and not player.queue:
            return await interaction.response.send_message("Очередь пуста!", ephemeral=True)
        
        embed = player.create_queue_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="setup_music_panel", description="Создает панель управления музыкой")
    @commands.has_permissions(administrator=True)
    async def setup_panel_command(self, interaction: disnake.Interaction, channel: disnake.TextChannel = None):
        target_channel = channel or interaction.channel
        player = self.get_player(interaction.guild)
        
        embed = player.create_queue_embed()
        control_message = await target_channel.send(embed=embed, view=self.control_view)
        player.control_message = control_message
        
        await interaction.response.send_message(f"Панель управления музыкой создана в канале {target_channel.mention}", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обрабатывает отключение бота, когда последний пользователь покидает голосовой канал"""
        # Пропускаем, если это изменение голосового состояния бота
        if member.id == self.bot.user.id:
            return
            
        # Проверяем, находится ли бот в голосовом канале на этом сервере
        if before.channel is not None and self.bot.user in before.channel.members:
            # Если голосовой канал теперь пуст (кроме бота)
            if len([m for m in before.channel.members if not m.bot]) == 0:
                # Получаем плеер для этого сервера
                guild = before.channel.guild
                player = self.get_player(guild)
                
                # Планируем отключение после таймаута
                if player.voice_client and player.voice_client.is_connected():
                    # Если что-то воспроизводится, планируем отключение по окончании
                    if player.voice_client.is_playing():
                        pass  # Будет обработано disconnect_after_timeout по окончании трека
                    else:
                        # Иначе, планируем немедленный таймаут
                        asyncio.create_task(player.disconnect_after_timeout(60))  # 60 секунд таймаута

def setup(bot):
    bot.add_cog(MusicCog(bot)) 