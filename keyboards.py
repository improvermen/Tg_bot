from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="📦 Мои заказы")],
            [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True
    )


def categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(
            text=c["name"],
            callback_data=f"cat_{c['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def products_keyboard(products: list[dict], category_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(
            text=p["name"],
            callback_data=f"prod_{p['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cat_back")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_detail_keyboard(variants: list[dict], product_id: int, category_id: int) -> InlineKeyboardMarkup:
    """Кнопки для выбора варианта (5/10/20 семян) — ведём в корзину."""
    buttons = []
    for v in variants:
        stock = "✓" if v["in_stock"] else "✗"
        buttons.append([InlineKeyboardButton(
            text=f"{v['seeds_count']} семечек — {v['price']}₽ {stock}",
            callback_data=f"add_{v['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к товарам", callback_data=f"cat_{category_id}")])
    buttons.append([InlineKeyboardButton(text="🛒 В корзину", callback_data="cart")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_keyboard(cart_items: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for item in cart_items:
        buttons.append([
            InlineKeyboardButton(text=f"➖", callback_data=f"cart_minus_{item['cart_id']}"),
            InlineKeyboardButton(text=f"{item['product_name']} {item['seeds_count']}шт × {item['quantity']}", callback_data="noop"),
            InlineKeyboardButton(text=f"➕", callback_data=f"cart_plus_{item['cart_id']}"),
            InlineKeyboardButton(text=f"🗑", callback_data=f"cart_del_{item['cart_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cart_clear")])
    buttons.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🛍 Продолжить покупки", callback_data="catalog")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 В каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")],
    ])


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main")],
    ])


def delivery_methods_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📮 Почта России", callback_data="delivery_pochta")],
        [InlineKeyboardButton(text="📦 СДЭК по России (+600₽)", callback_data="delivery_sdek_ru")],
        [InlineKeyboardButton(text="📦 СДЭК по СНГ (+1200₽)", callback_data="delivery_sdek_cis")],
        [InlineKeyboardButton(text="🚗 Курьер", callback_data="delivery_courier")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="order_cancel")],
    ])


def confirm_order_keyboard(order_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="order_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="order_cancel")],
    ])


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📦 Товары и цены", callback_data="admin_products")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🚪 Выход", callback_data="admin_exit")],
    ])


def admin_order_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ В обработке", callback_data=f"admin_status_{order_id}_processing")],
        [InlineKeyboardButton(text="💰 Оплачен", callback_data=f"admin_status_{order_id}_paid")],
        [InlineKeyboardButton(text="📤 Отправлен", callback_data=f"admin_status_{order_id}_shipped")],
        [InlineKeyboardButton(text="✅ Доставлен", callback_data=f"admin_status_{order_id}_delivered")],
        [InlineKeyboardButton(text="❌ Отменён", callback_data=f"admin_status_{order_id}_cancelled")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_orders")],
    ])


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Счёт для оплаты", callback_data="admin_set_payment")],
        [InlineKeyboardButton(text="📞 Ссылка на менеджера", callback_data="admin_set_manager")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="order_cancel")],
    ])
