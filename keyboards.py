from datetime import datetime, timedelta
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import ZONES, ZONE_SEATS


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📅 Забронировать"),
        KeyboardButton(text="🗂 Мои брони"),
    )
    builder.row(
        KeyboardButton(text="💰 Прайс"),
        KeyboardButton(text="ℹ️ О клубе"),
    )
    builder.row(KeyboardButton(text="👤 Профиль"))
    if is_admin:
        builder.row(KeyboardButton(text="🔧 Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def zones_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in ZONES.items():
        builder.button(text=label, callback_data=f"zone:{key}")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def dates_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = datetime.now()
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i in range(7):
        d = today + timedelta(days=i)
        label = ("Сегодня" if i == 0 else "Завтра" if i == 1 else
                 f"{day_names[d.weekday()]} {d.strftime('%d.%m')}")
        builder.button(text=label, callback_data=f"date:{d.strftime('%Y-%m-%d')}")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2)
    return builder.as_markup()


def times_keyboard(prefix: str, date_str: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    hours = [
        "08:00","09:00","10:00","11:00","12:00","13:00",
        "14:00","15:00","16:00","17:00","18:00","19:00",
        "20:00","21:00","22:00","23:00","00:00","01:00",
    ]
    # Если выбрана сегодняшняя дата — убрать прошедшее время
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    for h in hours:
        if date_str == today_str:
            hh = int(h.split(":")[0])
            cur = now.hour
            if hh != 0 and hh <= cur:
                continue
        builder.button(text=h, callback_data=f"{prefix}:{h}")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(3)
    return builder.as_markup()


def seats_keyboard(zone: str, booked: set) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total = ZONE_SEATS.get(zone, 1)
    for i in range(1, total + 1):
        if i in booked:
            builder.button(text=f"🔴 {i}", callback_data="seat_busy")
        else:
            builder.button(text=f"🟢 {i}", callback_data=f"seat:{i}")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(5)
    return builder.as_markup()


def skip_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_comment")
    ]])


def confirm_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="do_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
    ]])


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel:{booking_id}")
    ]])


def confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm_confirm:{booking_id}"),
        InlineKeyboardButton(text="❌ Отклонить",  callback_data=f"adm_reject:{booking_id}"),
    ]])
