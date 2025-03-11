import disnake
from datetime import datetime, timedelta

# Хранилище для предупреждений и статистики пользователей
warnings = {}
statistics = {}

async def send_log_message(bot, channel_id, message):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(message)

async def warn_user(bot, user, reason):
    try:
        await user.send(f"Вам выдано предупреждение по причине: {reason}")
    except disnake.HTTPException:
        pass

async def apply_timeout(user: disnake.Member, warns_count: int):
    duration = calculate_timeout_duration(warns_count)
    if duration is not None:
        await user.timeout(duration=datetime.utcnow() + timedelta(minutes=duration))

def calculate_timeout_duration(warns_count):
    if warns_count == 1:
        return 5  # 5 минут
    elif warns_count == 2:
        return 10  # 10 минут
    elif warns_count == 3:
        return 30  # 30 минут
    elif warns_count == 4:
        return 60  # 1 час
    elif warns_count == 5:
        return 180  # 3 часа
    elif warns_count == 6:
        return 720  # 12 часов
    elif warns_count == 7:
        return 1440  # 1 день
    elif warns_count == 8:
        return 10080  # 7 дней
    elif warns_count == 9:
        return None  # полная блокировка
    return 0

def save_warning_to_memory(user_id, reason):
    if user_id not in warnings:
        warnings[user_id] = []
    warnings[user_id].append({
        "reason": reason,
        "timestamp": datetime.utcnow()
    })

def get_user_warnings(user_id):
    return len(warnings.get(user_id, []))

def get_user_statistics(user_id):
    now = datetime.utcnow()
    warns_1d = sum(1 for warn in warnings.get(user_id, []) if (now - warn["timestamp"]).days < 1)
    warns_7d = sum(1 for warn in warnings.get(user_id, []) if (now - warn["timestamp"]).days < 7)
    warns_1m = sum(1 for warn in warnings.get(user_id, []) if (now - warn["timestamp"]).days < 30)
    warns_all = get_user_warnings(user_id)
    
    # Примерная статистика по обращениям (здесь нужно настроить ваш способ подсчета обращений)
    appeals_1d = 0
    appeals_7d = 0
    appeals_1m = 0
    appeals_all = 0
    
    return {
        'warns_1d': warns_1d,
        'warns_7d': warns_7d,
        'warns_1m': warns_1m,
        'warns_all': warns_all,
        'appeals_1d': appeals_1d,
        'appeals_7d': appeals_7d,
        'appeals_1m': appeals_1m,
        'appeals_all': appeals_all
    }
