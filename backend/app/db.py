import sqlite3, json, threading
DB="rateguard.db"
_lock=threading.Lock()
def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("create table if not exists metrics (id integer primary key, timestamp real, payload text)")
def save_metric(payload):
    with _lock, sqlite3.connect(DB) as c:
        c.execute("insert into metrics(timestamp,payload) values(?,?)",(payload["timestamp"],json.dumps(payload)))
def history(limit=200):
    with sqlite3.connect(DB) as c:
        rows=c.execute("select payload from metrics order by id desc limit ?",(limit,)).fetchall()
    return [json.loads(x[0]) for x in reversed(rows)]
