# -*- coding: utf-8 -*-
"""Ширма — обезличивание файлов перед тем, как показать их постороннему."""
from .core import Anonymizer, check, collect_files, load_map, read_words, save_map

__all__ = ["Anonymizer", "check", "collect_files", "load_map", "read_words", "save_map"]
__version__ = "1.0.0"
