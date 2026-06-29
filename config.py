import os

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8854421229:AAEZFerjkAodSLpbVItnpArCma9XKYUTz94")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7885240347"))

CLUB_NAME = "iGames"
CLUB_ADDRESS = "ул. Карла Маркса, 144, Магнитогорск"
CLUB_HOURS = "Пн–Чт: 10:00–00:00\nПт–Вс: 10:00–02:00"
CLUB_PHONE = "+7 922 638 8051"

# Количество мест по зонам
ZONE_SEATS = {
    "pc":  11,   # Общий зал
    "vip":  5,   # VIP
    "ps5":  1,   # PS
}

TOTAL_SEATS = max(ZONE_SEATS.values())  # для совместимости

PRICE_LIST = """
💻 *Общий зал* — 100 ₽/час (11 ПК)
🎮 *VIP-место* — 150 ₽/час (5 мест)
🕹 *PlayStation* — 200 ₽/час (1 место)
🌙 *Ночной тариф (00:00–08:00)* — скидка 30%
📦 *Пакет 5 часов* — 400 ₽
📦 *Пакет 10 часов* — 750 ₽
"""

ZONES = {
    "pc":  "💻 Общий зал",
    "vip": "🎮 VIP-место",
    "ps5": "🕹 PlayStation",
}
