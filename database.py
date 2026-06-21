"""
Менеджер базы данных (JSON-файлы)
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, List
from config import DB_FILE, USERS_FILE, DEFAULT_YEAR, CONQUERED_FILE, WIPE_FILE


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(path: str, data: dict):
    os.makedirs(
        os.path.dirname(path) if os.path.dirname(path) else ".",
        exist_ok=True
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===================== БАЗА РЕГИСТРАЦИЙ =====================

def get_db() -> dict:
    db = _load(DB_FILE)
    if "year" not in db:
        db["year"] = DEFAULT_YEAR
    if "registrations" not in db:
        db["registrations"] = {}
    if "reg_message_id" not in db:
        db["reg_message_id"] = None
    if "reg_open" not in db:
        db["reg_open"] = True
    return db


def save_db(db: dict):
    _save(DB_FILE, db)


def get_current_year() -> int:
    return get_db().get("year", DEFAULT_YEAR)


def set_year(year: int):
    db = get_db()
    db["year"] = year
    save_db(db)


def get_reg_message_id() -> Optional[int]:
    return get_db().get("reg_message_id")


def set_reg_message_id(msg_id: Optional[int]):
    db = get_db()
    db["reg_message_id"] = msg_id
    save_db(db)


def is_registration_open() -> bool:
    """Проверить открыта ли регистрация."""
    return get_db().get("reg_open", True)


def set_registration_open(state: bool):
    """Открыть или закрыть регистрацию."""
    db = get_db()
    db["reg_open"] = state
    save_db(db)


def get_registrations() -> dict:
    return get_db().get("registrations", {})


def get_user_registration(user_id: int) -> Optional[Dict]:
    regs = get_registrations()
    for slot_key, reg in regs.items():
        if reg.get("user_id") == user_id:
            return {"slot_key": slot_key, **reg}
    return None


def register_slot(
    slot_key: str,
    user_id: int,
    username: str,
    full_name: str,
    slot_info: dict
):
    db = get_db()

    if not username or not full_name:
        users_db = _load(USERS_FILE)
        user_data = users_db.get(str(user_id), {})
        if not username:
            username = user_data.get("username", "")
        if not full_name:
            full_name = user_data.get("full_name", str(user_id))

    db["registrations"][slot_key] = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "slot_name": slot_info.get("name", "?"),
        "slot_type": slot_info.get("type", "other"),
        "slot_flag": slot_info.get("flag", "🏳️"),
        "slot_year": slot_info.get("year"),
        "registered_at": datetime.now().isoformat()
    }
    save_db(db)
    _update_user_in_db(user_id, username, full_name)


def _update_user_in_db(user_id: int, username: str, full_name: str):
    if not username and not full_name:
        return
    users_db = _load(USERS_FILE)
    uid = str(user_id)
    now = datetime.now().isoformat()
    if uid in users_db:
        if username:
            users_db[uid]["username"] = username
        if full_name:
            users_db[uid]["full_name"] = full_name
        users_db[uid]["last_seen"] = now
    else:
        users_db[uid] = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name or str(user_id),
            "first_seen": now,
            "last_seen": now,
            "relocations": 0,
        }
    _save(USERS_FILE, users_db)


def unregister_slot(slot_key: str) -> Optional[dict]:
    db = get_db()
    removed = db["registrations"].pop(slot_key, None)
    save_db(db)
    return removed


def unregister_user(user_id: int) -> Optional[dict]:
    regs = get_registrations()
    for slot_key, reg in regs.items():
        if reg.get("user_id") == user_id:
            return unregister_slot(slot_key)
    return None


def wipe_all_registrations() -> int:
    """
    Сбросить ВСЕ регистрации.
    Возвращает количество удалённых записей.
    """
    db = get_db()
    count = len(db["registrations"])
    db["registrations"] = {}
    db["reg_message_id"] = None
    save_db(db)

    # Также сбрасываем счётчик пересадок у всех
    users_db = _load(USERS_FILE)
    for uid in users_db:
        users_db[uid]["relocations"] = 0
    _save(USERS_FILE, users_db)

    return count


def find_slot_by_name(name: str) -> Optional[tuple]:
    regs = get_registrations()
    name_lower = name.strip().lower()
    for slot_key, reg in regs.items():
        if reg.get("slot_name", "").lower() == name_lower:
            return (slot_key, reg)
    return None


def is_slot_occupied(slot_key: str) -> bool:
    return slot_key in get_registrations()


# ===================== ЗАВОЁВАННЫЕ СЛОТЫ =====================

def _load_conquered() -> dict:
    return _load(CONQUERED_FILE)


def _save_conquered(data: dict):
    _save(CONQUERED_FILE, data)


def conquer_slot(slot_key: str, slot_name: str, slot_flag: str, reason: str = ""):
    data = _load_conquered()
    data[slot_key] = {
        "slot_name": slot_name,
        "slot_flag": slot_flag,
        "reason": reason,
        "conquered_at": datetime.now().isoformat()
    }
    _save_conquered(data)


def unconquer_slot(slot_key: str) -> bool:
    data = _load_conquered()
    if slot_key in data:
        del data[slot_key]
        _save_conquered(data)
        return True
    return False


def is_slot_conquered(slot_key: str) -> bool:
    return slot_key in _load_conquered()


def get_conquered_slots() -> dict:
    return _load_conquered()


def find_conquered_by_name(name: str) -> Optional[tuple]:
    data = _load_conquered()
    name_lower = name.strip().lower()
    for slot_key, info in data.items():
        if info.get("slot_name", "").lower() == name_lower:
            return (slot_key, info)
        if name_lower in info.get("slot_name", "").lower():
            return (slot_key, info)
    return None


# ===================== ВАЙП ПЛАНИРОВЩИК =====================

def get_wipe_data() -> dict:
    return _load(WIPE_FILE)


def save_wipe_data(data: dict):
    _save(WIPE_FILE, data)


def set_planned_wipe(dt_str: str, year: int):
    """Сохранить запланированный вайп."""
    data = {
        "planned_at": dt_str,
        "year": year,
        "notified": False,
        "executed": False,
    }
    save_wipe_data(data)


def get_planned_wipe() -> Optional[dict]:
    data = get_wipe_data()
    if not data or data.get("executed"):
        return None
    return data


def mark_wipe_executed():
    data = get_wipe_data()
    if data:
        data["executed"] = True
        save_wipe_data(data)


def mark_wipe_notified():
    data = get_wipe_data()
    if data:
        data["notified"] = True
        save_wipe_data(data)


def cancel_wipe():
    save_wipe_data({})


# ===================== БАЗА ПОЛЬЗОВАТЕЛЕЙ =====================

def get_users_db() -> dict:
    return _load(USERS_FILE)


def save_users_db(db: dict):
    _save(USERS_FILE, db)


def register_user_start(user_id: int, username: str, full_name: str):
    db = get_users_db()
    uid = str(user_id)
    now = datetime.now().isoformat()

    if uid not in db:
        db[uid] = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "first_seen": now,
            "last_seen": now,
            "relocations": 0,
        }
    else:
        db[uid]["username"] = username
        db[uid]["full_name"] = full_name
        db[uid]["last_seen"] = now

    _save(USERS_FILE, db)
    _sync_registration_username(user_id, username, full_name)


def _sync_registration_username(user_id: int, username: str, full_name: str):
    db = get_db()
    changed = False
    for slot_key, reg in db["registrations"].items():
        if reg.get("user_id") == user_id:
            if username and reg.get("username") != username:
                reg["username"] = username
                changed = True
            if full_name and reg.get("full_name") != full_name:
                reg["full_name"] = full_name
                changed = True
            break
    if changed:
        save_db(db)


def get_user_data(user_id: int) -> Optional[dict]:
    return get_users_db().get(str(user_id))


def get_user_relocations(user_id: int) -> int:
    data = get_user_data(user_id)
    return data.get("relocations", 0) if data else 0


def increment_relocations(user_id: int):
    db = get_users_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "user_id": user_id,
            "username": "",
            "full_name": str(user_id),
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "relocations": 1,
        }
    else:
        db[uid]["relocations"] = db[uid].get("relocations", 0) + 1
    _save(USERS_FILE, db)


def get_all_users() -> List[dict]:
    return list(get_users_db().values())


def get_user_by_username(username: str) -> Optional[dict]:
    db = get_users_db()
    uname = username.lstrip("@").lower()
    for uid, data in db.items():
        if data.get("username", "").lower() == uname:
            return data
    return None
