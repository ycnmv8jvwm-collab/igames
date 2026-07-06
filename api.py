from aiohttp import web
import json
import asyncio
import sqlite3
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_ID, ZONES
from database import init_db, upsert_user, get_user, create_booking
from keyboards import confirm_kb

def zone_label(key):
    return ZONES.get(key, key)

async def handle_booking(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    bot = Bot(token=BOT_TOKEN)
    init_db()

    user_id   = data.get("userId")
    full_name = data.get("fullName", "Неизвестно")
    username  = data.get("username", "")
    zone      = data.get("zone", "")
    seat      = int(data.get("seat", 0))
    date      = data.get("dateStr", "")
    time      = data.get("time", "")
    comment   = data.get("comment", "")

    # Вычислить time_to +15 минут
    try:
        h, m = map(int, time.split(":"))
        total = h * 60 + m + 15
        time_to = f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        time_to = time

    upsert_user(user_id, username, full_name)
    u = get_user(user_id)

    bid = create_booking(
        user_id=user_id,
        zone=zone,
        seat=seat,
        date=date,
        time_from=time,
        time_to=time_to,
        comment=comment,
    )

    # Уведомление клиенту
    try:
        await bot.send_message(
            user_id,
            f"✅ Бронь <b>#{bid}</b> принята!\n"
            f"📅 {date}  🕐 {time} (держится 15 мин)\n\n"
            "Ожидайте подтверждения администратора.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Уведомление администратору
    text = (
        f"🔔 <b>Новая бронь #{bid}</b> (мини-приложение)\n\n"
        f"👤 {full_name} (@{username or '—'})\n"
        f"📞 {u['phone'] if u and u['phone'] else '—'}\n\n"
        f"Зона: {zone_label(zone)}, место {seat}\n"
        f"📅 {date}  🕐 {time} (держится 15 мин)"
        + (f"\n💬 {comment}" if comment else "")
    )
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML", reply_markup=confirm_kb(bid))
    except Exception:
        pass

    await bot.session.close()
    return web.json_response({"ok": True, "booking_id": bid})


async def handle_contact(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)

    bot = Bot(token=BOT_TOKEN)
    user_id   = data.get("userId")
    full_name = data.get("fullName", "Неизвестно")
    username  = data.get("username", "")
    message   = data.get("message", "")

    text = (
        f"📩 <b>Сообщение через мини-приложение</b>\n\n"
        f"👤 {full_name} (@{username or '—'})\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"💬 {message}"
    )
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception:
        pass

    await bot.session.close()
    return web.json_response({"ok": True})


async def handle_health(request):
    return web.json_response({"ok": True})


def create_app():
    app = web.Application()
    app.router.add_post("/api/booking", handle_booking)
    app.router.add_post("/api/contact", handle_contact)
    app.router.add_get("/health", handle_health)

    # CORS для GitHub Pages
    async def cors_middleware(app, handler):
        async def middleware(request):
            if request.method == "OPTIONS":
                return web.Response(headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                })
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        return middleware

    app.middlewares.append(cors_middleware)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)
