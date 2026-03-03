#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify translation speed and terminology hit rate")
    parser.add_argument("--input", default=None, help="Path to source text file (default: test/dic.txt)")
    parser.add_argument("--db", default=None, help="Path to terminology SQLite DB (default: src/file_translator/translator_terms.db)")
    parser.add_argument("--src", default="cn", help="Source language (default: cn)")
    parser.add_argument("--tgt", default="en", help="Target language (default: en)")
    parser.add_argument("--engine", default="mock", help="Translation engine (default: mock)")
    parser.add_argument("--domain", default=None, help="Optional terminology domain filter")
    parser.add_argument("--max-workers", type=int, default=4, help="Translation worker count (default: 4)")
    return parser


def resolve_paths(input_arg: str | None, db_arg: str | None) -> tuple[Path, Path, Path]:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    input_path = Path(input_arg).resolve() if input_arg else (project_root / "test" / "dic.txt")
    db_path = Path(db_arg).resolve() if db_arg else (project_root / "src" / "file_translator" / "translator_terms.db")
    return project_root, input_path, db_path


def load_units(input_path: Path) -> list[str]:
    content = input_path.read_text(encoding="utf-8")
    return [line for line in content.splitlines() if line.strip()]


def load_terms(db_path: Path, domain: str | None) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        if domain:
            query = """
            SELECT DISTINCT l.text
            FROM term_lexeme l
            JOIN term_concept c ON c.id = l.concept_id
            WHERE l.status='approved' AND c.domain=?
            """
            rows = conn.execute(query, (domain,)).fetchall()
        else:
            query = """
            SELECT DISTINCT text
            FROM term_lexeme
            WHERE status='approved'
            """
            rows = conn.execute(query).fetchall()
        return [r[0] for r in rows if r and r[0]]
    finally:
        conn.close()


def translate_units(
    units: list[str],
    db_path: Path,
    src_lang: str,
    tgt_lang: str,
    engine: str,
    domain: str | None,
    max_workers: int,
    normalize_lang,
    connect,
    init_schema,
    apply_glossary,
    lookup_exact_glossary_term,
    translate_many_via_engine,
) -> list[str]:
    src = normalize_lang(src_lang)
    tgt = normalize_lang(tgt_lang)
    out = [""] * len(units)
    pending_idx: list[int] = []
    pending_texts: list[str] = []

    conn = connect(db_path)
    try:
        init_schema(conn)
        for i, text in enumerate(units):
            exact = lookup_exact_glossary_term(
                conn,
                text=text,
                src_lang=src,
                tgt_lang=tgt,
                domain=domain,
            )
            if exact is not None:
                out[i] = exact
                continue

            glossed = apply_glossary(conn, text, src_lang=src, tgt_lang=tgt, domain=domain)
            pending_idx.append(i)
            pending_texts.append(glossed)
    finally:
        conn.close()

    if pending_texts:
        translated_pending = translate_many_via_engine(pending_texts, src, tgt, engine)
        for i, translated in zip(pending_idx, translated_pending):
            out[i] = translated

    return out


def main() -> int:
    args = build_parser().parse_args()
    project_root, input_path, db_path = resolve_paths(args.input, args.db)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1
    if not db_path.exists():
        print(f"ERROR: terminology DB not found: {db_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(project_root / "src"))

    from file_translator.db import connect, init_schema
    from file_translator.services import (
        apply_glossary,
        lookup_exact_glossary_term,
        normalize_lang,
        translate_many_via_engine,
    )

    units = load_units(input_path)
    if not units:
        print("ERROR: no non-empty lines found in input file", file=sys.stderr)
        return 1

    terms = load_terms(db_path, args.domain)

    start = time.perf_counter()
    translated_units = translate_units(
        units=units,
        db_path=db_path,
        src_lang=args.src,
        tgt_lang=args.tgt,
        engine=args.engine,
        domain=args.domain,
        max_workers=max(1, args.max_workers),
        normalize_lang=normalize_lang,
        connect=connect,
        init_schema=init_schema,
        apply_glossary=apply_glossary,
        lookup_exact_glossary_term=lookup_exact_glossary_term,
        translate_many_via_engine=translate_many_via_engine,
    )
    elapsed = time.perf_counter() - start

    translated_text = "\n".join(translated_units)
    matched_terms = sum(1 for term in terms if term in translated_text)
    total_terms = len(terms)
    hit_rate = (matched_terms / total_terms * 100.0) if total_terms else 0.0

    print("=== Translation Verification Result ===")
    print(f"Input file: {input_path}")
    print(f"Terminology DB: {db_path}")
    print(f"Translation units: {len(units)}")
    print(f"Engine: {args.engine}")
    print(f"Languages: {args.src} -> {args.tgt}")
    print(f"Domain filter: {args.domain if args.domain else '(none)'}")
    print(f"Translation time: {elapsed:.4f} seconds")
    print(f"Total terms in database: {total_terms}")
    print(f"Matched terms count: {matched_terms}")
    print(f"Terminology hit rate: {hit_rate:.2f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
