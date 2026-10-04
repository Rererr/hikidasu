"""hikidasu: 日本語の markdown ノートを常駐した埋め込みモデルで意味検索する。"""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hikidasu")
except PackageNotFoundError:  # ソースから直接実行したとき
    __version__ = "0.0.0+src"
