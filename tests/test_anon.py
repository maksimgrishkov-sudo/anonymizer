# -*- coding: utf-8 -*-
"""Проверки Ширмы.

Главное, что проверяется, — не «нашёл ли шаблон почту», а свойства, без
которых инструмент бесполезен или опасен:

  1. обратимость: что скрыли, то и вернули, дословно;
  2. устойчивость меток: одно значение — одна метка, и между файлами тоже;
  3. длинные метки не ломаются короткими (KEY_10 против KEY_1);
  4. служебные адреса остаются на месте, иначе лог нечитаем.

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anon import Anonymizer, check


class TestHide(unittest.TestCase):
    def test_обратимость(self):
        text = ("token=8638152401:AAEW6jeSP9aLE6hDrfYFIyP_HWqCRZXY3nA "
                "почта ivan@example.ru телефон +7 912 445-31-08 сервер 185.204.3.77")
        a = Anonymizer()
        hidden = a.hide(text)
        self.assertNotIn("8638152401", hidden)
        self.assertNotIn("ivan@example.ru", hidden)
        self.assertEqual(a.restore(hidden), text)

    def test_одно_значение_одна_метка(self):
        a = Anonymizer()
        hidden = a.hide("ключ sk-aaaabbbbccccdddd1 и снова sk-aaaabbbbccccdddd1")
        self.assertEqual(hidden.count("KEY_1"), 2)
        self.assertEqual(len(a.map), 1)

    def test_метки_сквозные_между_файлами(self):
        """Иначе связи между логом и кодом рвутся, и разбор теряет смысл."""
        a = Anonymizer()
        first = a.hide("сервер 185.204.3.77")
        second = a.hide("тот же сервер 185.204.3.77 в другом файле")
        mark = first.split()[-1]
        self.assertIn(mark, second)

    def test_нумерация_продолжается_после_загрузки_словаря(self):
        a = Anonymizer()
        a.hide("почта one@example.ru")
        b = Anonymizer(mapping=a.map)
        hidden = b.hide("почта two@example.ru")
        self.assertIn("MAIL_2", hidden)
        self.assertEqual(len(b.map), 2)

    def test_длинные_метки_не_ломаются_короткими(self):
        a = Anonymizer()
        text = " ".join("ключ sk-%016d" % i for i in range(12))
        hidden = a.hide(text)
        self.assertIn("KEY_12", hidden)
        self.assertEqual(a.restore(hidden), text)

    def test_служебные_адреса_не_трогаем(self):
        a = Anonymizer()
        hidden = a.hide("подключение к 127.0.0.1 и к api.telegram.org")
        self.assertIn("127.0.0.1", hidden)
        self.assertIn("api.telegram.org", hidden)

    def test_пароль_в_коде_прячется_а_имя_поля_остаётся(self):
        a = Anonymizer()
        hidden = a.hide('api_key = "sk-live-4f8a0c2e9b1d7a3f"')
        self.assertIn("api_key", hidden)
        self.assertNotIn("4f8a0c2e9b1d7a3f", hidden)

    def test_свои_слова(self):
        a = Anonymizer(own_words=["ООО Ромашка"])
        hidden = a.hide("заказ передан в ООО Ромашка сегодня")
        self.assertNotIn("Ромашка", hidden)
        self.assertEqual(a.restore(hidden), "заказ передан в ООО Ромашка сегодня")

    def test_свои_слова_в_падеже(self):
        """В списке «Петрова», в логе «Петровой» — фамилия должна скрыться.

        Найдено на живом примере: проверка молчала, а фамилия оставалась.
        """
        a = Anonymizer(own_words=["Петрова"])
        text = "Заявка от Петровой Анны, передана Петрову"
        hidden = a.hide(text)
        self.assertNotIn("Петров", hidden)
        self.assertEqual(a.restore(hidden), text)

    def test_имя_пользователя_в_пути_windows(self):
        """Путь из лога Windows приезжает с двойными слэшами.

        Шаблон ждал один — и имя пользователя уходило заказчику открытым.
        """
        a = Anonymizer()
        for text in (r"C:\Users\shandrin\bot", r"C:\\Users\\shandrin\\bot",
                     "/home/deploy/app"):
            hidden = a.hide(text)
            self.assertNotIn("shandrin", hidden, text)
            self.assertNotIn("deploy", hidden, text)
            self.assertEqual(a.restore(hidden), text)

    def test_проверка_видит_имя_пользователя(self):
        found = check(r"C:\\Users\\shandrin\\app.log")
        self.assertTrue(any(f["kind"] == "USER" for f in found))

    def test_проверка_не_ругается_на_свои_же_метки(self):
        """Обезличенный файл должен считаться чистым.

        Иначе человек привыкает не верить предупреждениям — и пропустит
        настоящее.
        """
        a = Anonymizer()
        hidden = a.hide(r"C:\Users\shandrin\bot, почта ivan@example.ru, сервер 185.204.3.77")
        self.assertEqual(check(hidden), [])


class TestWords(unittest.TestCase):
    def test_список_слов_с_меткой_в_начале_файла(self):
        """Блокнот и PowerShell пишут невидимую метку в первый байт.

        Из-за неё первое слово списка не совпадало ни с чем, и название
        компании оставалось в файле. Проверено на живом логе.
        """
        import tempfile
        from anon import read_words

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "words.txt"
            p.write_text("# комментарий\nРомашка\nПетрова\n", encoding="utf-8-sig")
            words = read_words(p)
            self.assertEqual(words, ["Ромашка", "Петрова"])
            a = Anonymizer(own_words=words)
            self.assertNotIn("Ромашка", a.hide("заказ для ООО Ромашка"))


class TestCheck(unittest.TestCase):
    def test_находит_пропущенное(self):
        found = check("свяжитесь: a.petrova@romashka.ru")
        self.assertTrue(any(f["kind"] == "MAIL" for f in found))

    def test_на_обезличенном_чисто(self):
        a = Anonymizer()
        hidden = a.hide("почта ivan@example.ru, ключ sk-aaaabbbbccccdddd1")
        self.assertEqual(check(hidden), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
