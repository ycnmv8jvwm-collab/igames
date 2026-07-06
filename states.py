from aiogram.fsm.state import State, StatesGroup


class RegisterSG(StatesGroup):
    phone = State()


class AdminMessageSG(StatesGroup):
    text = State()


class BookingSG(StatesGroup):
    zone      = State()
    date      = State()
    time_from = State()
    seat      = State()
    comment   = State()
    confirm   = State()
