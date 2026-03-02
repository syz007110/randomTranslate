from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urlparse

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


def normalize_lang(lang: str) -> str:
    l = (lang or "").strip().lower()
    mapping = {
        "zh": "cn",
        "zh-cn": "cn",
        "zh_cn": "cn",
        "en-us": "en",
        "en_us": "en",
        "jp": "ja",
    }
    return mapping.get(l, l)


def apply_glossary(conn: sqlite3.Connection, text: str, src_lang: str, tgt_lang: str, domain: str | None = None) -> str:
    src_lang = normalize_lang(src_lang)
    tgt_lang = normalize_lang(tgt_lang)
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
    endpoint = os.getenv("XFYUN_TRANSLATE_URL", "https://itrans.xf-yun.com/v1/its")

    if not app_id or not api_key or not api_secret:
        raise RuntimeError("XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET must be set")

    u = urlparse(endpoint)
    host = u.netloc
    path = u.path or "/v1/its"

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    request_line = f"POST {path} HTTP/1.1"
    signature_origin = f"host: {host}\ndate: {date_str}\n{request_line}"
    signature = base64.b64encode(
        hmac.new(api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    query = urlencode({"authorization": authorization, "host": host, "date": date_str}, quote_via=quote)
    url = f"{endpoint}?{query}"

    from_lang = normalize_lang(src_lang)
    to_lang = normalize_lang(tgt_lang)

    body = {
        "header": {"app_id": app_id, "status": 3},
        "parameter": {"its": {"from": from_lang, "to": to_lang, "result": {}}},
        "payload": {
            "input_data": {
                "encoding": "utf8",
                "status": 3,
                "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            }
        },
    }

    resp = requests.post(url, json=body, timeout=90)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"XFYUN HTTP error {resp.status_code}: {resp.text[:500]}") from e

    data = resp.json()
    header = data.get("header", {})
    code = header.get("code", -1)
    if code != 0:
        raise RuntimeError(f"XFYUN API error: code={code}, message={header.get('message')}, sid={header.get('sid')}")

    try:
        text_b64 = data["payload"]["result"]["text"]
        decoded = base64.b64decode(text_b64).decode("utf-8")
        decoded_json = json.loads(decoded)
        return decoded_json["trans_result"]["dst"]
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

    max_retries = 4
    for attempt in range(max_retries):
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

        if resp.status_code != 429:
            resp.raise_for_status()
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                raise RuntimeError(f"Unexpected Kimi response: {data}") from e

        # 429: exponential backoff with optional Retry-After support
        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            sleep_s = max(1, int(retry_after))
        else:
            sleep_s = 2 ** attempt
        if attempt == max_retries - 1:
            raise RuntimeError(f"Kimi rate limited (429) after retries: {resp.text[:300]}")
        time.sleep(sleep_s)

    raise RuntimeError("Kimi request failed unexpectedly")


def _translate_kimi_batch(texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        raise RuntimeError("KIMI_API_KEY is not set")

    base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1").rstrip("/")
    model = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
    url = f"{base_url}/chat/completions"

    payload_items = [{"id": i, "text": t} for i, t in enumerate(texts)]

    system_prompt = (
        "You are a professional translation engine. "
        "Translate each item's text from source language to target language accurately. "
        "Return strict JSON only: {\"items\":[{\"id\":0,\"translation\":\"...\"}, ...]}"
    )
    user_prompt = (
        f"source_language={src_lang}\n"
        f"target_language={tgt_lang}\n"
        f"items_json={json.dumps(payload_items, ensure_ascii=False)}"
    )

    max_retries = 4
    for attempt in range(max_retries):
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
            timeout=120,
        )

        if resp.status_code != 429:
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            try:
                obj = json.loads(content)
                items = obj.get("items", [])
                out = [""] * len(texts)
                for it in items:
                    idx = int(it["id"])
                    if 0 <= idx < len(out):
                        out[idx] = str(it.get("translation", ""))
                # fallback fill for missing
                for i, v in enumerate(out):
                    if not v:
                        out[i] = texts[i]
                return out
            except Exception as e:
                raise RuntimeError(f"Unexpected Kimi batch response: {content[:500]}") from e

        retry_after = resp.headers.get("Retry-After")
        sleep_s = max(1, int(retry_after)) if retry_after and retry_after.isdigit() else 2 ** attempt
        if attempt == max_retries - 1:
            raise RuntimeError(f"Kimi rate limited (429) after retries: {resp.text[:300]}")
        time.sleep(sleep_s)

    raise RuntimeError("Kimi batch request failed unexpectedly")


def translate_via_engine(text: str, src_lang: str, tgt_lang: str, engine: str) -> str:
    engine = (engine or "mock").lower()
    if engine == "mock":
        return _translate_mock(text, src_lang, tgt_lang)
    if engine == "xfyun":
        return _translate_xfyun(text, src_lang, tgt_lang)
    if engine in {"kimi", "llm_kimi"}:
        return _translate_kimi(text, src_lang, tgt_lang)
    raise RuntimeError(f"Unsupported engine: {engine}")


def translate_many_via_engine(texts: list[str], src_lang: str, tgt_lang: str, engine: str) -> list[str]:
    engine = (engine or "mock").lower()
    if not texts:
        return []
    if engine in {"kimi", "llm_kimi"}:
        return _translate_kimi_batch(texts, src_lang, tgt_lang)
    return [translate_via_engine(t, src_lang, tgt_lang, engine) for t in texts]
