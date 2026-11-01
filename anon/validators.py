# -*- coding: utf-8 -*-
"""Контрольные суммы реквизитов: ИНН, ОГРН/ОГРНИП, СНИЛС, номер карты.

Шаблон «10 или 12 цифр» ловит что попало: ID чата, метку времени, номер
заказа. Контрольная цифра отсекает почти всё случайное — у случайного
десятизначного числа шанс сойтись примерно один из одиннадцати.

Формулы — по алгоритмам ФНС и ПФР; сверены с расширением Docx Anonymizer
(github.com/argmaster-dev/docx-anonymizer, src/core/validators.js, MIT).
Каждая функция принимает значение как в тексте — с пробелами и дефисами.
"""
import re

_INN10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _digits(value):
    s = re.sub(r"[\s\-.]", "", str(value))
    return s if s.isdigit() else ""


def _check(d, weights):
    return sum(w * d[i] for i, w in enumerate(weights)) % 11 % 10


def inn(value):
    """ИНН юрлица (10 цифр) или физлица и ИП (12 цифр)."""
    s = _digits(value)
    d = [int(c) for c in s]
    if len(s) == 10:
        return _check(d, _INN10) == d[9]
    if len(s) == 12:
        return _check(d, _INN12_1) == d[10] and _check(d, _INN12_2) == d[11]
    return False


def ogrn(value):
    """ОГРН (13 цифр, остаток от 11) или ОГРНИП (15 цифр, остаток от 13)."""
    s = _digits(value)
    if len(s) == 13:
        return int(s[:12]) % 11 % 10 == int(s[12])
    if len(s) == 15:
        return int(s[:14]) % 13 % 10 == int(s[14])
    return False


def snils(value):
    """СНИЛС: 9 цифр номера и 2 контрольные. Номера до 001-001-998 контролем не проверяются."""
    s = _digits(value)
    if len(s) != 11:
        return False
    total = sum(int(c) * (9 - i) for i, c in enumerate(s[:9]))
    if int(s[:9]) <= 1001998:
        return True
    ctl = total % 101
    return (0 if ctl == 100 else ctl) == int(s[9:])


def luhn(value):
    """Номер банковской карты, 13–19 цифр, алгоритм Луна."""
    s = _digits(value)
    if not 13 <= len(s) <= 19:
        return False
    total = 0
    for i, c in enumerate(reversed(s)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0
