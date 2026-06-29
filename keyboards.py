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


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel:{booking_id}")
    ]])


def confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm_confirm:{booking_id}"),
        InlineKeyboardButton(text="❌ Отклонить",  callback_data=f"adm_reject:{booking_id}"),
    ]])
