from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from db import Shoe


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Каталог"), KeyboardButton(text="🧾 Мої замовлення")],
            [KeyboardButton(text="💱 Курс USD/UAH"), KeyboardButton(text="ℹ️ Допомога")],
        ],
        resize_keyboard=True,
    )


def catalog_inline_kb(shoes: list[Shoe]) -> InlineKeyboardMarkup:
    buttons = []
    for s in shoes:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{s.name} — {s.price_uah:.0f} грн",
                    callback_data=f"shoe:{s.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sizes_inline_kb(shoe_id: int, sizes: list[int]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for size in sizes:
        row.append(InlineKeyboardButton(text=str(size), callback_data=f"size:{shoe_id}:{size}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до каталогу", callback_data="back:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

