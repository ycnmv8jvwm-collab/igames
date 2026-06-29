import re
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, Contact

import database as db
from config import (
    ADMIN_ID, CLUB_NAME, CLUB_ADDRESS, CLUB_HOURS,
    CLUB_PHONE, PRICE_LIST, ZONES, TOTAL_SEATS,
)
from keyboards import (
    main_menu, phone_keyboard, zones_keyboard,
    seats_keyboard, cancel_booking_kb, confirm_kb, back_kb,
)
from states import RegisterSG, BookingSG

main_router = Router()

db.init_db()


# ─────────────────────────────────────────────────────
#  УТИЛИТЫ
# ─────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def zone_label(key: str) -> str:
    return ZONES.get(key, key)


def fmt_booking(b) -> str:
    status_map = {"pending": "⏳ Ожидает", "confirmed": "✅ Подтверждено", "cancelled": "❌ Отменено"}
    status = status_map.get(b["status"], b["status"])
    return (
        f"🆔 #{b['id']} | {zone_label(b['zone'])}, место {b['seat']}\n"
        f"📅 {b['date']}  🕐 {b['time_from']}–{b['time_to']}\n"
        f"Статус: {status}"
        + (f"\n💬 {b['comment']}" if b["comment"] else "")
    )


# ─────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────

@main_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    db.upsert_user(user.id, user.username or "", user.full_name)

    existing = db.get_user(user.id)
    admin = is_admin(user.id)

    if existing and existing["phone"]:
        await message.answer(
            f"👋 Привет, {user.first_name}! Добро пожаловать в <b>{CLUB_NAME}</b>.",
            reply_markup=main_menu(admin),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"👋 Привет! Я бот компьютерного клуба <b>{CLUB_NAME}</b>.\n\n"
            "Для продолжения поделись своим номером телефона 👇",
            reply_markup=phone_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(RegisterSG.phone)


# ─────────────────────────────────────────────────────
#  РЕГИСТРАЦИЯ
# ─────────────────────────────────────────────────────

@main_router.message(RegisterSG.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext):
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, поделитесь своим номером, а не чужим.")
        return

    db.save_phone(message.from_user.id, contact.phone_number)
    await state.clear()
    await message.answer(
        "✅ Номер сохранён! Теперь вы можете пользоваться ботом.",
        reply_markup=main_menu(is_admin(message.from_user.id)),
    )


@main_router.message(RegisterSG.phone)
async def reg_phone_text(message: Message):
    await message.answer("Пожалуйста, нажмите кнопку «Поделиться номером» ниже.")


# ─────────────────────────────────────────────────────
#  ИНФОРМАЦИЯ
# ─────────────────────────────────────────────────────

@main_router.message(F.text == "ℹ️ О клубе")
async def about(message: Message):
    await message.answer(
        f"🏢 <b>{CLUB_NAME}</b>\n\n"
        f"📍 {CLUB_ADDRESS}\n"
        f"🕐 {CLUB_HOURS}\n"
        f"📞 {CLUB_PHONE}",
        parse_mode="HTML",
    )


@main_router.message(F.text == "💰 Прайс")
async def price(message: Message):
    await message.answer(f"💰 <b>Прайс-лист {CLUB_NAME}</b>\n{PRICE_LIST}", parse_mode="HTML")


# ─────────────────────────────────────────────────────
#  ПРОФИЛЬ
# ─────────────────────────────────────────────────────

@main_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    u = db.get_user(message.from_user.id)
    bookings = db.get_user_bookings(message.from_user.id)
    active = [b for b in bookings if b["status"] in ("pending", "confirmed")]
    phone = u["phone"] if u and u["phone"] else "не указан"
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"Имя: {message.from_user.full_name}\n"
        f"Телефон: {phone}\n"
        f"Активных броней: {len(active)}",
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────
#  МОИ БРОНИ
# ─────────────────────────────────────────────────────

@main_router.message(F.text == "🗂 Мои брони")
async def my_bookings(message: Message):
    rows = db.get_user_bookings(message.from_user.id)
    if not rows:
        await message.answer("У вас ещё нет броней.")
        return

    for b in rows:
        if b["status"] != "cancelled":
            await message.answer(
                fmt_booking(b),
                reply_markup=cancel_booking_kb(b["id"]) if b["status"] in ("pending", "confirmed") else None,
            )


@main_router.callback_query(F.data.startswith("cancel:"))
async def user_cancel(call: CallbackQuery):
    booking_id = int(call.data.split(":")[1])
    db.cancel_booking(booking_id, call.from_user.id)
    await call.message.edit_text("❌ Бронь отменена.")
    await call.answer("Бронь отменена.")


# ─────────────────────────────────────────────────────
#  БРОНИРОВАНИЕ — FSM
# ─────────────────────────────────────────────────────

@main_router.message(F.text == "📅 Забронировать")
async def book_start(message: Message, state: FSMContext):
    u = db.get_user(message.from_user.id)
    if not u or not u["phone"]:
        await message.answer("Сначала зарегистрируйтесь: введите /start")
        return
    await state.set_state(BookingSG.zone)
    await message.answer("Выберите зону:", reply_markup=zones_keyboard())


@main_router.callback_query(BookingSG.zone, F.data.startswith("zone:"))
async def book_zone(call: CallbackQuery, state: FSMContext):
    zone = call.data.split(":")[1]
    await state.update_data(zone=zone)
    await state.set_state(BookingSG.date)

    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    dates_str = "\n".join(f"• {d}" for d in dates)
    await call.message.edit_text(
        f"Выбрана зона: <b>{zone_label(zone)}</b>\n\n"
        f"Введите дату бронирования в формате <b>ГГГГ-ММ-ДД</b>\n\n"
        f"Доступные даты:\n{dates_str}",
        parse_mode="HTML",
    )
    await call.answer()


@main_router.callback_query(F.data == "cancel_booking")
async def cancel_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Бронирование отменено.")
    await call.answer()


@main_router.message(BookingSG.date)
async def book_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date.date() < datetime.now().date():
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат или прошедшая дата. Введите дату в формате ГГГГ-ММ-ДД.")
        return

    await state.update_data(date=date_str)
    await state.set_state(BookingSG.time_from)
    await message.answer("Введите время начала в формате <b>ЧЧ:ММ</b> (например, 14:00):", parse_mode="HTML")


@main_router.message(BookingSG.time_from)
async def book_time_from(message: Message, state: FSMContext):
    t = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", t):
        await message.answer("❌ Формат: ЧЧ:ММ")
        return
    await state.update_data(time_from=t)
    await state.set_state(BookingSG.time_to)
    await message.answer("Введите время окончания (например, 16:00):")


@main_router.message(BookingSG.time_to)
async def book_time_to(message: Message, state: FSMContext):
    t = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", t):
        await message.answer("❌ Формат: ЧЧ:ММ")
        return

    data = await state.get_data()
    if t <= data["time_from"]:
        await message.answer("❌ Время окончания должно быть позже начала.")
        return

    await state.update_data(time_to=t)
    await state.set_state(BookingSG.seat)

    booked = db.get_booked_seats(data["zone"], data["date"], data["time_from"], t)
    await message.answer(
        f"🟢 — свободно  🔴 — занято\n\nВыберите место (1–{TOTAL_SEATS}):",
        reply_markup=seats_keyboard(data["zone"], booked),
    )


@main_router.callback_query(F.data == "seat_busy")
async def seat_busy(call: CallbackQuery):
    await call.answer("Это место занято на выбранное время.", show_alert=True)


@main_router.callback_query(BookingSG.seat, F.data.startswith("seat:"))
async def book_seat(call: CallbackQuery, state: FSMContext):
    seat = int(call.data.split(":")[1])
    await state.update_data(seat=seat)
    await state.set_state(BookingSG.comment)
    await call.message.edit_text("Добавьте комментарий к брони (или напишите «нет»):")
    await call.answer()


@main_router.message(BookingSG.comment)
async def book_comment(message: Message, state: FSMContext):
    comment = "" if message.text.lower() in ("нет", "-", "") else message.text
    await state.update_data(comment=comment)
    data = await state.get_data()

    summary = (
        f"📋 <b>Проверьте данные брони:</b>\n\n"
        f"Зона: {zone_label(data['zone'])}\n"
        f"Место: #{data['seat']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time_from']} – {data['time_to']}\n"
        + (f"Комментарий: {comment}\n" if comment else "")
        + "\nПодтвердить? Напишите <b>да</b> или <b>нет</b>."
    )
    await state.set_state(BookingSG.confirm)
    await message.answer(summary, parse_mode="HTML")


@main_router.message(BookingSG.confirm)
async def book_confirm(message: Message, state: FSMContext, bot: Bot):
    if message.text.lower() not in ("да", "yes", "✅", "+"):
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(is_admin(message.from_user.id)))
        return

    data = await state.get_data()

    # Проверяем, что место всё ещё свободно
    booked = db.get_booked_seats(data["zone"], data["date"], data["time_from"], data["time_to"])
    if data["seat"] in booked:
        await state.clear()
        await message.answer(
            "❌ К сожалению, это место уже заняли. Попробуйте выбрать другое.",
            reply_markup=main_menu(is_admin(message.from_user.id)),
        )
        return

    bid = db.create_booking(
        user_id=message.from_user.id,
        zone=data["zone"],
        seat=data["seat"],
        date=data["date"],
        time_from=data["time_from"],
        time_to=data["time_to"],
        comment=data.get("comment", ""),
    )
    await state.clear()

    u = db.get_user(message.from_user.id)
    await message.answer(
        f"✅ Бронь #{bid} принята! Ждём подтверждения администратора.",
        reply_markup=main_menu(is_admin(message.from_user.id)),
    )

    # Уведомление администратору
    text = (
        f"🔔 <b>Новая бронь #{bid}</b>\n\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
        f"📞 {u['phone'] if u else '—'}\n\n"
        f"Зона: {zone_label(data['zone'])}, место {data['seat']}\n"
        f"📅 {data['date']}  🕐 {data['time_from']}–{data['time_to']}\n"
        + (f"💬 {data['comment']}" if data.get("comment") else "")
    )
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML", reply_markup=confirm_kb(bid))
    except Exception:
        pass


# ─────────────────────────────────────────────────────
#  АДМИН-ПАНЕЛЬ
# ─────────────────────────────────────────────────────

@main_router.message(F.text == "🔧 Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = db.all_users_count()
    bookings = db.all_bookings_count()
    today = db.all_bookings_today()

    text = (
        f"🔧 <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: {users}\n"
        f"📅 Всего броней: {bookings}\n"
        f"📋 Броней сегодня: {len(today)}\n\n"
    )

    if today:
        text += "<b>Сегодняшние брони:</b>\n"
        for b in today:
            text += (
                f"• #{b['id']} {b['time_from']}–{b['time_to']} | "
                f"{zone_label(b['zone'])} #{b['seat']} | "
                f"{b['full_name']} | {b['status']}\n"
            )

    await message.answer(text, parse_mode="HTML")


@main_router.message(Command("pending"))
async def admin_pending(message: Message):
    if not is_admin(message.from_user.id):
        return
    rows = db.all_pending()
    if not rows:
        await message.answer("Нет ожидающих броней.")
        return
    for b in rows:
        text = (
            f"⏳ <b>Бронь #{b['id']}</b>\n"
            f"👤 {b['full_name']} (@{b['username'] or '—'})\n"
            f"📞 {b['phone'] or '—'}\n"
            f"Зона: {zone_label(b['zone'])}, место {b['seat']}\n"
            f"📅 {b['date']}  🕐 {b['time_from']}–{b['time_to']}"
            + (f"\n💬 {b['comment']}" if b["comment"] else "")
        )
        await message.answer(text, parse_mode="HTML", reply_markup=confirm_kb(b["id"]))


@main_router.callback_query(F.data.startswith("adm_confirm:"))
async def adm_confirm(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    bid = int(call.data.split(":")[1])
    db.confirm_booking(bid)
    await call.message.edit_text(f"✅ Бронь #{bid} подтверждена.")

    # Уведомить пользователя
    rows = db.get_user_bookings.__wrapped__ if hasattr(db.get_user_bookings, "__wrapped__") else None
    # получаем бронь из БД напрямую
    import sqlite3
    with sqlite3.connect("club.db") as conn:
        conn.row_factory = sqlite3.Row
        b = conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
    if b:
        try:
            await bot.send_message(
                b["user_id"],
                f"✅ Ваша бронь #{bid} подтверждена!\n"
                f"📅 {b['date']}  🕐 {b['time_from']}–{b['time_to']}\n"
                f"Ждём вас в клубе! 🎮",
            )
        except Exception:
            pass
    await call.answer("Подтверждено!")


@main_router.callback_query(F.data.startswith("adm_reject:"))
async def adm_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    bid = int(call.data.split(":")[1])
    import sqlite3
    with sqlite3.connect("club.db") as conn:
        conn.row_factory = sqlite3.Row
        b = conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (bid,))

    await call.message.edit_text(f"❌ Бронь #{bid} отклонена.")
    if b:
        try:
            await bot.send_message(
                b["user_id"],
                f"❌ К сожалению, ваша бронь #{bid} была отклонена.\n"
                "Свяжитесь с клубом для уточнения деталей.",
            )
        except Exception:
            pass
    await call.answer("Отклонено.")
