"""
Загрузчик данных из countries.txt, interesting.txt, year_map.txt
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from config import DATA_FILE, INTERESTING_FILE, YEAR_MAP_FILE, DATA_DIR, DEFAULT_YEAR
from logger import log

# ===================== КЭШИ =====================

_slots_cache: Dict[int, List[dict]] = {}       # год -> список слотов
_year_map_cache: Dict[int, int] = {}           # отображаемый год -> год данных
_interesting_cache: Dict[int, List[str]] = {}  # год -> список названий
_all_keys_cache: Dict[str, dict] = {}          # ключ -> слот (для быстрого поиска)

# ===================== ПАРСИНГ YEAR_MAP =====================

def _load_year_map() -> Dict[int, int]:
    """
    Загрузить маппинг годов из year_map.txt
    Формат: 1937=1936
    """
    result = {}
    if not os.path.exists(YEAR_MAP_FILE):
        log.warning(f"year_map.txt не найден: {YEAR_MAP_FILE}")
        return result

    with open(YEAR_MAP_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                parts = line.split("=", 1)
                try:
                    display = int(parts[0].strip())
                    data = int(parts[1].strip())
                    result[display] = data
                except ValueError:
                    continue
    return result


def get_data_year(display_year: int) -> int:
    """
    Получить год данных для отображаемого года.
    Если нет в маппинге — возвращает сам год если есть данные,
    иначе ближайший меньший.
    """
    global _year_map_cache

    if not _year_map_cache:
        _year_map_cache = _load_year_map()

    # Прямое попадание в маппинг
    if display_year in _year_map_cache:
        return _year_map_cache[display_year]

    # Загружаем доступные годы данных
    available = _get_available_data_years()

    # Если год сам по себе есть в данных
    if display_year in available:
        return display_year

    # Ищем ближайший меньший
    smaller = [y for y in available if y <= display_year]
    if smaller:
        return max(smaller)

    # Ближайший больший
    bigger = [y for y in available if y > display_year]
    if bigger:
        return min(bigger)

    return DEFAULT_YEAR


def _get_available_data_years() -> List[int]:
    """Получить список годов, которые реально есть в countries.txt"""
    if _slots_cache:
        return list(_slots_cache.keys())

    # Быстрое сканирование без полной загрузки
    years = set()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) >= 1:
                    try:
                        years.add(int(parts[0]))
                    except ValueError:
                        continue
    return sorted(years)


# ===================== ПАРСИНГ COUNTRIES.TXT =====================

def _make_key(year: int, slot_type: str, flag: str, name: str) -> str:
    """
    Генерация уникального ключа слота.
    Формат: {year}_{type}_{очищенное_название}
    """
    clean_name = re.sub(r'[^\w\s]', '', name, flags=re.UNICODE)
    clean_name = clean_name.strip().replace(' ', '_').lower()
    return f"{year}_{slot_type}_{clean_name}"


def _load_slots_for_year(year: int) -> List[dict]:
    """
    Загрузить все слоты для конкретного года из countries.txt
    Формат строки: ГОД|ТИП|ФЛАГ|НАЗВАНИЕ|СВЕРХДЕРЖАВА
    """
    if not os.path.exists(DATA_FILE):
        log.error(f"Файл данных не найден: {DATA_FILE}")
        return []

    slots = []
    with open(DATA_FILE, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 4:
                log.warning(f"Строка {line_num}: недостаточно полей: {line}")
                continue

            try:
                line_year = int(parts[0].strip())
            except ValueError:
                log.warning(f"Строка {line_num}: неверный год: {parts[0]}")
                continue

            if line_year != year:
                continue

            slot_type = parts[1].strip().lower()
            flag = parts[2].strip()
            name = parts[3].strip()
            is_superpower_str = parts[4].strip().lower() if len(parts) > 4 else "нет"
            is_superpower = is_superpower_str in ("да", "yes", "true", "1")

            key = _make_key(year, slot_type, flag, name)

            slot = {
                "key": key,
                "type": slot_type,
                "flag": flag,
                "name": name,
                "year": year,
                "superpower": is_superpower,
            }
            slots.append(slot)

    log.info(f"Загружено {len(slots)} слотов для {year} года")
    return slots


def _ensure_loaded(year: int):
    """Убедиться что слоты для года загружены в кэш."""
    if year not in _slots_cache:
        slots = _load_slots_for_year(year)
        _slots_cache[year] = slots
        # Обновляем глобальный кэш ключей
        for slot in slots:
            _all_keys_cache[slot["key"]] = slot


def reload_caches():
    """Сбросить все кэши (вызывается при смене года)."""
    global _slots_cache, _year_map_cache, _interesting_cache, _all_keys_cache
    _slots_cache.clear()
    _year_map_cache.clear()
    _interesting_cache.clear()
    _all_keys_cache.clear()
    log.info("Кэши data_loader сброшены")


# ===================== ПОЛУЧЕНИЕ СЛОТОВ =====================

def get_slots_for_year(year: int) -> List[dict]:
    """Получить все слоты для года."""
    _ensure_loaded(year)
    return _slots_cache.get(year, [])


def get_all_countries(year: int) -> List[dict]:
    """Страны (country) — без сверхдержав."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "country"]


def get_regular_countries(year: int) -> List[dict]:
    """Обычные страны (не сверхдержавы)."""
    return get_all_countries(year)


def get_superpowers(year: int) -> List[dict]:
    """Сверхдержавы."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "superpower"]


def get_pmcs(year: int) -> List[dict]:
    """ЧВК."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "pmc"]


def get_mo(year: int) -> List[dict]:
    """Министерства обороны."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "mo"]


def get_vice(year: int) -> List[dict]:
    """Вице-президенты/лидеры."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "vice"]


def get_terror(year: int) -> List[dict]:
    """Террористические организации."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "terror"]


def get_other(year: int) -> List[dict]:
    """Иные движения."""
    slots = get_slots_for_year(year)
    return [s for s in slots if s["type"] == "other"]


# ===================== ИНТЕРЕСНЫЕ СТРАНЫ =====================

def _load_interesting() -> Dict[int, List[str]]:
    """
    Загрузить интересные страны из interesting.txt
    Формат: ГОД|Страна1|Страна2|...
    """
    result = {}
    if not os.path.exists(INTERESTING_FILE):
        log.warning(f"interesting.txt не найден: {INTERESTING_FILE}")
        return result

    with open(INTERESTING_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            try:
                year = int(parts[0].strip())
                names = [p.strip() for p in parts[1:] if p.strip()]
                result[year] = names
            except ValueError:
                continue

    return result


def get_interesting_countries(year: int) -> List[dict]:
    """
    Получить список интересных стран для года.
    Возвращает список слот-словарей (как у обычных слотов).
    """
    global _interesting_cache

    if not _interesting_cache:
        _interesting_cache = _load_interesting()

    interesting_names = _interesting_cache.get(year, [])
    if not interesting_names:
        log.warning(f"Нет интересных стран для года {year} в interesting.txt")
        # Возвращаем первые 10 стран как fallback
        return get_all_countries(year)[:10]

    all_slots = get_slots_for_year(year)

    result = []
    for name in interesting_names:
        slot = next(
            (s for s in all_slots if s["name"].lower() == name.lower()),
            None
        )
        if slot:
            result.append(slot)
        else:
            log.warning(f"Интересная страна '{name}' не найдена в слотах {year} года")

    return result


# ===================== ПОИСК СЛОТОВ =====================

def find_slot_by_key(key: str) -> Optional[dict]:
    """
    Найти слот по ключу.
    Ищет во всех загруженных годах.
    """
    # Сначала в кэше ключей
    if key in _all_keys_cache:
        return _all_keys_cache[key]

    # Перебираем все доступные годы
    for year in _get_available_data_years():
        _ensure_loaded(year)
        if key in _all_keys_cache:
            return _all_keys_cache[key]

    return None


def find_slot_by_name(name: str, year: int) -> Optional[dict]:
    """
    Найти слот по точному названию в конкретном году.
    """
    _ensure_loaded(year)
    slots = _slots_cache.get(year, [])
    name_lower = name.strip().lower()

    # Точное совпадение
    slot = next((s for s in slots if s["name"].lower() == name_lower), None)
    if slot:
        return slot

    # Частичное совпадение
    slot = next((s for s in slots if name_lower in s["name"].lower()), None)
    return slot


def find_slot_by_name_all_years(name: str) -> Optional[dict]:
    """Найти слот по названию во всех годах."""
    for year in _get_available_data_years():
        slot = find_slot_by_name(name, year)
        if slot:
            return slot
    return None


def dl_find_slot_by_name(name: str, year: int) -> Optional[dict]:
    """Алиас для find_slot_by_name (совместимость с admin.py)."""
    return find_slot_by_name(name, year)