import sqlite3, json
from pathlib import Path
from threading import RLock
from .models import Tick, utc_now

class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        with self.lock, self.conn:
            self.conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS ticks(
              id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
              sequence INTEGER NOT NULL, generation INTEGER NOT NULL,
              source_epoch INTEGER NOT NULL, received_at TEXT NOT NULL,
              raw_quote TEXT NOT NULL, normalized_quote TEXT NOT NULL,
              pip_size INTEGER NOT NULL, digit INTEGER NOT NULL,
              provider_id TEXT, quality TEXT NOT NULL,
              UNIQUE(symbol,generation,sequence));
            CREATE INDEX IF NOT EXISTS ix_ticks_symbol_seq ON ticks(symbol,sequence);
            CREATE TABLE IF NOT EXISTS signals(
              signal_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, generation INTEGER NOT NULL,
              snapshot_sequence INTEGER NOT NULL, target_sequence INTEGER NOT NULL,
              created_at TEXT NOT NULL, predicted_digit INTEGER,
              probabilities TEXT NOT NULL, status TEXT NOT NULL, verifier_reason TEXT NOT NULL,
              actual_digit INTEGER, target_source_epoch INTEGER, target_received_at TEXT,
              outcome TEXT, model_version TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_signals_status ON signals(status);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, level TEXT NOT NULL,
              component TEXT NOT NULL, message TEXT NOT NULL, details TEXT);
            """)

    def add_tick(self, tick: Tick):
        with self.lock, self.conn:
            self.conn.execute("""INSERT INTO ticks
              (symbol,sequence,generation,source_epoch,received_at,raw_quote,normalized_quote,
               pip_size,digit,provider_id,quality) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (tick.symbol,tick.sequence,tick.stream_generation,tick.source_epoch,tick.received_at,
               tick.raw_quote,tick.normalized_quote,tick.pip_size,tick.digit,tick.provider_id,tick.quality))

    def latest_sequence(self, symbol, generation):
        row = self.conn.execute("SELECT MAX(sequence) n FROM ticks WHERE symbol=? AND generation=?",(symbol,generation)).fetchone()
        return int(row["n"] or 0)

    def ticks(self, symbol, limit=2000):
        rows = self.conn.execute("SELECT * FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT ?",(symbol,limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def count_ticks(self, symbol):
        return self.conn.execute("SELECT COUNT(*) n FROM ticks WHERE symbol=?",(symbol,)).fetchone()["n"]

    def create_signal(self, signal):
        with self.lock, self.conn:
            self.conn.execute("""INSERT INTO signals
            (signal_id,symbol,generation,snapshot_sequence,target_sequence,created_at,predicted_digit,
             probabilities,status,verifier_reason,model_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (signal["signal_id"],signal["symbol"],signal["generation"],signal["snapshot_sequence"],
             signal["target_sequence"],signal["created_at"],signal["predicted_digit"],
             json.dumps(signal["probabilities"]),signal["status"],signal["verifier_reason"],signal["model_version"]))

    def resolve_signal(self, signal_id, tick):
        row = self.conn.execute("SELECT * FROM signals WHERE signal_id=?",(signal_id,)).fetchone()
        if not row or row["status"] != "PENDING":
            return
        outcome = ("ABSTAIN" if row["predicted_digit"] is None else
                   ("MATCH" if row["predicted_digit"] == tick.digit else "MISS"))
        with self.lock, self.conn:
            self.conn.execute("""UPDATE signals SET status='RESOLVED',actual_digit=?,target_source_epoch=?,
            target_received_at=?,outcome=? WHERE signal_id=?""",
            (tick.digit,tick.source_epoch,tick.received_at,outcome,signal_id))

    def pending_signals(self, symbol):
        rows = self.conn.execute("SELECT * FROM signals WHERE symbol=? AND status='PENDING' ORDER BY created_at",(symbol,)).fetchall()
        return [dict(r) for r in rows]

    def invalidate_generation(self, symbol, generation, reason):
        with self.lock, self.conn:
            self.conn.execute(
                "UPDATE signals SET status='INVALIDATED',verifier_reason=? "
                "WHERE symbol=? AND generation=? AND status='PENDING'",
                (reason, symbol, generation)
            )

    def signals(self, symbol, limit=100):
        rows = self.conn.execute("SELECT * FROM signals WHERE symbol=? ORDER BY created_at DESC LIMIT ?",(symbol,limit)).fetchall()
        result=[]
        for r in rows:
            d=dict(r); d["probabilities"]=json.loads(d["probabilities"]); result.append(d)
        return result

    def log(self, level, component, message, details=None):
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO events(at,level,component,message,details) VALUES(?,?,?,?,?)",
                              (utc_now(),level,component,message,json.dumps(details or {})))

    def events(self, limit=100):
        rows=self.conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
