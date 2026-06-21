import os

# ===== БОТ =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "GenericBot")

# ===== ЧАТЫ =====
GROUP_ID = int(os.getenv("GROUP_ID", "-1000000000000"))
TOPIC_ID = int(os.getenv("TOPIC_ID", "1"))
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1000000000000"))

# ===== ВЛАДЕЛЕЦ =====
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "@username")

STAFF = {
    "Владелец": os.getenv("STAFF_OWNER", "@username"),
    "Совладелец": os.getenv("STAFF_CO", "@username"),
    "Регистратор": f"@{os.getenv('BOT_USERNAME', 'GenericBot')}",
    "Картограф": os.getenv("STAFF_CART", "@username"),
}

# ===== ОГРАНИЧЕНИЯ =====
MAX_RELOCATIONS = int(os.getenv("MAX_RELOCATIONS", "999"))

SUPPORT_BOT = os.getenv("SUPPORT_BOT", "@SupportBot")
PROJECT_CHANNEL = os.getenv("PROJECT_CHANNEL", "@ProjectChannel")

# ===== ГОДЫ =====
DATA_YEARS = [1936, 1939, 1941, 1991, 2001, 2014, 2022, 2025]
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "1939"))

# ===== ФАЙЛЫ =====
DATA_DIR = os.getenv("DATA_DIR", "data")
DATA_FILE = os.path.join(DATA_DIR, "countries.txt")
INTERESTING_FILE = os.path.join(DATA_DIR, "interesting.txt")
YEAR_MAP_FILE = os.path.join(DATA_DIR, "year_map.txt")
CONQUERED_FILE = os.path.join(DATA_DIR, "conquered.json")
DB_FILE = os.path.join(DATA_DIR, "database.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
WIPE_FILE = os.path.join(DATA_DIR, "wipe.json")
