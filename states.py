from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    choosing_model = State()
    choosing_size = State()
    entering_phone = State()

