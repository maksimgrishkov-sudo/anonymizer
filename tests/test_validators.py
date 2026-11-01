# -*- coding: utf-8 -*-
"""Контрольные суммы реквизитов (01.11.2026).

Без них «ИНН» — любые 10 или 12 цифр подряд: ID чата Telegram, метка времени,
номер заказа. Ширма прятала их как ИНН, а в базе компаний пропускала опечатки.

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anon import Anonymizer, check
from anon.validators import inn, luhn, ogrn, snils


class TestValidators(unittest.TestCase):
    def test_инн_юрлица(self):
        self.assertTrue(inn("7707083893"))        # ПАО Сбербанк
        self.assertFalse(inn("7707083894"))       # последняя цифра сбита

    def test_инн_физлица(self):
        self.assertTrue(inn("500100732259"))
        self.assertFalse(inn("500100732258"))

    def test_инн_с_пробелами_и_не_цифры(self):
        self.assertTrue(inn("7707 083 893"))
        self.assertFalse(inn("77070838"))
        self.assertFalse(inn("abc"))

    def test_огрн_и_огрнип(self):
        self.assertTrue(ogrn("1027700132195"))    # ПАО Сбербанк
        self.assertFalse(ogrn("1027700132196"))
        self.assertTrue(ogrn("304500116000157"))
        self.assertFalse(ogrn("304500116000158"))

    def test_снилс(self):
        self.assertTrue(snils("112-233-445 95"))
        self.assertFalse(snils("112-233-445 96"))

    def test_карта_по_луну(self):
        self.assertTrue(luhn("4111 1111 1111 1111"))
        self.assertFalse(luhn("4111 1111 1111 1112"))


class TestHideWithChecksums(unittest.TestCase):
    def test_настоящий_инн_прячется(self):
        out = Anonymizer().hide("ИНН поставщика 7707083893")
        self.assertNotIn("7707083893", out)

    def test_случайные_десять_цифр_остаются(self):
        # ID чата и метка времени — не ИНН; раньше они превращались в INN_1
        text = "chat_id=1048941477 ts=1793199720"
        self.assertEqual(Anonymizer().hide(text), text)

    def test_огрн_снилс_карта_прячутся(self):
        text = "ОГРН 1027700132195, СНИЛС 112-233-445 95, карта 4111 1111 1111 1111"
        out = Anonymizer().hide(text)
        for v in ("1027700132195", "112-233-445 95", "4111 1111 1111 1111"):
            self.assertNotIn(v, out)

    def test_обратимость_с_реквизитами(self):
        text = "ИНН 7707083893, ОГРН 1027700132195, карта 4111 1111 1111 1111"
        a = Anonymizer()
        self.assertEqual(a.restore(a.hide(text)), text)

    def test_проверка_не_ругается_на_случайные_цифры(self):
        self.assertEqual(check("order 1048941477"), [])
        self.assertTrue(check("ИНН 7707083893"))


if __name__ == "__main__":
    unittest.main()
