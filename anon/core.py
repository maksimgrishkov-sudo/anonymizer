# -*- coding: utf-8 -*-
"""Обезличивание и обратная подстановка.

Главное свойство — метки СТАБИЛЬНЫ. Если просто заменить всё звёздочками,
пропадут связи между кусками: непонятно, один это ключ в десяти местах или
десять разных. Поэтому одно и то же значение везде получает одну и ту же
метку, в том числе между файлами одной пачки.

Словарь замен — единственное, что раскрывает скрытое. Он остаётся у
владельца и никуда не отправляется.
"""
import json
import re
from pathlib import Path

from .patterns import GROUPED, KEEP, PATTERNS, TITLES

# Файлы, которые нет смысла разбирать: там нет текста, а время уйдёт.
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".7z", ".rar", ".exe", ".dll", ".so", ".db", ".sqlite", ".xlsx", ".docx",
    ".mp3", ".mp4", ".woff", ".woff2", ".ttf",
}


def word_pattern(word):
    """Выражение для своего слова, которое переживёт падежи.

    В списке стоит «Петрова», а в логе встретится «Петровой», «Петрову»,
    «Ромашки» вместо «Ромашка». Поэтому у слова отсекается последняя буква,
    если она похожа на окончание, и разрешается любой русский хвост до трёх
    букв. Найдено на живом логе: фамилия оставалась в файле, а проверка
    перед отправкой молчала.

    Слова короче пяти букв не трогаем: «Иван» без последней буквы начнёт
    цеплять пол-лога.
    """
    stem = word.strip()
    if len(stem) >= 5 and re.search(r"[аеёиоуыэюяьй]$", stem, re.I):
        stem = stem[:-1]
    return re.compile(re.escape(stem) + r"[а-яё]{0,3}", re.I)


class Anonymizer:
    """Прячет значения за метками и возвращает их обратно."""

    def __init__(self, mapping=None, own_words=None):
        # метка → настоящее значение
        self.map = dict(mapping or {})
        # настоящее значение → метка; нужно, чтобы замены не разъезжались
        self.back = {v: k for k, v in self.map.items()}
        self.own_words = [w for w in (own_words or []) if w]
        self.counters = {}
        # сколько раз сработало каждое правило — для отчёта
        self.hits = {}
        self._restore_counters()

    def _restore_counters(self):
        """Продолжаем нумерацию словаря, а не начинаем заново.

        Иначе при добавлении второго файла метка KEY_1 досталась бы уже
        другому ключу, и словарь перестал бы разворачиваться обратно.
        """
        for mark in self.map:
            kind, _, num = mark.rpartition("_")
            if kind and num.isdigit():
                self.counters[kind] = max(self.counters.get(kind, 0), int(num))

    # ── скрытие ─────────────────────────────────────────────────────
    def label(self, kind, value):
        if value in self.back:
            return self.back[value]
        self.counters[kind] = self.counters.get(kind, 0) + 1
        mark = "%s_%d" % (kind, self.counters[kind])
        self.map[mark] = value
        self.back[value] = mark
        return mark

    def hide(self, text):
        # Сначала свои слова: название компании и фамилии шаблоном не поймать,
        # а если их пропустить, обезличивание теряет смысл.
        #
        # Русское окончание добавляется к каждому слову: в списке стоит
        # «Петрова», а в логе встретится «Петровой» — и без этого фамилия
        # уедет заказчику открытым текстом. Проверено на живом примере.
        for word in self.own_words:
            text = word_pattern(word).sub(lambda m: self._mark("NAME", m.group(0)), text)

        for kind, rx in PATTERNS:
            def repl(m, kind=kind):
                if kind in GROUPED:
                    # имя поля и кавычку оставляем, прячем только значение
                    return m.group(1) + self._mark(kind, m.group(2))
                val = m.group(0)
                if val in KEEP or val.lower() in KEEP:
                    return val
                return self._mark(kind, val)
            text = rx.sub(repl, text)
        return text

    def _mark(self, kind, value):
        self.hits[kind] = self.hits.get(kind, 0) + 1
        return self.label(kind, value)

    # ── возврат ─────────────────────────────────────────────────────
    def restore(self, text):
        """Длинные метки первыми: иначе KEY_10 пострадает от замены KEY_1."""
        for mark in sorted(self.map, key=len, reverse=True):
            text = text.replace(mark, self.map[mark])
        return text

    def restored_count(self, text):
        return sum(1 for mark in self.map if mark in text)

    # ── отчёт ───────────────────────────────────────────────────────
    def report(self):
        """Что и сколько скрыто — по-русски, для человека."""
        rows = []
        by_kind = {}
        for mark in self.map:
            kind = mark.rsplit("_", 1)[0]
            by_kind[kind] = by_kind.get(kind, 0) + 1
        for kind, uniq in sorted(by_kind.items(), key=lambda x: -x[1]):
            rows.append({
                "kind": kind,
                "title": TITLES.get(kind, kind),
                "unique": uniq,
                "hits": self.hits.get(kind, uniq),
            })
        return rows


# Уже поставленная метка: KEY_1, USER_12. Проверка не должна принимать
# её за секрет — иначе обезличенный файл вечно «грязный», и человек
# привыкает не верить предупреждениям.
MARK = re.compile(r"^[A-Z]{3,8}_\d+$")


def check(text, own_words=None):
    """Что в тексте всё ещё похоже на секрет.

    Последняя проверка перед отправкой: шаблоны неидеальны, и лучше увидеть
    пропущенное самому, чем узнать о нём от того, кому файл ушёл.
    """
    found = []
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            val = m.group(2) if kind in GROUPED else m.group(0)
            if val in KEEP or val.lower() in KEEP or MARK.match(val):
                continue
            found.append({"kind": kind, "title": TITLES.get(kind, kind),
                          "value": val[:80]})
    # Свои слова ищем тем же выражением, что и при скрытии: иначе проверка
    # промолчит на «Петровой», хотя в списке есть «Петрова».
    for word in (own_words or []):
        if not word:
            continue
        m = word_pattern(word).search(text)
        if m:
            found.append({"kind": "NAME", "title": TITLES["NAME"], "value": m.group(0)})

    # Один и тот же домен встречается в логе десятки раз — в списке он нужен
    # один. И отбрасываем куски, которые уже входят в найденное целиком:
    # первые десять цифр телеграм-токена иначе показываются отдельной
    # строкой как ИНН, и человек ищет несуществующую вторую находку.
    # Ключ уникальности — само значение, а не пара с видом: один и тот же
    # ключ ловится двумя правилами сразу, и человеку незачем видеть его
    # дважды. Правила идут от конкретных к общим, поэтому остаётся точное.
    uniq, seen = [], set()
    values = [f["value"] for f in found]
    for f in found:
        key = f["value"]
        if key in seen:
            continue
        if any(f["value"] != v and f["value"] in v for v in values):
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


# ── работа с файлами ────────────────────────────────────────────────
def read_words(path):
    """Свой список слов: по одному в строке, решётка — комментарий.

    Читаем как utf-8-sig: Блокнот и PowerShell ставят в начало файла
    невидимую метку, и без этого первое слово в списке не совпадало
    ни с чем — название компании молча уходило заказчику.
    """
    p = Path(path)
    if not p.exists():
        return []
    return [w.strip() for w in p.read_text(encoding="utf-8-sig").splitlines()
            if w.strip() and not w.lstrip().startswith("#")]


def load_map(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_map(path, mapping):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(mapping, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def collect_files(target):
    """Файлы, которые имеет смысл разбирать."""
    target = Path(target)
    files = sorted(p for p in (target.rglob("*") if target.is_dir() else [target])
                   if p.is_file() and p.suffix.lower() not in BINARY_SUFFIXES)
    return files
