"""
Telegram-бот «JamaicanFlowerSeeds» — интернет-магазин семян.
"""
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    ADMIN_GROUP_ID,
    ADMIN_PASSWORD,
    PAYMENT_BANK_NAME,
    PAYMENT_ACCOUNT,
)
from database import Database
from keyboards import (
    main_menu_keyboard,
    categories_keyboard,
    products_keyboard,
    product_detail_keyboard,
    cart_keyboard,
    cart_empty_keyboard,
    back_to_main_keyboard,
    delivery_methods_keyboard,
    confirm_order_keyboard,
    admin_main_keyboard,
    admin_order_actions_keyboard,
    admin_settings_keyboard,
    cancel_keyboard,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()

# ─── FSM States ───────────────────────────────────────────────────────────────

class OrderForm(StatesGroup):
    fio = State()
    phone = State()
    city = State()
    delivery = State()
    address = State()
    comment = State()
    confirm = State()


class AdminAuth(StatesGroup):
    password = State()


# ─── Helpers ──────────────────────────────────────────────────────────────────

STATUS_NAMES = {
    "new": "🆕 Новый",
    "processing": "⏳ В обработке",
    "paid": "💰 Оплачен",
    "shipped": "📤 Отправлен",
    "delivered": "✅ Доставлен",
    "cancelled": "❌ Отменён",
}

DELIVERY_NAMES = {
    "pochta": "Почта России",
    "sdek_ru": "СДЭК по России",
    "sdek_cis": "СДЭК по СНГ",
    "courier": "Курьер по Санкт-Петербургу",
}

DELIVERY_COSTS = {
    "pochta": 500,
    "sdek_ru": 600,
    "sdek_cis": 1200,
    "courier": 500,
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── Start & Main Menu ────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    welcome = (
        f"🌿 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Добро пожаловать в <b>JamaicanFlowerSeeds</b> — интернет-магазин премиальных семян.\n\n"
        "Выберите действие в меню ниже 👇"
    )
    # Можно отправить логотип, если есть — пока текст
    await message.answer(
        welcome,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


async def send_main_menu(message: types.Message, text: str = "Главное меню:"):
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


# ─── Catalog ──────────────────────────────────────────────────────────────────

@dp.message(F.text == "🛍 Каталог")
@dp.callback_query(F.data == "catalog")
async def show_catalog(event: types.Message | types.CallbackQuery):
    if isinstance(event, types.CallbackQuery):
        message = event.message
        await event.answer()
    else:
        message = event

    categories = await db.get_categories()
    await message.answer(
        "🛍 <b>Каталог</b>\n\nВыберите категорию:",
        parse_mode="HTML",
        reply_markup=categories_keyboard(categories)
    )


@dp.callback_query(F.data.startswith("cat_"))
async def category_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    data = callback.data
    if data == "cat_back":
        categories = await db.get_categories()
        await callback.message.edit_text(
            "🛍 <b>Каталог</b>\n\nВыберите категорию:",
            parse_mode="HTML",
            reply_markup=categories_keyboard(categories)
        )
        await callback.answer()
        return

    cat_id = int(data.split("_")[1])
    await state.update_data(last_category_id=cat_id)
    products = await db.get_products_by_category(cat_id)
    cat_name = next((c["name"] for c in await db.get_categories() if c["id"] == cat_id), "Категория")
    await callback.message.edit_text(
        f"🛍 <b>{cat_name}</b>\n\nВыберите товар:",
        parse_mode="HTML",
        reply_markup=products_keyboard(products, cat_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("prod_"))
async def product_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)
    variants = await db.get_variants(product_id)
    if not product or not variants:
        await callback.answer("Товар не найден", show_alert=True)
        return

    category_id = product.get("category_id", 1)
    desc = (product.get("description") or "")[:200]
    text = (
        f"<b>{product['name']}</b>\n\n"
        f"{desc}\n\n"
        f"Выберите количество семян:"
    )

    photo_ids = product.get("photo_ids")
    if photo_ids:
        try:
            ids = photo_ids.split(",")
            await callback.message.delete()
            await callback.message.answer_photo(
                ids[0].strip(),
                caption=text,
                parse_mode="HTML",
                reply_markup=product_detail_keyboard(variants, product_id, category_id)
            )
        except Exception:
            await callback.message.edit_text(
                text, parse_mode="HTML",
                reply_markup=product_detail_keyboard(variants, product_id, category_id)
            )
    else:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=product_detail_keyboard(variants, product_id, category_id)
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    variant_id = int(callback.data.split("_")[1])
    variant = await db.get_variant(variant_id)
    if not variant:
        await callback.answer("Товар не найден", show_alert=True)
        return
    if not variant["in_stock"]:
        await callback.answer("Товар временно отсутствует", show_alert=True)
        return

    await db.add_to_cart(callback.from_user.id, variant_id)
    await callback.answer(f"✅ {variant['product_name']} ({variant['seeds_count']} сем.) добавлено в корзину")


# ─── Cart ────────────────────────────────────────────────────────────────────

def format_cart_message(cart: list, total: int) -> str:
    lines = ["🛒 <b>Корзина</b>\n"]
    for item in cart:
        lines.append(
            f"• {item['product_name']} ({item['seeds_count']} сем.) × {item['quantity']} = "
            f"{item['price'] * item['quantity']}₽"
        )
    lines.append(f"\n<b>Итого: {total}₽</b>")
    return "\n".join(lines)


@dp.message(F.text == "🛒 Корзина")
@dp.callback_query(F.data == "cart")
async def show_cart(event: types.Message | types.CallbackQuery):
    if isinstance(event, types.CallbackQuery):
        message = event.message
        await event.answer()
    else:
        message = event

    cart = await db.get_cart(message.chat.id)
    if not cart:
        await message.answer(
            "🛒 Корзина пуста.\nДобавьте товары из каталога.",
            reply_markup=cart_empty_keyboard()
        )
        return

    total = sum(item["price"] * item["quantity"] for item in cart)
    await message.answer(
        format_cart_message(cart, total),
        parse_mode="HTML",
        reply_markup=cart_keyboard(cart)
    )


@dp.callback_query(F.data.startswith("cart_"))
async def cart_actions(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id

    if data == "cart_clear":
        await db.clear_cart(user_id)
        await callback.message.edit_text("Корзина очищена.", reply_markup=cart_empty_keyboard())
        await callback.answer("Корзина очищена")
        return

    if data.startswith("cart_plus_"):
        cart_id = int(data.split("_")[2])
        await db.update_cart_quantity(user_id, cart_id, 1)
    elif data.startswith("cart_minus_"):
        cart_id = int(data.split("_")[2])
        await db.update_cart_quantity(user_id, cart_id, -1)
    elif data.startswith("cart_del_"):
        cart_id = int(data.split("_")[2])
        await db.remove_from_cart(user_id, cart_id)
    else:
        await callback.answer()
        return

    cart = await db.get_cart(user_id)
    if not cart:
        await callback.message.edit_text("Корзина пуста.", reply_markup=cart_empty_keyboard())
        await callback.answer()
        return

    total = sum(item["price"] * item["quantity"] for item in cart)
    await callback.message.edit_text(
        format_cart_message(cart, total),
        parse_mode="HTML",
        reply_markup=cart_keyboard(cart)
    )
    await callback.answer()


# ─── Order Flow ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    await state.set_state(OrderForm.fio)
    await state.update_data(cart_total=sum(i["price"] * i["quantity"] for i in cart))
    await callback.message.edit_text(
        "📝 <b>Оформление заказа</b>\n\n1️⃣ Введите ваше ФИО:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@dp.message(StateFilter(OrderForm.fio), F.text)
async def order_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text.strip())
    await state.set_state(OrderForm.phone)
    await message.answer("2️⃣ Введите номер телефона (например: +79001234567):", reply_markup=cancel_keyboard())


@dp.message(StateFilter(OrderForm.phone), F.text)
async def order_phone(message: types.Message, state: FSMContext):
    text = re.sub(r"\D", "", message.text)
    if len(text) < 10:
        await message.answer("Введите корректный номер телефона (минимум 10 цифр):")
        return
    await state.update_data(phone=message.text.strip())
    await state.set_state(OrderForm.city)
    await message.answer("3️⃣ Введите город / населённый пункт:", reply_markup=cancel_keyboard())


@dp.message(StateFilter(OrderForm.city), F.text)
async def order_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(OrderForm.delivery)
    await message.answer(
        "4️⃣ Выберите способ доставки:",
        reply_markup=delivery_methods_keyboard()
    )


@dp.callback_query(StateFilter(OrderForm.delivery), F.data.startswith("delivery_"))
async def order_delivery(callback: types.CallbackQuery, state: FSMContext):
    method = callback.data.replace("delivery_", "")
    cost = DELIVERY_COSTS.get(method, 0)
    await state.update_data(delivery=method, delivery_cost=cost)
    await state.set_state(OrderForm.address)
    await callback.message.edit_text(
        "5️⃣ Введите адрес доставки (индекс, улица, дом, квартира):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@dp.message(StateFilter(OrderForm.address), F.text)
async def order_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderForm.comment)
    await message.answer(
        "6️⃣ Напишите комментарий к заказу (или отправьте «—» чтобы пропустить):",
        reply_markup=cancel_keyboard()
    )


@dp.message(StateFilter(OrderForm.comment), F.text)
async def order_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip() if message.text.strip() != "—" else ""
    await state.update_data(comment=comment)
    await state.set_state(OrderForm.confirm)
    data = await state.get_data()
    await show_order_summary(message, state, data)


async def show_order_summary(message: types.Message, state: FSMContext, data: dict):
    cart = await db.get_cart(message.chat.id)
    cart_total = data.get("cart_total", sum(i["price"] * i["quantity"] for i in cart))
    delivery_cost = data.get("delivery_cost", 0)
    grand_total = cart_total + delivery_cost
    delivery = DELIVERY_NAMES.get(data.get("delivery", ""), data.get("delivery", ""))

    summary = (
        "📋 <b>Проверьте заказ:</b>\n\n"
        f"👤 ФИО: {data.get('fio')}\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"📍 Город: {data.get('city')}\n"
        f"📦 Доставка: {delivery}\n"
        f"🏠 Адрес: {data.get('address')}\n"
    )
    if data.get("comment"):
        summary += f"💬 Комментарий: {data['comment']}\n\n"
    else:
        summary += "\n"

    lines = []
    for item in cart:
        lines.append(f"• {item['product_name']} ({item['seeds_count']} сем.) × {item['quantity']} = {item['price'] * item['quantity']}₽")
    summary += "\n".join(lines)
    summary += (
        f"\n\n<b>Товары: {cart_total}₽</b>"
        f"\n<b>Доставка: {delivery_cost}₽</b>"
        f"\n<b>Итого к оплате: {grand_total}₽</b>\n\nПодтвердить заказ?"
    )
    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=confirm_order_keyboard()
    )


@dp.callback_query(StateFilter(OrderForm.confirm), F.data == "order_confirm")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user

    order_id = await db.create_order(
        user_id=user.id,
        user_name=data["fio"],
        user_phone=data["phone"],
        user_city=data["city"],
        delivery_method=DELIVERY_NAMES.get(data.get("delivery", ""), data.get("delivery")),
        delivery_address=data["address"],
        comment=data.get("comment", ""),
        total=data["cart_total"] + data.get("delivery_cost", 0),
    )

    # Текст с реквизитами для оплаты
    payment_text = (
        f"🏦 Банк: {PAYMENT_BANK_NAME}\n"
        f"💳 Счёт: {PAYMENT_ACCOUNT}\n\n"
        "После оплаты сохраните чек. Администратор проверит оплату и сменит статус заказа на «Оплачен»."
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Заказ №{order_id} принят!</b>\n\n"
        "Мы свяжемся с вами в течение 1 часа.\n\n"
        "<b>Реквизиты для оплаты:</b>\n"
        f"{payment_text}",
        parse_mode="HTML"
    )
    await send_main_menu(callback.message, "Главное меню:")

    # Уведомление администратору
    order = await db.get_order(order_id)
    await send_order_to_admin(order)
    await callback.answer()


@dp.callback_query(F.data == "order_cancel")
@dp.callback_query(StateFilter(OrderForm))
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Заказ отменён.")
    await send_main_menu(callback.message, "Главное меню:")
    await callback.answer()


# ─── Send order to admin ──────────────────────────────────────────────────────

async def send_order_to_admin(order: dict):
    items_text = "\n".join(
        f"  • {i['product_name']} ({i['seeds_count']} сем.) × {i['quantity']} = {i['price'] * i['quantity']}₽"
        for i in order.get("items", [])
    )
    text = (
        f"📬 <b>Новый заказ #{order['id']}</b>\n\n"
        f"👤 ФИО: {order['user_name']}\n"
        f"📞 Телефон: {order['user_phone']}\n"
        f"📍 Город: {order['user_city']}\n"
        f"📦 Доставка: {order['delivery_method']}\n"
        f"🏠 Адрес: {order['delivery_address']}\n"
        f"💬 Комментарий: {order.get('comment') or '—'}\n\n"
        f"<b>Товары:</b>\n{items_text}\n\n"
        f"<b>Итого: {order['total']}₽</b>\n\n"
        f"User ID: <code>{order['user_id']}</code>"
    )
    kb = admin_order_actions_keyboard(order["id"])

    if ADMIN_GROUP_ID:
        try:
            await bot.send_message(ADMIN_GROUP_ID, text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.error(f"Ошибка отправки в группу: {e}")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")


# ─── My Orders ────────────────────────────────────────────────────────────────

@dp.message(F.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    orders = await db.get_user_orders(message.from_user.id, limit=5)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return

    text = "📦 <b>Ваши заказы</b> (последние 5):\n\n"
    for o in orders:
        dt = o["created_at"][:10] if isinstance(o["created_at"], str) else str(o["created_at"])[:10]
        status = STATUS_NAMES.get(o["status"], o["status"])
        text += f"<b>#{o['id']}</b> от {dt} — {o['total']}₽ — {status}\n"
    await message.answer(text, parse_mode="HTML")


# ─── Contacts & Help ──────────────────────────────────────────────────────────

@dp.message(F.text == "📞 Контакты")
async def contacts(message: types.Message):
    manager_link = await db.get_setting("manager_link")
    text = (
        "📞 <b>Контакты</b>\n\n"
        "JamaicanFlowerSeeds — интернет-магазин премиальных семян.\n\n"
    )
    if manager_link:
        text += f"Написать менеджеру: {manager_link}"
    else:
        text += "По вопросам заказов — оставьте заявку через бота, мы свяжемся с вами."
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "❓ Помощь")
async def help_handler(message: types.Message):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "• <b>Каталог</b> — просмотр товаров и добавление в корзину\n"
        "• <b>Корзина</b> — управление товарами и оформление заказа\n"
        "• <b>Мои заказы</b> — статус ваших заказов\n"
        "• <b>Контакты</b> — связь с нами\n\n"
        "При возникновении проблем — напишите в контакты."
    )
    await message.answer(text, parse_mode="HTML")


# ─── To main menu ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data == "to_main")
async def to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# ─── Admin Panel ──────────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    if is_admin(message.from_user.id) or await db.is_admin_session(message.from_user.id):
        await state.clear()
        await message.answer("⚙️ Админ-панель:", reply_markup=admin_main_keyboard())
        return
    await state.set_state(AdminAuth.password)
    await message.answer("Введите пароль администратора:", reply_markup=cancel_keyboard())


@dp.message(StateFilter(AdminAuth.password), F.text)
async def admin_password(message: types.Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await db.set_admin_session(message.from_user.id)
        await state.clear()
        await message.answer("✅ Вход выполнен. Админ-панель:", reply_markup=admin_main_keyboard())
    else:
        await message.answer("Неверный пароль. Попробуйте снова или /cancel")


@dp.callback_query(F.data == "admin_orders")
async def admin_orders_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id) and not await db.is_admin_session(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    orders = await db.get_all_orders(limit=30)
    if not orders:
        await callback.message.edit_text("Заказов пока нет.", reply_markup=admin_main_keyboard())
        await callback.answer()
        return

    text = "📋 <b>Заказы</b> (последние 30):\n\n"
    for o in orders[:15]:
        dt = str(o["created_at"])[:16] if o.get("created_at") else ""
        status = STATUS_NAMES.get(o.get("status", ""), o.get("status", ""))
        text += f"<b>#{o['id']}</b> | {o.get('user_name', '')} | {o.get('total', 0)}₽ | {status} | {dt}\n"
    text += "\nВыберите заказ для смены статуса в меню ниже или нажмите «Назад»."
    # Показываем пагинацию по callback для выбора заказа — упрощённо, кнопки со статусами для последних
    kb = InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(
            text=f"#{o['id']} {o.get('user_name','')} — {o.get('total',0)}₽",
            callback_data=f"admin_order_{o['id']}"
        )] for o in orders[:10]],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_order_"))
async def admin_order_detail(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id) and not await db.is_admin_session(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    items = "\n".join(
        f"  • {i['product_name']} ({i['seeds_count']} сем.) × {i['quantity']} = {i['price']*i['quantity']}₽"
        for i in order.get("items", [])
    )
    status = STATUS_NAMES.get(order.get("status", ""), order.get("status", ""))
    text = (
        f"<b>Заказ #{order['id']}</b> — {status}\n\n"
        f"👤 {order['user_name']}\n📞 {order['user_phone']}\n"
        f"📍 {order['user_city']}\n📦 {order['delivery_method']}\n"
        f"🏠 {order['delivery_address']}\n\n{items}\n\n<b>Итого: {order['total']}₽</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_order_actions_keyboard(order_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_status_"))
async def admin_set_status(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id) and not await db.is_admin_session(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = callback.data.split("_")
    order_id = int(parts[2])
    status = parts[3]
    await db.update_order_status(order_id, status)
    order = await db.get_order(order_id)

    # Уведомить клиента об изменении статуса
    status_text = STATUS_NAMES.get(status, status)
    try:
        await bot.send_message(
            order["user_id"],
            f"📦 Статус заказа #{order_id} изменён: <b>{status_text}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления клиента: {e}")

    await callback.answer(f"Статус: {status_text}")
    # Вернуться к списку заказов
    orders = await db.get_all_orders(limit=10)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(
            text=f"#{o['id']} {o.get('user_name','')}",
            callback_data=f"admin_order_{o['id']}"
        )] for o in orders],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    await callback.message.edit_text("Статус обновлён. Выберите заказ:", parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "admin_products")
async def admin_products(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id) and not await db.is_admin_session(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    products = await db.get_all_products_with_variants()
    text = "📦 <b>Товары и цены</b>\n\n"
    for p in products[:15]:
        text += f"<b>{p['name']}</b> ({p['category_name']})\n"
        for v in p.get("variants", []):
            text += f"  {v['seeds_count']} сем. — {v['price']}₽ (в наличии: {'да' if v['in_stock'] else 'нет'})\n"
        text += "\n"
    text += "Изменение товаров — через команду /admin в будущих обновлениях. Сейчас настройте счёт в «Настройки»."
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_settings")
async def admin_settings(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id) and not await db.is_admin_session(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    bank = await db.get_setting("payment_bank") or "—"
    account = await db.get_setting("payment_account") or "—"
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Счёт: {account}\n\n"
        "Изменение — вручную в .env (PAYMENT_BANK_NAME, PAYMENT_ACCOUNT) или через команды бота в следующих версиях."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_settings_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "admin_back")
@dp.callback_query(F.data == "admin_exit")
async def admin_back(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    await db.init()
    logger.info("Бот JamaicanFlowerSeeds запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
