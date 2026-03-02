from __future__ import annotations

from pathlib import Path

from .db import connect, init_schema
from .file_ops import translate_docx, translate_json, translate_md, translate_txt
from .services import (
    TranslationRequest,
    apply_glossary,
    get_cached,
    save_cache,
    translate_many_via_engine,
    translate_via_engine,
)

DB_PATH = Path.home() / ".file_translator" / "translator.db"


class Translator:
    def __init__(self, src_lang: str, tgt_lang: str, engine: str, domain: str | None):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.engine = engine
        self.domain = domain

    def __call__(self, text: str) -> str:
        conn = connect(DB_PATH)
        try:
            req = TranslationRequest(text=text, src_lang=self.src_lang, tgt_lang=self.tgt_lang, engine=self.engine)
            cached = get_cached(conn, req)
            if cached is not None:
                return cached

            glossed = apply_glossary(conn, text, src_lang=self.src_lang, tgt_lang=self.tgt_lang, domain=self.domain)
            translated = translate_via_engine(glossed, self.src_lang, self.tgt_lang, self.engine)
            save_cache(conn, req, translated)
            return translated
        finally:
            conn.close()

    def translate_many(self, texts: list[str], max_workers: int = 4) -> list[str]:
        # 1) cache/glossary preprocess
        pending_idx = []
        pending_texts = []
        out = [""] * len(texts)

        conn = connect(DB_PATH)
        try:
            for i, text in enumerate(texts):
                req = TranslationRequest(text=text, src_lang=self.src_lang, tgt_lang=self.tgt_lang, engine=self.engine)
                cached = get_cached(conn, req)
                if cached is not None:
                    out[i] = cached
                    continue
                glossed = apply_glossary(conn, text, src_lang=self.src_lang, tgt_lang=self.tgt_lang, domain=self.domain)
                pending_idx.append(i)
                pending_texts.append(glossed)
        finally:
            conn.close()

        if pending_texts:
            # 2) engine batch call (LLM will use one request where possible)
            translated_pending = translate_many_via_engine(
                pending_texts, self.src_lang, self.tgt_lang, self.engine
            )

            # 3) save cache + fill output
            conn2 = connect(DB_PATH)
            try:
                for i, src_text, translated in zip(pending_idx, [texts[k] for k in pending_idx], translated_pending):
                    req = TranslationRequest(
                        text=src_text,
                        src_lang=self.src_lang,
                        tgt_lang=self.tgt_lang,
                        engine=self.engine,
                    )
                    save_cache(conn2, req, translated)
                    out[i] = translated
            finally:
                conn2.close()

        return out


def make_translate_fn(src_lang: str, tgt_lang: str, engine: str, domain: str | None):
    return Translator(src_lang=src_lang, tgt_lang=tgt_lang, engine=engine, domain=domain)


def translate_file(in_path: Path, out_path: Path, src: str, tgt: str, engine: str, domain: str | None, max_workers: int = 4):
    conn = connect(DB_PATH)
    try:
        init_schema(conn)
    finally:
        conn.close()

    tf = make_translate_fn(src, tgt, engine, domain)

    # For LLM, reduce parallel fan-out by default to avoid rate limits.
    if (engine or "").lower() in {"kimi", "llm_kimi"}:
        max_workers = min(max_workers, 1)

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
