#!/usr/bin/env python3
"""markdown ノート群を日本語特化の埋め込み（ruri-v3-310m）で検索する CLI。qmd 不要、日本語のまま。
常駐サーバ（hikidasu-serve.py）に Unix ソケットで問い合わせ、居なければ起動して待つ（初回のみ数秒〜数十秒）。

使い方: hikidasu "質問文" [-n 8] [--json] | --status | --stop
環境変数: HIKIDASU_KB（検索対象ディレクトリ。既定 ~/notes）、HIKIDASU_SOCK、HIKIDASU_INDEX、HIKIDASU_MODEL、HIKIDASU_OFFLINE=1
出力: cos  パス  description（--json なら [{path,score,description}]）
注意: cos の絶対値では「該当なし」を判定できない（該当なしの問いでも 1 位が 0.82 前後になる）。description を読んで判断する。
      サーバは起動時の HIKIDASU_KB を保持する。別の KB で呼ぶと不一致エラーになるので --stop してから呼び直す。"""
import argparse, fcntl, json, os, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
SOCK = os.environ.get("HIKIDASU_SOCK", os.path.join(HERE, "hikidasu.sock"))
LOG = SOCK + ".log"
PY = os.path.join(HERE, ".venv", "bin", "python") if os.path.exists(os.path.join(HERE, ".venv", "bin", "python")) else sys.executable
KB = os.path.abspath(os.path.expanduser(os.environ.get("HIKIDASU_KB", "~/notes")))

ap = argparse.ArgumentParser()
ap.add_argument("query", nargs="?")
ap.add_argument("-n", type=int, default=8)
ap.add_argument("--json", action="store_true")
ap.add_argument("--stop", action="store_true")
ap.add_argument("--status", action="store_true")
ap.add_argument("--wait", type=int, default=120, help="自動起動を待つ秒数")
a = ap.parse_args()


def call(req, timeout=120):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCK)
    s.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        c = s.recv(65536)
        if not c:
            break
        buf += c
    s.close()
    return json.loads(buf)


def ping():
    try:
        r = call({"cmd": "ping"}, timeout=5)
        return r if r.get("ok") else None
    except (OSError, ValueError):
        return None


def log_tail(n=5):
    try:
        return "".join(open(LOG, encoding="utf-8", errors="replace").readlines()[-n:])
    except OSError:
        return ""


def ensure_server():
    """居なければ起動する。同時起動は lock ファイルで直列化し、取得後にもう一度 ping する"""
    if ping():
        return False
    lock = open(SOCK + ".start.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        if ping():
            return False
        logf = open(LOG, "a")
        proc = subprocess.Popen([PY, os.path.join(HERE, "hikidasu-serve.py")], stdout=logf, stderr=logf, stdin=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + a.wait
        while time.time() < deadline:
            if ping():
                return True
            if proc.poll() is not None:
                sys.exit(f"常駐サーバが終了コード {proc.returncode} で落ちた。ログ末尾:\n{log_tail()}")
            time.sleep(0.3)
        sys.exit(f"常駐サーバが {a.wait} 秒以内に応答しなかった（初回はモデル取得で時間がかかる。HIKIDASU_OFFLINE=1 ならキャッシュ必須）。ログ末尾:\n{log_tail()}")
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


if a.stop:
    if ping():
        call({"cmd": "stop"})
        print("常駐を停止した")
    else:
        print("常駐していない")
    sys.exit()
if a.status:
    p = ping()
    print(f"常駐中 docs={p['docs']} kb={p['kb']} model={p['model']}" if p else "常駐していない")
    sys.exit()
if not a.query:
    ap.error("質問文が要る")

t0 = time.time()
started = ensure_server()
p = ping()
if p and os.path.abspath(p.get("kb", "")) != KB:
    sys.exit(f"常駐サーバの対象（{p['kb']}）と HIKIDASU_KB（{KB}）が違う。`hikidasu --stop` で止めてから呼び直す")
r = call({"query": a.query, "n": a.n})
if "error" in r:
    sys.exit("サーバ側エラー: " + r["error"])
if a.json:
    print(json.dumps(r["rows"], ensure_ascii=False, indent=1))
else:
    for x in r["rows"]:
        print(f"{x['score']:.2f}  {x['path']}\n      {x['description'][:140]}")
    note = f"、{r['warning']}" if r.get("warning") else ""
    print(f"({r['docs']} 本、再埋め込み {r['reembedded']}、検索 {r['ms']:.0f}ms、合計 {time.time()-t0:.1f}s{'、常駐を起動' if started else ''}{note})", file=sys.stderr)
