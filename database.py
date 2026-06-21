"""
Менеджер базы данных (JSON-файлы)
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import DB_FILE, USERS_FILE, DEFAULT_YEAR, CONQUERED_FILE


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(path: str, data: dict):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
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


def set_reg_message_id(msg_id: int):
    db = get_db()
    db["reg_message_id"] = msg_id
    save_db(db)


def get_registrations() -> dict:
    return get_db().get("registrations", {})


def get_user_registration(user_id: int) -> Optional[Dict]:
    regs = get_registrations()
    for slot_key, reg in regs.items():
        if reg.get("user_id") == user_id:
            return {"slot_key": slot_key, **reg}
    return None


def register_slot(slot_key: str, user_id: int, username: str, full_name: str, slot_info: dict):
    db = get_db()
    db["registrations"][slot_key] = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "slot_name": slot_info.get("name"),
        "slot_type": slot_info.get("type"),
        "slot_flag": slot_info.get("flag"),
        "slot_year": slot_info.get("year"),
        "registered_at": datetime.now().isoformat()
    }
    save_db(db)


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
    """Пометить слот как завоёванный"""
    data = _load_conquered()
    data[slot_key] = {
        "slot_name": slot_name,
        "slot_flag": slot_flag,
        "reason": reason,
        "conquered_at": datetime.now().isoformat()
    }
    _save_conquered(data)


def unconquer_slot(slot_key: str) -> bool:
    """Снять метку завоёванного"""
    data = _load_conquered()
    if slot_key in data:
        del data[slot_key]
        _save_conquered(data)
        return True
    return False


def is_slot_conquered(slot_key: str) -> bool:
    """Проверить завоёван ли слот"""
    return slot_key in _load_conquered()


def get_conquered_slots() -> dict:
    """Получить все завоёванные слоты"""
    return _load_conquered()


def find_conquered_by_name(name: str) -> Optional[tuple]:
    """Найти завоёванный слот по названию"""
    data = _load_conquered()
    name_lower = name.strip().lower()
    for slot_key, info in data.items():
        if info.get("slot_name", "").lower() == name_lower:
            return (slot_key, info)
    return None


# ===================== БАЗА ПОЛЬЗОВАТЕЛЕЙ =====================

def get_users_db() -> dict:
    return _load(USERS_FILE)


def save_users_db(db: dict):
    _save(USERS_FILE, db)


def register_user_start(user_id: int, username: str, full_name: str):
    db = get_users_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "relocations": 0,
        }
    else:
        db[uid]["username"] = username
        db[uid]["full_name"] = full_name
        db[uid]["last_seen"] = datetime.now().isoformat()
    save_users_db(db)


def get_user_data(user_id: int) -> Optional[dict]:
    db = get_users_db()
    return db.get(str(user_id))


def get_user_relocations(user_id: int) -> int:
    data = get_user_data(user_id)
    return data.get("relocations", 0) if data else 0


def increment_relocations(user_id: int):
    db = get_users_db()
    uid = str(user_id)
    if uid in db:
        db[uid]["relocations"] = db[uid].get("relocations", 0) + 1
        save_users_db(db)


def get_all_users() -> List[dict]:
    db = get_users_db()
    return list(db.values())


def get_user_by_username(username: str) -> Optional[dict]:
    db = get_users_db()
    uname = username.lstrip("@").lower()
    for uid, data in db.items():
        if data.get("username", "").lower() == uname:
            return data
    return None