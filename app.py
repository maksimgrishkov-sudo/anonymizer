# -*- coding: utf-8 -*-
"""Локальный интерфейс Ширмы: http://127.0.0.1:8765

Запуск: python app.py

Только стандартная библиотека — ни одной внешней зависимости. Для
инструмента, через который проходят чужие секреты, это не педантизм:
чем меньше постороннего кода в цепочке, тем меньше поводов ему не верить.

Сервер слушает только петлевой адрес. Ни файлы, ни словарь замен никуда
не отправляются: всё считается на этой машине и здесь же остаётся.
"""
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from anon import Anonymizer, check, read_words

HERE = Path(__file__).parent
WORDS = HERE / "words.txt"
PORT = 8765

# Ограничение на размер тела запроса: браузер отдаёт файл целиком в память,
# и без потолка большой дамп положит процесс.
MAX_BODY = 32 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    # молчим в консоль: каждая строка лога — лишний шум при работе
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        # страница работает офлайн, внешние запросы ей запрещены
        self.send_header("Content-Security-Policy",
                         "default-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, (HERE / "static" / "index.html").read_bytes(),
                              "text/html; charset=utf-8")
        if path == "/style.css":
            return self._send(200, (HERE / "static" / "style.css").read_bytes(),
                              "text/css; charset=utf-8")
        if path == "/app.js":
            return self._send(200, (HERE / "static" / "app.js").read_bytes(),
                              "application/javascript; charset=utf-8")
        self._send(404, json.dumps({"error": "нет такой страницы"}, ensure_ascii=False))

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, json.dumps(
                {"error": "файл больше 32 МБ — такие лучше через командную строку"},
                ensure_ascii=False))
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._send(400, json.dumps({"error": "не разобрал запрос"},
                                              ensure_ascii=False))

        words = read_words(WORDS)
        text = data.get("text") or ""

        if self.path == "/api/hide":
            # словарь предыдущих файлов пачки приходит с клиента: так метки
            # остаются сквозными, и связи между файлами не рвутся
            anon = Anonymizer(mapping=data.get("map") or {}, own_words=words)
            hidden = anon.hide(text)
            return self._send(200, json.dumps({
                "text": hidden,
                "map": anon.map,
                "report": anon.report(),
                "left": check(hidden, words),
            }, ensure_ascii=False))

        if self.path == "/api/restore":
            anon = Anonymizer(mapping=data.get("map") or {}, own_words=words)
            return self._send(200, json.dumps({
                "text": anon.restore(text),
                "count": anon.restored_count(text),
            }, ensure_ascii=False))

        if self.path == "/api/check":
            return self._send(200, json.dumps({"left": check(text, words)},
                                              ensure_ascii=False))

        self._send(404, json.dumps({"error": "нет такого действия"}, ensure_ascii=False))


def main():
    if not WORDS.exists():
        WORDS.write_text(
            "# Свои слова, которые шаблоном не поймать: название компании,\n"
            "# ФИО сотрудников, внутренние названия систем. По одному в строке.\n"
            "# Регистр не важен.\n", encoding="utf-8")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("Ширма работает:", url)
    print("Файлы никуда не отправляются — всё считается здесь.")
    print("Остановить: Ctrl+C")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
