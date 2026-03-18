import asyncio
import logging
import os
import re
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

# Ensure local imports (db.py, api.py, etc.) work regardless of working directory
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import api
import db
from keyboards import catalog_inline_kb, main_menu_kb, sizes_inline_kb
from states import OrderFlow


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN env var (see .env.example)")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("pr5.task1.bot")


router = Router()


def _parse_sizes(sizes_csv: str) -> list[int]:
    out: list[int] = []
    for p in (sizes_csv or "").split(","):
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out


def _is_phone_like(text: str) -> bool:
    # Very simple validation for lab work
    t = re.sub(r"[^\d+]", "", text.strip())
    return len(t) >= 8


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    text = (
        f"Привіт, {message.from_user.first_name or 'користувачу'}!\n\n"
        "Тема: <b>Замовлення взуття</b> (Aiogram 3.x)\n\n"
        "Натисніть «🛍️ Каталог», щоб обрати модель і оформити замовлення.\n"
        "Команди: /help, /info"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "<b>Допомога</b>\n\n"
        "• 🛍️ Каталог — вибір моделі і розміру, потім введення телефону.\n"
        "• 🧾 Мої замовлення — історія ваших замовлень.\n"
        "• 💱 Курс USD/UAH — приклад зовнішнього API (НБУ).\n\n"
        "Команди:\n"
        "/start — головне меню\n"
        "/help — ця довідка\n"
        "/info — інформація про користувача"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(Command("info"))
async def cmd_info(message: Message) -> None:
    count = await db.count_orders_for_user(message.from_user.id)
    text = (
        "<b>Info</b>\n\n"
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Username: <code>{message.from_user.username or '-'}</code>\n"
        f"Замовлень: <b>{count}</b>\n"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(F.text == "🛍️ Каталог")
async def menu_catalog(message: Message, state: FSMContext) -> None:
    await state.clear()
    shoes = list(await db.list_shoes())
    if not shoes:
        await message.answer("Каталог порожній.", reply_markup=main_menu_kb())
        return
    await state.set_state(OrderFlow.choosing_model)
    await message.answer("Оберіть модель:", reply_markup=catalog_inline_kb(shoes))


@router.message(F.text == "🧾 Мої замовлення")
async def menu_orders(message: Message) -> None:
    orders = list(await db.list_orders_for_user(message.from_user.id))
    if not orders:
        await message.answer("У вас ще немає замовлень.", reply_markup=main_menu_kb())
        return
    lines = ["<b>Ваші замовлення:</b>"]
    for o in orders[:10]:
        lines.append(
            f"• #{o.id} ({o.created_at}) — {o.shoe_name}, розмір {o.size}, {o.price_uah:.0f} грн, статус: {o.status}"
        )
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(F.text == "💱 Курс USD/UAH")
async def menu_rate(message: Message) -> None:
    rate = await api.fetch_usd_uah_rate_nbu()
    if rate is None:
        await message.answer("Не вдалося отримати курс. Спробуйте пізніше.", reply_markup=main_menu_kb())
        return
    await message.answer(f"Курс НБУ: <b>1 USD = {rate:.2f} UAH</b>", parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(F.text == "ℹ️ Допомога")
async def menu_help(message: Message) -> None:
    await cmd_help(message)


@router.callback_query(F.data == "back:catalog")
async def cb_back_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    shoes = list(await db.list_shoes())
    await state.set_state(OrderFlow.choosing_model)
    await callback.message.edit_text("Оберіть модель:", reply_markup=catalog_inline_kb(shoes))
    await callback.answer()


@router.callback_query(F.data.startswith("shoe:"))
async def cb_choose_shoe(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFlow.choosing_size)
    shoe_id = int(callback.data.split(":")[1])
    shoe = await db.get_shoe(shoe_id)
    if not shoe:
        await callback.answer("Модель не знайдена", show_alert=True)
        return
    sizes = _parse_sizes(shoe.sizes)
    await state.update_data(shoe_id=shoe.id)
    await callback.message.edit_text(
        f"<b>{shoe.name}</b>\nКатегорія: {shoe.category}\nЦіна: {shoe.price_uah:.0f} грн\n\nОберіть розмір:",
        parse_mode=ParseMode.HTML,
        reply_markup=sizes_inline_kb(shoe.id, sizes),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("size:"))
async def cb_choose_size(callback: CallbackQuery, state: FSMContext) -> None:
    _, shoe_id_str, size_str = callback.data.split(":")
    shoe_id = int(shoe_id_str)
    size = int(size_str)
    await state.set_state(OrderFlow.entering_phone)
    await state.update_data(shoe_id=shoe_id, size=size)
    await callback.message.answer("Введіть номер телефону для підтвердження (наприклад, +380...):")
    await callback.answer()


@router.message(OrderFlow.entering_phone)
async def phone_input(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if not _is_phone_like(phone):
        await message.answer("Схоже на некоректний номер. Введіть ще раз:")
        return

    data = await state.get_data()
    shoe_id = int(data["shoe_id"])
    size = int(data["size"])
    shoe = await db.get_shoe(shoe_id)
    if not shoe:
        await message.answer("Не вдалося знайти модель. Спробуйте оформити замовлення заново.", reply_markup=main_menu_kb())
        await state.clear()
        return

    user_id = await db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await db.create_order(user_id=user_id, shoe_id=shoe_id, size=size, phone=phone)
    await state.clear()

    text = (
        "✅ <b>Замовлення створено!</b>\n\n"
        f"Модель: <b>{shoe.name}</b>\n"
        f"Розмір: <b>{size}</b>\n"
        f"Телефон: <b>{phone}</b>\n"
        f"Ціна: <b>{shoe.price_uah:.0f} грн</b>\n\n"
        "Дякуємо! Ми зв’яжемося з вами найближчим часом."
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    # Media handling requirement: respond to photos
    photo = message.photo[-1]
    await message.answer(
        "📷 Фото отримано!\n"
        f"file_id: <code>{photo.file_id}</code>\n"
        "Це приклад обробки медіа у Aiogram.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(),
    )


@router.message(F.text)
async def echo_text(message: Message) -> None:
    # Basic message handling: reply to arbitrary text
    await message.answer(
        "Напишіть /help або скористайтесь меню кнопок.\n"
        "Для замовлення: «🛍️ Каталог».",
        reply_markup=main_menu_kb(),
    )


@router.errors()
async def on_error(event) -> bool:
    # Global exception logging
    logger.exception("Unhandled error: %r", event.exception)
    try:
        if getattr(event, "update", None) and getattr(event.update, "message", None):
            await event.update.message.answer("Сталася помилка. Спробуйте пізніше.")
    except TelegramBadRequest:
        pass
    return True


async def main() -> None:
    await db.init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

