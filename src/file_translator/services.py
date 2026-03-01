from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests


@dataclass
class TranslationRequest:
    text: str
    src_lang: str
    tgt_lang: str
    engine: str
    glossary_version: str = "v1"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cached(conn: sqlite3.Connection, req: TranslationRequest) -> str | None:
    h = text_hash(req.text)
    row = conn.execute(
        """
        SELECT id, translated_text FROM translation_cache
        WHERE source_hash=? AND src_lang=? AND tgt_lang=? AND engine=? AND glossary_version=?
        """,
        (h, req.src_lang, req.tgt_lang, req.engine, req.glossary_version),
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE translation_cache SET hit_count=hit_count+1, last_hit_at=? WHERE id=?",
        (_now(), row["id"]),
    )
    conn.commit()
    return row["translated_text"]


def save_cache(conn: sqlite3.Connection, req: TranslationRequest, translated_text: str) -> None:
    h = text_hash(req.text)
    now = _now()
    conn.execute(
        """
        INSERT INTO translation_cache
        (source_hash, source_text, src_lang, tgt_lang, engine, glossary_version, translated_text, created_at, last_hit_at, hit_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(source_hash, src_lang, tgt_lang, engine, glossary_version)
        DO UPDATE SET translated_text=excluded.translated_text, last_hit_at=excluded.last_hit_at
        """,
        (h, req.text, req.src_lang, req.tgt_lang, req.engine, req.glossary_version, translated_text, now, now),
    )
    conn.commit()


def apply_glossary(conn: sqlite3.Connection, text: str, src_lang: str, tgt_lang: str, domain: str | None = None) -> str:
    query = """
    SELECT ls.text AS src_text, lt.text AS tgt_text
    FROM term_concept c
    JOIN term_lexeme ls ON ls.concept_id = c.id AND ls.lang=? AND ls.status='approved'
    JOIN term_lexeme lt ON lt.concept_id = c.id AND lt.lang=? AND lt.status='approved'
    WHERE (? IS NULL OR c.domain = ?)
    ORDER BY ls.priority ASC, LENGTH(ls.text) DESC
    """
    rows = conn.execute(query, (src_lang, tgt_lang, domain, domain)).fetchall()
    out = text
    for r in rows:
        src_text, tgt_text = r["src_text"], r["tgt_text"]
        if not src_text or not tgt_text:
            continue
        out = re.sub(re.escape(src_text), tgt_text, out)
    return out


def _translate_mock(text: str, src_lang: str, tgt_lang: str) -> str:
    return f"[{src_lang}->{tgt_lang}] {text}"


def _translate_xfyun(text: str, src_lang: str, tgt_lang: str) -> str:
    app_id = os.getenv("XFYUN_APP_ID")
    api_key = os.getenv("XFYUN_API_KEY")
    api_secret = os.getenv("XFYUN_API_SECRET")
    endpoint = os.getenv("XFYUN_TRANSLATE_URL", "https://ntrans.xfyun.cn/v2/ots")

    if not app_id or not api_key or not api_secret:
        raise RuntimeError("XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET must be set")

    u = urlparse(endpoint)
    host = u.netloc
    path = u.path or "/v2/ots"

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    body = {
        "common": {"app_id": app_id},
        "business": {"from": src_lang, "to": tgt_lang},
        "data": {"text": base64.b64encode(text.encode("utf-8")).decode("utf-8")},
    }
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

    digest_raw = hashlib.sha256(body_bytes).digest()
    digest = "SHA-256=" + base64.b64encode(digest_raw).decode("utf-8")

    sign_origin = f"host: {host}\ndate: {date_str}\nPOST {path} HTTP/1.1\ndigest: {digest}"
    signature = base64.b64encode(
        hmac.new(api_secret.encode("utf-8"), sign_origin.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    authorization = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line digest", signature="{signature}"'
    )

    resp = requests.post(
        endpoint,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Host": host,
            "Date": date_str,
            "Digest": digest,
            "Authorization": authorization,
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()

    code = data.get("code", 0)
    if code != 0:
        raise RuntimeError(f"XFYUN API error: code={code}, message={data.get('message')}")

    try:
        dst = data["data"]["result"]["trans_result"]["dst"]
        return dst
    except Exception:
        # 兼容部分返回结构
        try:
            dst_b64 = data["data"]["result"]["trans_result"]["dst"]
            return base64.b64decode(dst_b64).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Unexpected XFYUN response: {data}") from e


def _translate_kimi(text: str, src_lang: str, tgt_lang: str) -> str:
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        raise RuntimeError("KIMI_API_KEY is not set")

    base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1").rstrip("/")
    model = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
    url = f"{base_url}/chat/completions"

    system_prompt = (
        "You are a professional translation engine. "
        "Translate the user text from source language to target language accurately. "
        "Return translation only, no explanations."
    )

    user_prompt = (
        f"source_language={src_lang}\n"
        f"target_language={tgt_lang}\n"
        "text:\n"
        f"{text}"
    )

    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Unexpected Kimi response: {data}") from e


def translate_via_engine(text: str, src_lang: str, tgt_lang: str, engine: str) -> str:
    engine = (engine or "mock").lower()
    if engine == "mock":
        return _translate_mock(text, src_lang, tgt_lang)
    if engine == "xfyun":
        return _translate_xfyun(text, src_lang, tgt_lang)
    if engine in {"kimi", "llm_kimi"}:
        return _translate_kimi(text, src_lang, tgt_lang)
    raise RuntimeError(f"Unsupported engine: {engine}")
