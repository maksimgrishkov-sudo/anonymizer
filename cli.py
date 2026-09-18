# -*- coding: utf-8 -*-
"""Ширма из командной строки — для папок и для работы по SSH.

    python cli.py hide logs/app.log             → app.log.anon + anon.map.json
    python cli.py hide src/ --out anon_src/     → всю папку разом
    python cli.py back ответ.txt                → ответ.restored.txt
    python cli.py check app.log.anon            → что осталось подозрительного

Словарь замен кладётся рядом с результатом и никуда не отправляется:
только он раскрывает скрытое и только он позволяет вернуть всё назад.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from anon import Anonymizer, check, collect_files, load_map, read_words, save_map
from anon.patterns import TITLES

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

HERE = Path(__file__).parent
WORDS = HERE / "words.txt"


def cmd_hide(target: Path, out: Path | None):
    files = collect_files(target)
    if not files:
        raise SystemExit("нечего обрабатывать: %s" % target)

    base = target if target.is_dir() else target.parent
    map_path = (out or base) / "anon.map.json"
    anon = Anonymizer(mapping=load_map(map_path), own_words=read_words(WORDS))

    done = skipped = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            print("  пропуск (не текст):", f.name)
            skipped += 1
            continue
        hidden = anon.hide(text)
        if out:
            dest = out / (f.relative_to(base) if target.is_dir() else Path(f.name))
            dest.parent.mkdir(parents=True, exist_ok=True)
        else:
            dest = f.with_suffix(f.suffix + ".anon")
        dest.write_text(hidden, encoding="utf-8")
        done += 1

    save_map(map_path, anon.map)

    print("обработано файлов: %d%s" % (done, ", пропущено: %d" % skipped if skipped else ""))
    for row in anon.report():
        print("  %-28s %d" % (row["title"], row["unique"]))
    print()
    print("СЛОВАРЬ ЗАМЕН:", map_path)
    print("Он раскрывает всё скрытое — держать у себя, никуда не отправлять.")


def cmd_back(target: Path, map_path: Path | None):
    mp = map_path or target.parent / "anon.map.json"
    if not mp.exists():
        raise SystemExit("нет словаря замен: %s" % mp)
    anon = Anonymizer(mapping=load_map(mp))
    text = target.read_text(encoding="utf-8")
    out = target.with_name(target.stem + ".restored" + target.suffix)
    out.write_text(anon.restore(text), encoding="utf-8")
    print("подставлено меток:", anon.restored_count(text))
    print("готово:", out)


def cmd_check(target: Path):
    found = check(target.read_text(encoding="utf-8"), read_words(WORDS))
    if not found:
        print("чисто: ничего похожего на секрет не нашёл")
        return
    print("ОСТАЛОСЬ В ФАЙЛЕ:", len(found))
    for item in found[:25]:
        print("  %-28s %s" % (item["title"], item["value"]))
    if len(found) > 25:
        print("  … и ещё %d" % (len(found) - 25))
    # ненулевой код возврата: удобно ставить проверку в конвейер перед отправкой
    raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description="Ширма — обезличивание файлов")
    ap.add_argument("cmd", choices=["hide", "back", "check"])
    ap.add_argument("path")
    ap.add_argument("--out", help="папка для результата (для hide)")
    ap.add_argument("--map", help="путь к словарю замен (для back)")
    a = ap.parse_args()

    target = Path(a.path)
    if not target.exists():
        raise SystemExit("нет такого пути: %s" % target)

    if a.cmd == "hide":
        cmd_hide(target, Path(a.out) if a.out else None)
    elif a.cmd == "back":
        cmd_back(target, Path(a.map) if a.map else None)
    else:
        cmd_check(target)


if __name__ == "__main__":
    main()
