"""埋め込みモデル（既定 cl-nagoya/ruri-v3-310m）を常駐させる検索サーバ。Unix ソケットで 1 行 JSON を受ける。
通常は `hikidasu` が自動起動するので、直接起動するのは検証時だけ。

要求: {"query": str, "n": int} / {"cmd": "ping"} / {"cmd": "stop"}
応答: {"rows": [{path, score, description}], "docs": int, "reembedded": int, "ms": float}
      ping は {"ok": true, "docs": int, "kb": str, "model": str, "version": str}

索引は要求ごとにノートの sha256 を見て差分だけ再埋め込みし、npz に保存する（一時ファイルに書いて置き換え）。
npz にはモデル名を記録し、違うモデルで起動したら捨てて作り直す。
二重起動は pid ファイルの flock で防ぐ。--idle 秒間要求が無ければ終了する（既定 3600）。
モデルの取得: 既定ではオンラインで Hugging Face から取得・更新を試みる。HIKIDASU_OFFLINE=1 でキャッシュのみ使う。"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import select
import signal
import socket
import sys
import time

from . import __version__, paths

_TAIL = re.compile(r"(?<=[。．])\s*[^。．？?]{1,16}[？?]+\s*$")


def strip_boilerplate(q: str) -> str:
    """「。」の後に続く 16 文字以内の短い疑問節（「何を疑う？」「なぜ？」など）だけを落とす。「。」が無い問いは触らない。
    除去版は原文と併用して文書ごとに高い方を採るので、外しても順位は原文側で守られる。"""
    q = q.strip()
    m = _TAIL.search(q)
    return q[: m.start()].rstrip("。． ") if m else q


def description_of(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    return ""


def main() -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    if os.environ.get("HIKIDASU_OFFLINE") == "1":
        os.environ["HF_HUB_OFFLINE"] = "1"

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kb", default=paths.kb_dir())
    ap.add_argument("--index", default=None)
    ap.add_argument("--sock", default=None)
    ap.add_argument("--idle", type=int, default=3600)
    ap.add_argument("--model", default=os.environ.get("HIKIDASU_MODEL", "cl-nagoya/ruri-v3-310m"))
    ap.add_argument("--dirs", default=None, help="KB 内で索引するサブディレクトリ（カンマ区切り）。既定は HIKIDASU_DIRS、無ければ再帰的に全 *.md")
    ap.add_argument("--version", action="version", version=f"hikidasu-serve {__version__}")
    a = ap.parse_args()
    a.kb = os.path.abspath(os.path.expanduser(a.kb))
    a.sock = a.sock or paths.sock_path(a.kb)
    a.index = a.index or paths.index_path(a.kb)
    if len(a.sock.encode()) > 100:
        sys.exit(f"ソケットパスが長すぎる（{len(a.sock.encode())} バイト、上限 104）: {a.sock}。HIKIDASU_SOCK で短い場所を指定する")

    # 二重起動の防止: pid ファイルを排他ロックし、取れなければ既に動いている
    pidfile = a.sock + ".pid"
    lock_fd = os.open(pidfile, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("既に起動している（pid ファイルがロック中）: " + pidfile)
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, str(os.getpid()).encode())

    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    class Index:
        def __init__(self):
            device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
            self.model = SentenceTransformer(a.model, device=device)
            self.model.max_seq_length = 8192
            self.vecs = {}  # path -> (hash, vec)
            if os.path.exists(a.index):
                try:
                    z = np.load(a.index, allow_pickle=False)
                    if str(z["model"]) == a.model:
                        self.vecs = {p: (h, v) for p, h, v in zip(z["paths"], z["hashes"], z["vecs"])}
                    else:
                        print(f"索引のモデルが違う（{z['model']} → {a.model}）。作り直す", flush=True)
                except Exception as e:  # 壊れた npz は捨てて作り直す
                    print(f"索引を読めない（{e!r}）。作り直す", flush=True)
            self.paths, self.texts, self.V = [], {}, None
            self.refresh()

        def refresh(self) -> int:
            plist = paths.list_notes(a.kb, a.dirs)
            texts = {p: open(os.path.join(a.kb, p), encoding="utf-8", errors="replace").read() for p in plist}
            hashes = {p: hashlib.sha256(texts[p].encode()).hexdigest()[:16] for p in plist}
            todo = [p for p in plist if p not in self.vecs or self.vecs[p][0] != hashes[p]]
            if todo:
                new = self.model.encode(["検索文書: " + texts[p] for p in todo], normalize_embeddings=True, batch_size=8, show_progress_bar=False)
                for p, v in zip(todo, new):
                    self.vecs[p] = (hashes[p], v)
            changed = bool(todo) or plist != self.paths or any(p not in plist for p in self.vecs)
            if changed:
                self.vecs = {p: self.vecs[p] for p in plist}
                if plist:
                    tmp = a.index + ".tmp.npz"
                    np.savez(tmp, model=np.array(a.model), paths=np.array(plist),
                             hashes=np.array([hashes[p] for p in plist]), vecs=np.stack([self.vecs[p][1] for p in plist]))
                    os.replace(tmp, a.index)
                self.V = np.stack([self.vecs[p][1] for p in plist]) if plist else None
            self.paths, self.texts = plist, texts
            return len(todo)

        def search(self, query: str, n: int) -> dict:
            t0 = time.time()
            reembedded = self.refresh()
            if self.V is None:
                return {"rows": [], "docs": 0, "reembedded": reembedded, "ms": 0.0,
                        "warning": f"索引対象が無い: {a.kb}（HIKIDASU_DIRS={a.dirs or os.environ.get('HIKIDASU_DIRS') or '未設定=再帰'}）"}
            qs = [query]
            stripped = strip_boilerplate(query)
            if stripped != query:
                qs.append(stripped)
            Q = self.model.encode(["検索クエリ: " + x for x in qs], normalize_embeddings=True, show_progress_bar=False)
            sims = np.max(self.V @ Q.T, axis=1)
            n = max(1, min(int(n), len(self.paths)))
            top = np.argsort(-sims)[:n]
            rows = [{"path": self.paths[i], "score": round(float(sims[i]), 3), "description": description_of(self.texts[self.paths[i]])} for i in top]
            return {"rows": rows, "docs": len(self.paths), "reembedded": reembedded, "ms": round(1000 * (time.time() - t0), 1)}

    t0 = time.time()
    idx = Index()
    os.umask(0o077)  # ソケットは作成時から自分専用
    if os.path.exists(a.sock):
        os.unlink(a.sock)  # ロックを持っているのは自分だけなので、残骸と判断できる
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(a.sock)
    os.chmod(a.sock, 0o600)
    srv.listen(8)

    def bye(*_):
        for f in (a.sock, pidfile):
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    print(f"ready docs={len(idx.paths)} kb={a.kb} model={a.model} startup={time.time()-t0:.1f}s sock={a.sock}", flush=True)
    last = time.time()
    while True:
        r, _, _ = select.select([srv], [], [], 30)
        if not r:
            if time.time() - last > a.idle:
                print("idle exit", flush=True)
                bye()
            continue
        conn, _ = srv.accept()
        conn.settimeout(10)
        last = time.time()
        try:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            req = json.loads(buf or b"{}")
            if req.get("cmd") == "ping":
                resp = {"ok": True, "docs": len(idx.paths), "kb": a.kb, "model": a.model, "version": __version__}
            elif req.get("cmd") == "stop":
                conn.sendall(b'{"ok":true}\n')
                conn.close()
                bye()
            else:
                resp = idx.search(req["query"], req.get("n", 8))
            conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode())
        except Exception as e:
            try:
                conn.sendall((json.dumps({"error": repr(e)}) + "\n").encode())
            except Exception:
                pass
        finally:
            conn.close()


if __name__ == "__main__":
    main()
