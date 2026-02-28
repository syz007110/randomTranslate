from __future__ import annotations

from pathlib import Path

from .db import connect, init_schema
from .file_ops import translate_docx, translate_json, translate_md, translate_txt
from .services import TranslationRequest, apply_glossary, get_cached, save_cache, translate_via_engine

DB_PATH = Path.home() / ".file_translator" / "translator.db"


def make_translate_fn(conn, src_lang: str, tgt_lang: str, engine: str, domain: str | None):
    def _translate(text: str) -> str:
        req = TranslationRequest(text=text, src_lang=src_lang, tgt_lang=tgt_lang, engine=engine)
        cached = get_cached(conn, req)
        if cached is not None:
            return cached

        glossed = apply_glossary(conn, text, src_lang=src_lang, tgt_lang=tgt_lang, domain=domain)
        translated = translate_via_engine(glossed, src_lang, tgt_lang, engine)
        save_cache(conn, req, translated)
        return translated

    return _translate


def translate_file(in_path: Path, out_path: Path, src: str, tgt: str, engine: str, domain: str | None, max_workers: int = 4):
    conn = connect(DB_PATH)
    try:
        init_schema(conn)
        tf = make_translate_fn(conn, src, tgt, engine, domain)
        suffix = in_path.suffix.lower()
        if suffix == ".docx":
            translate_docx(in_path, out_path, tf, max_workers=max_workers)
        else:
            content = in_path.read_text(encoding="utf-8")
            if suffix == ".txt":
                result = translate_txt(content, tf, max_workers=max_workers)
            elif suffix == ".md":
                result = translate_md(content, tf, max_workers=max_workers)
            elif suffix == ".json":
                result = translate_json(content, tf, max_workers=max_workers)
            else:
                raise RuntimeError(f"Unsupported extension: {suffix}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(result, encoding="utf-8")
    finally:
        conn.close()
