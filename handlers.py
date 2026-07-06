import re
import sqlite3
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, Contact

import database as db
from config import (
    ADMIN_ID, CLUB_NAME, CLUB_ADDRESS, CLUB_HOURS,
    CLUB_PHONE, PRICE_LIST, ZONES,
)
from keyboards import (
    main_menu, phone_keyboard, zones_keyboard, dates_keyboard,
    seats_keyboard, skip_comment_kb,
    confirm_booking_kb, cancel_booking_kb, confirm_kb, cancel_admin_msg_kb,
)
from states import RegisterSG, BookingSG, AdminMessageSG

main_router = Router()
db.init_db()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def zone_label(key: str) -> str:
    return ZONES.get(key, key)


def fmt_booking(b) -> str:
    status_map = {"pending": "⏳ Ожидает", "confirmed": "✅ Подтверждено", "cancelled": "❌ Отменено"}
    status = status_map.get(b["status"], b["status"])
    return (
        f"🆔 #{b['id']} | {zone_label(b['zone'])}, место {b['seat']}\n"
        f"📅 {b['date']}  🕐 {b['time_from']} (держится 15 мин)\n"
        f"Статус: {status}"
        + (f"\n💬 {b['comment']}" if b["comment"] else "")
    )


# ── /start ──────────────────────────────────────────

@main_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    db.upsert_user(user.id, user.username or "", user.full_name)
    existing = db.get_user(user.id)
    admin = is_admin(user.id)

    if existing and existing["phone"]:
        await message.answer(
            f"👋 Привет, {user.first_name}! Добро пожаловать в <b>{CLUB_NAME}</b>.",
            reply_markup=main_menu(admin), parse_mode="HTML",
        )
    else:
        await message.answer(
            f"👋 Привет! Я бот компьютерного клуба <b>{CLUB_NAME}</b>.\n\n"
            "Поделись своим номером телефона для регистрации 👇",
            reply_markup=phone_keyboard(), parse_mode="HTML",
        )
        await state.set_state(RegisterSG.phone)


# ── Регистрация ──────────────────────────────────────

@main_router.message(RegisterSG.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext):
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, поделитесь своим номером.")
        return
    db.save_phone(message.from_user.id, contact.phone_number)
    await state.clear()
    await message.answer(
        "✅ Готово! Теперь вы можете пользоваться ботом.",
        reply_markup=main_menu(is_admin(message.from_user.id)),
    )


@main_router.message(RegisterSG.phone)
async def reg_phone_text(message: Message):
    await message.answer("Нажмите кнопку «Поделиться номером» ниже.")


# ── Информация ───────────────────────────────────────

@main_router.message(F.text == "ℹ️ О клубе")
async def about(message: Message):
    await message.answer(
        f"🏢 <b>{CLUB_NAME}</b>\n\n📍 {CLUB_ADDRESS}\n🕐 {CLUB_HOURS}\n📞 {CLUB_PHONE}",
        parse_mode="HTML",
    )


@main_router.message(F.text == "💰 Прайс")
async def price(message: Message):
    await message.answer(
        f"💰 <b>Тарифы {CLUB_NAME}</b>\n{PRICE_LIST}",
        parse_mode="Markdown",
    )


@main_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    u = db.get_user(message.from_user.id)
    bookings = db.get_user_bookings(message.from_user.id)
    active = [b for b in bookings if b["status"] in ("pending", "confirmed")]
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\nИмя: {message.from_user.full_name}\n"
        f"Телефон: {u['phone'] if u and u['phone'] else 'не указан'}\n"
        f"Активных броней: {len(active)}",
        parse_mode="HTML",
    )


# ── Мои брони ────────────────────────────────────────

@main_router.message(F.text == "🗂 Мои брони")
async def my_bookings(message: Message):
    rows = db.get_user_bookings(message.from_user.id)
    active = [b for b in rows if b["status"] != "cancelled"]
    if not active:
        await message.answer("У вас ещё нет активных броней.")
        return
    for b in active:
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



# ── Данные из мини-приложения ────────────────────────

@main_router.message(F.web_app_data)
async def web_app_data_handler(message: Message, bot: Bot):
    import json
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        return

    user = message.from_user
    db.upsert_user(user.id, user.username or "", user.full_name)
    u = db.get_user(user.id)

    if data.get("type") == "booking":
        zone  = data.get("zone", "")
        seat  = data.get("seat", "?")
        date  = data.get("dateStr", "?")
        time  = data.get("time", "?")
        comment = data.get("comment", "")

        # Вычислить time_to (+15 минут)
        try:
            h, m = map(int, time.split(":"))
            total = h * 60 + m + 15
            time_to = f"{(total // 60) % 24:02d}:{total % 60:02d}"
        except Exception:
            time_to = time

        bid = db.create_booking(
            user_id=user.id,
            zone=zone,
            seat=int(seat),
            date=date,
            time_from=time,
            time_to=time_to,
            comment=comment,
        )

        await message.answer(
            f"✅ Бронь <b>#{bid}</b> принята!\n"
            f"📅 {date}  🕐 {time} (держится 15 мин)\n\n"
            "Ожидайте подтверждения администратора.",
            parse_mode="HTML",
        )

        # Уведомление администратору
        text = (
            f"🔔 <b>Новая бронь #{bid}</b> (мини-приложение)\n\n"
            f"👤 {user.full_name} (@{user.username or '—'})\n"
            f"📞 {u['phone'] if u and u['phone'] else '—'}\n\n"
            f"Зона: {zone_label(zone)}, место {seat}\n"
            f"📅 {date}  🕐 {time} (держится 15 мин)"
            + (f"\n💬 {comment}" if comment else "")
        )
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode="HTML", reply_markup=confirm_kb(bid))
        except Exception:
            pass

    elif data.get("type") == "contact":
        msg = data.get("message", "")
        text = (
            f"📩 <b>Сообщение через мини-приложение</b>\n\n"
            f"👤 {user.full_name} (@{user.username or '—'})\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            f"💬 {msg}"
        )
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
            await message.answer("✅ Сообщение отправлено администратору!")
        except Exception:
            await message.answer("❌ Ошибка отправки.")



@main_router.message(F.text == "📞 Написать админу")
async def contact_admin_start(message: Message, state: FSMContext):
    u = db.get_user(message.from_user.id)
    if not u or not u["phone"]:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await state.set_state(AdminMessageSG.text)
    await message.answer(
        "✍️ Напишите ваше сообщение администратору — оно будет отправлено напрямую.",
        reply_markup=cancel_admin_msg_kb(),
    )


@main_router.callback_query(F.data == "cancel_admin_msg")
async def cancel_admin_msg(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Отменено.")
    await call.answer()


@main_router.message(AdminMessageSG.text)
async def contact_admin_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    u = db.get_user(user.id)

    text = (
        f"📩 <b>Сообщение от клиента</b>\n\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"📞 {u['phone'] if u and u['phone'] else '—'}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"💬 {message.text}"
    )
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        await message.answer(
            "✅ Сообщение отправлено администратору! Ожидайте ответа.",
            reply_markup=main_menu(is_admin(user.id)),
        )
    except Exception:
        await message.answer(
            "❌ Не удалось отправить сообщение. Попробуйте позже.",
            reply_markup=main_menu(is_admin(user.id)),
        )


# Админ отвечает клиенту — Reply на сообщение с "🆔 ID: 123456"
@main_router.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
async def admin_reply_to_client(message: Message, bot: Bot):
    original = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"ID:\s*(\d+)", original)
    if not match:
        return
    client_id = int(match.group(1))
    try:
        await bot.send_message(
            client_id,
            f"💬 <b>Ответ администратора:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("✅ Ответ отправлен клиенту.")
    except Exception:
        await message.answer("❌ Не удалось отправить ответ клиенту.")


# ── БРОНИРОВАНИЕ ─────────────────────────────────────

@main_router.message(F.text == "📅 Забронировать")
async def book_start(message: Message, state: FSMContext):
    u = db.get_user(message.from_user.id)
    if not u or not u["phone"]:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await state.set_state(BookingSG.zone)
    await message.answer("Выберите зону:", reply_markup=zones_keyboard())


# Шаг 1 — зона
@main_router.callback_query(BookingSG.zone, F.data.startswith("zone:"))
async def book_zone(call: CallbackQuery, state: FSMContext):
    zone = call.data.split(":")[1]
    await state.update_data(zone=zone)
    await state.set_state(BookingSG.date)
    await call.message.edit_text(
        f"Зона: <b>{zone_label(zone)}</b>\n\nВыберите дату:",
        reply_markup=dates_keyboard(), parse_mode="HTML",
    )
    await call.answer()


# Шаг 2 — дата
@main_router.callback_query(BookingSG.date, F.data.startswith("date:"))
async def book_date(call: CallbackQuery, state: FSMContext):
    date_str = call.data.split(":")[1]
    await state.update_data(date=date_str)
    await state.set_state(BookingSG.time_from)
    d = datetime.strptime(date_str, "%Y-%m-%d")
    await call.message.edit_text(
        f"Дата: <b>{d.strftime('%d.%m.%Y')}</b>\n\n"
        f"Введите время начала в формате <b>ЧЧ:ММ</b> (например, 14:30):\n\n"
        f"⚠️ Бронь держится <b>15 минут</b> с указанного времени, "
        f"после чего автоматически снимается.",
        parse_mode="HTML",
    )
    await call.answer()


# Шаг 3 — время начала (текстовый ввод) → сразу к выбору места (бронь на 15 минут)
@main_router.message(BookingSG.time_from)
async def book_time_from(message: Message, state: FSMContext):
    t = message.text.strip()
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t):
        await message.answer(
            "❌ Неверный формат. Введите время как <b>ЧЧ:ММ</b>, например 14:30.",
            parse_mode="HTML",
        )
        return

    time_from = t
    data = await state.get_data()

    # Бронь фиксированная — 15 минут от времени начала
    h, m = map(int, time_from.split(":"))
    total = h * 60 + m + 15
    time_to = f"{(total // 60) % 24:02d}:{total % 60:02d}"

    await state.update_data(time_from=time_from, time_to=time_to)
    await state.set_state(BookingSG.seat)

    booked = db.get_booked_seats(data["zone"], data["date"], time_from, time_to)
    await message.answer(
        f"🕐 <b>{time_from}</b>\n⚠️ Бронь держится <b>15 минут</b>, затем снимается автоматически.\n\n"
        f"🟢 свободно  🔴 занято\n\nВыберите место:",
        reply_markup=seats_keyboard(data["zone"], booked), parse_mode="HTML",
    )


# Шаг 5 — место
@main_router.callback_query(F.data == "seat_busy")
async def seat_busy(call: CallbackQuery):
    await call.answer("Это место уже занято!", show_alert=True)


@main_router.callback_query(BookingSG.seat, F.data.startswith("seat:"))
async def book_seat(call: CallbackQuery, state: FSMContext):
    seat = int(call.data.split(":")[1])
    await state.update_data(seat=seat)
    await state.set_state(BookingSG.comment)
    await call.message.edit_text(
        f"Место <b>#{seat}</b> выбрано!\n\nДобавьте комментарий или пропустите:",
        reply_markup=skip_comment_kb(), parse_mode="HTML",
    )
    await call.answer()


# Шаг 6 — комментарий
@main_router.callback_query(BookingSG.comment, F.data == "skip_comment")
async def skip_comment(call: CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    await show_confirm(call.message, state, edit=True)
    await call.answer()


@main_router.message(BookingSG.comment)
async def book_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await show_confirm(message, state, edit=False)


async def show_confirm(msg, state: FSMContext, edit: bool):
    data = await state.get_data()
    d = datetime.strptime(data["date"], "%Y-%m-%d")
    text = (
        f"📋 <b>Проверьте бронь:</b>\n\n"
        f"Зона: {zone_label(data['zone'])}\n"
        f"Место: #{data['seat']}\n"
        f"Дата: {d.strftime('%d.%m.%Y')}\n"
        f"Время: {data['time_from']} (бронь держится 15 минут)\n"
        + (f"Комментарий: {data['comment']}\n" if data.get("comment") else "")
        + "\nПодтвердить бронирование?"
    )
    await state.set_state(BookingSG.confirm)
    if edit:
        await msg.edit_text(text, reply_markup=confirm_booking_kb(), parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=confirm_booking_kb(), parse_mode="HTML")


# Шаг 7 — подтверждение
@main_router.callback_query(BookingSG.confirm, F.data == "do_confirm")
async def do_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    booked = db.get_booked_seats(data["zone"], data["date"], data["time_from"], data["time_to"])
    if data["seat"] in booked:
        await state.clear()
        await call.message.edit_text("❌ Место только что заняли. Попробуйте другое.")
        return

    bid = db.create_booking(
        user_id=call.from_user.id,
        zone=data["zone"],
        seat=data["seat"],
        date=data["date"],
        time_from=data["time_from"],
        time_to=data["time_to"],
        comment=data.get("comment", ""),
    )
    await state.clear()

    d = datetime.strptime(data["date"], "%Y-%m-%d")
    await call.message.edit_text(
        f"✅ Бронь <b>#{bid}</b> принята!\n"
        f"📅 {d.strftime('%d.%m.%Y')}  🕐 {data['time_from']} (держится 15 мин)\n\n"
        "Ожидайте подтверждения администратора.",
        parse_mode="HTML",
    )
    await call.answer("Бронь создана!")

    u = db.get_user(call.from_user.id)
    text = (
        f"🔔 <b>Новая бронь #{bid}</b>\n\n"
        f"👤 {call.from_user.full_name} (@{call.from_user.username or '—'})\n"
        f"📞 {u['phone'] if u else '—'}\n\n"
        f"Зона: {zone_label(data['zone'])}, место {data['seat']}\n"
        f"📅 {d.strftime('%d.%m.%Y')}  🕐 {data['time_from']} (держится 15 мин)"
        + (f"\n💬 {data['comment']}" if data.get("comment") else "")
    )
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML", reply_markup=confirm_kb(bid))
    except Exception:
        pass


@main_router.callback_query(F.data == "cancel_booking")
async def cancel_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Бронирование отменено.")
    await call.answer()


# ── АДМИН ─────────────────────────────────────────────

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
        text += "<b>Сегодня:</b>\n"
        for b in today:
            text += (
                f"• #{b['id']} {b['time_from']} | "
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
            f"📅 {b['date']}  🕐 {b['time_from']} (держится 15 мин)"
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
    with sqlite3.connect("club.db") as conn:
        conn.row_factory = sqlite3.Row
        b = conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
    if b:
        try:
            await bot.send_message(
                b["user_id"],
                f"✅ Ваша бронь #{bid} подтверждена!\n"
                f"📅 {b['date']}  🕐 {b['time_from']} (держится 15 мин)\n"
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
    with sqlite3.connect("club.db") as conn:
        conn.row_factory = sqlite3.Row
        b = conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (bid,))
    await call.message.edit_text(f"❌ Бронь #{bid} отклонена.")
    if b:
        try:
            await bot.send_message(
                b["user_id"],
                f"❌ Ваша бронь #{bid} была отклонена.\n"
                "Свяжитесь с клубом для уточнения деталей.",
            )
        except Exception:
            pass
    await call.answer("Отклонено.")
    import json
import logging
from aiogram import types
from aiogram.filters import Command
from config import ADMIN_CHAT_ID

# ... ваш существующий код и main_router ...

@main_router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Бот работает! Данные из приложения будут пересылаться админу.")

@main_router.message(lambda message: message.web_app_data is not None)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        if action == "booking":
            booking = data.get("booking", {})
            user = data.get("user", {})
            text = (
                f"🆕 <b>Новая бронь!</b>\n"
                f"👤 {user.get('firstName', 'Неизвестно')} {user.get('lastName', '')} "
                f"(@{user.get('username', 'нет')})\n"
                f"🎯 Зона: {booking.get('zoneLabel', '—')}\n"
                f"💺 Место: №{booking.get('seat', '—')}\n"
                f"📅 Дата: {booking.get('dateStr', '—')}\n"
                f"🕐 Время: {booking.get('time', '—')}\n"
                f"📝 Комментарий: {booking.get('comment', '—')}"
            )
            await message.bot.send_message(ADMIN_CHAT_ID, text, parse_mode="HTML")

        elif action == "contact":
            user = data.get("user", {})
            text = (
                f"📩 <b>Новое сообщение от пользователя</b>\n"
                f"👤 {user.get('firstName', 'Неизвестно')} {user.get('lastName', '')} "
                f"(@{user.get('username', 'нет')})\n"
                f"💬 {data.get('message', '')}"
            )
            await message.bot.send_message(ADMIN_CHAT_ID, text, parse_mode="HTML")

        else:
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                f"📨 Получены данные:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            )

        await message.answer("✅ Данные получены!")

    except Exception as e:
        logging.error(f"Ошибка обработки web_app_data: {e}")
        await message.answer("❌ Произошла ошибка при обработке.")
