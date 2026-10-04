"""検索対象（KB）の決め方と、索引・ソケットの置き場所。クライアントとサーバで共有する。

- KB: 環境変数 HIKIDASU_KB（既定 ~/notes）。絶対パスに正規化する
- 対象ファイル: HIKIDASU_DIRS が無ければ KB 配下の *.md を再帰的に全部（隠しディレクトリと node_modules は除く）。
  あればカンマ区切りのサブディレクトリ直下の *.md だけ
- 状態: $XDG_CACHE_HOME/hikidasu/<KB のハッシュ>/ に index.npz と sock を置く。KB ごとに分かれるので複数 KB を同時に常駐できる。
  HIKIDASU_SOCK / HIKIDASU_INDEX で個別に上書きできる
"""
import glob
import hashlib
import os


def kb_dir() -> str:
    return os.path.abspath(os.path.expanduser(os.environ.get("HIKIDASU_KB", "~/notes")))


def state_dir(kb: str) -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "hikidasu", hashlib.sha1(kb.encode()).hexdigest()[:10])
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def sock_path(kb: str) -> str:
    return os.environ.get("HIKIDASU_SOCK") or os.path.join(state_dir(kb), "sock")


def index_path(kb: str) -> str:
    return os.environ.get("HIKIDASU_INDEX") or os.path.join(state_dir(kb), "index.npz")


def list_notes(kb: str, dirs: "str | None") -> list[str]:
    """KB 相対パスの一覧（ソート済み）。"""
    dirs = dirs if dirs is not None else os.environ.get("HIKIDASU_DIRS")
    if dirs:
        paths = []
        for d in dirs.split(","):
            paths += glob.glob(os.path.join(kb, d.strip(), "*.md"))
    else:
        paths = []
        for root, subdirs, files in os.walk(kb):
            subdirs[:] = [s for s in subdirs if not s.startswith(".") and s != "node_modules"]
            paths += [os.path.join(root, f) for f in files if f.endswith(".md")]
    return sorted(os.path.relpath(p, kb) for p in paths)
