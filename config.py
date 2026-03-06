import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ─── Telegram Bot ─────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─── Admins ───────────────────────────────────────────────────────────────────
# По умолчанию используем ваш основной админ‑ID, а при наличии переменной
# окружения ADMIN_IDS она переопределит значение из кода.
_admin_ids_raw = os.getenv("ADMIN_IDS", "1322410337")
ADMIN_IDS: list[int] = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

# ID группы/чата для получения заказов (числовой), если вы его укажете в .env
_admin_group_raw = os.getenv("ADMIN_GROUP_ID", "").strip()
ADMIN_GROUP_ID: int | None = int(_admin_group_raw) if _admin_group_raw else None

# Ссылка на группу для заказов (используется в интерфейсе, хранится в git)
ADMIN_GROUP_LINK: str = os.getenv(
    "ADMIN_GROUP_LINK",
    "https://t.me/+l07SZNCUrXg1OGFi",
)

# ─── Admin Panel ──────────────────────────────────────────────────────────────
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_PATH: str = str(BASE_DIR / "data" / "shop2.db")

# ─── Payment (для счёта) ──────────────────────────────────────────────────────
# По умолчанию реквизиты берутся из этого файла (он попадает в git),
# а при наличии переменных окружения PAYMENT_BANK_NAME / PAYMENT_ACCOUNT
# они будут переопределять значения из кода.
PAYMENT_BANK_NAME: str = os.getenv(
    "PAYMENT_BANK_NAME",
    "EnergoBank",
)
PAYMENT_ACCOUNT: str = os.getenv(
    "PAYMENT_ACCOUNT",
    "Пополните счет: 2201 2502 0263 3222",
)
