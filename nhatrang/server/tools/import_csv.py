"""CSV-импорт риелторов и сигналов (заполняет Некит).

  риелторы: name,kind,languages,contacts,notes,commission_free_confirmed,confirmed_at
            languages: через ';'; contacts: JSON-объект; commission_free_confirmed=1 принимается
            только вместе с непустым confirmed_at (ручное подтверждение Некитом).
  сигналы:  place,source,tag,count,url,confirmed
            place: имя или алиас места; confirmed!=1 пропускается и попадает в отчёт.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys

from app.tags import ALL_TAGS
from app.textgeo import fold


def import_realtors_csv(conn: sqlite3.Connection, path: str) -> dict:
    rep = {"added": 0, "rejected": []}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        cf = (row.get("commission_free_confirmed") or "0").strip()
        if cf == "1" and not (row.get("confirmed_at") or "").strip():
            rep["rejected"].append((row.get("name"), "commission_free без confirmed_at"))
            continue
        if (row.get("kind") or "").strip() not in ("ru", "vi"):
            rep["rejected"].append((row.get("name"), "kind должен быть ru или vi"))
            continue
        try:
            contacts = json.loads(row.get("contacts") or "{}")
        except ValueError:
            rep["rejected"].append((row.get("name"), "contacts не JSON"))
            continue
        langs = [x.strip() for x in (row.get("languages") or "").split(";") if x.strip()]
        conn.execute(
            "INSERT INTO realtors(name, kind, languages, commission_free_confirmed, confirmed_at, "
            "notes, contacts) VALUES(?,?,?,?,?,?,?)",
            (row["name"].strip(), row["kind"].strip(), json.dumps(langs, ensure_ascii=False),
             1 if cf == "1" else 0, (row.get("confirmed_at") or "").strip() or None,
             row.get("notes") or "", json.dumps(contacts, ensure_ascii=False)))
        rep["added"] += 1
    return rep


def _find_place(conn, name: str):
    fn = fold(name)
    hits = [r["id"] for r in conn.execute("SELECT id, name_fold, aliases FROM places") if
            r["name_fold"] == fn or any(fold(a) == fn for a in json.loads(r["aliases"]))]
    return hits[0] if len(hits) == 1 else None


def import_signals_csv(conn: sqlite3.Connection, path: str) -> dict:
    rep = {"added": 0, "skipped_unconfirmed": [], "rejected": []}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        if (row.get("confirmed") or "").strip() != "1":
            rep["skipped_unconfirmed"].append(row.get("place"))
            continue
        pid = _find_place(conn, row.get("place") or "")
        tag = (row.get("tag") or "").strip()
        if pid is None or tag not in ALL_TAGS:
            rep["rejected"].append((row.get("place"), "место не найдено/неоднозначно или неизвестный тег"))
            continue
        conn.execute("INSERT INTO signals(place_id, source, tag, count, url, confirmed) "
                     "VALUES(?,?,?,?,?,1)",
                     (pid, row["source"].strip(), tag, int(row.get("count") or 1), row.get("url")))
        rep["added"] += 1
    return rep


if __name__ == "__main__":
    from app.config import load_settings
    from app.db import connect, migrate
    c = connect(load_settings().db_path)
    migrate(c)
    kind, path = sys.argv[1], sys.argv[2]
    print((import_realtors_csv if kind == "realtors" else import_signals_csv)(c, path))
