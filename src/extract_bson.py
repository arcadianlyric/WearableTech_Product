"""Stream LifeSnaps BSON collections into one parquet file per data type.

No MongoDB needed: bson.decode_file_iter reads the dump directly.
All fields are kept as strings; typed parsing happens downstream.

Usage: python src/extract_bson.py data/raw/rais_anonymized/mongo_rais_anonymized data/interim/bson
"""
import ast
import re
import sys
from pathlib import Path

import bson
import pyarrow as pa
import pyarrow.parquet as pq

CHUNK = 500_000
COLLECTIONS = {"fitbit": "id", "sema": "user_id", "surveys": "user_id"}


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", str(t).lower()).strip("_") or "untyped"


def flatten(doc, id_field):
    row = {"uid": str(doc[id_field])}
    for k, v in (doc.get("data") or {}).items():
        row[k] = None if v is None else str(v)
    return row


def heart_rate_row(doc):
    v = doc["data"]["value"]  # {'bpm': 67, 'confidence': 1}
    if isinstance(v, str):
        v = ast.literal_eval(v)
    return {"uid": str(doc["id"]), "dateTime": doc["data"]["dateTime"],
            "bpm": int(v["bpm"]), "confidence": int(v["confidence"])}


class Sink:
    def __init__(self, path):
        self.path, self.rows, self.writer, self.cols, self.n = path, [], None, None, 0

    def add(self, row):
        self.rows.append(row)
        if len(self.rows) >= CHUNK:
            self.flush()

    def flush(self):
        if not self.rows:
            return
        if self.cols is None:
            # Small types fit in the first chunk, so this sees every key they use.
            self.cols = list(dict.fromkeys(k for r in self.rows for k in r))
            sample = self.rows[0]
            self.schema = pa.schema([(c, pa.int64() if isinstance(sample.get(c), int) else pa.string())
                                     for c in self.cols])
        table = pa.Table.from_pylist([{c: r.get(c) for c in self.cols} for r in self.rows], schema=self.schema)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, self.schema)
        self.writer.write_table(table)
        self.n += len(self.rows)
        self.rows = []

    def close(self):
        self.flush()
        if self.writer:
            self.writer.close()


def main(src, out):
    src, out = Path(src), Path(out)
    for coll, id_field in COLLECTIONS.items():
        (out / coll).mkdir(parents=True, exist_ok=True)
        sinks = {}
        with open(src / f"{coll}.bson", "rb") as f:
            for i, doc in enumerate(bson.decode_file_iter(f)):
                t = doc.get("type") if coll != "sema" else doc["data"].get("SURVEY_NAME")
                s = slug(t)
                if s not in sinks:
                    sinks[s] = Sink(out / coll / f"{s}.parquet")
                sinks[s].add(heart_rate_row(doc) if s == "heart_rate" else flatten(doc, id_field))
                if i and i % 5_000_000 == 0:
                    print(f"{coll}: {i:,}", flush=True)
        for s, sink in sinks.items():
            sink.close()
            print(f"{coll}/{s}: {sink.n:,} rows", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
