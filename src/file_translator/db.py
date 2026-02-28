from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime


def utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
CREATE TABLE IF NOT EXISTS term_concept (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept_key TEXT NOT NULL UNIQUE,
  domain TEXT,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS term_lexeme (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept_id INTEGER NOT NULL,
  lang TEXT NOT NULL,
  text TEXT NOT NULL,
  is_preferred INTEGER NOT NULL DEFAULT 0,
  priority INTEGER NOT NULL DEFAULT 100,
  status TEXT NOT NULL DEFAULT 'approved',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (concept_id) REFERENCES term_concept(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_term_lexeme_unique
ON term_lexeme(concept_id, lang, text);

CREATE TABLE IF NOT EXISTS translation_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_hash TEXT NOT NULL,
  source_text TEXT NOT NULL,
  src_lang TEXT NOT NULL,
  tgt_lang TEXT NOT NULL,
  engine TEXT NOT NULL,
  glossary_version TEXT NOT NULL DEFAULT 'v1',
  translated_text TEXT NOT NULL,
  quality_score REAL,
  created_at TEXT NOT NULL,
  last_hit_at TEXT NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_lookup
ON translation_cache(source_hash, src_lang, tgt_lang, engine, glossary_version);
"""
    )
    conn.commit()
