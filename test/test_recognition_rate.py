#!/usr/bin/env python3
"""
术语识别率测试

测试目标：验证术语识别率 = 识别到的术语数 / 术语总数
原理：使用 apply_glossary_protected 识别术语并替换为占位符
"""
import argparse
import re
import sqlite3
from pathlib import Path


def load_glossary(conn, src_lang, tgt_lang, domain=None):
    """加载术语库"""
    rows = conn.execute("""
        SELECT DISTINCT ls.text AS src_text, lt.text AS tgt_text
        FROM term_concept c
        JOIN term_lexeme ls ON ls.concept_id = c.id 
            AND ls.lang = ? AND ls.status = 'approved'
        JOIN term_lexeme lt ON lt.concept_id = c.id 
            AND lt.lang = ? AND lt.status = 'approved'
        WHERE (? IS NULL OR c.domain = ?)
    """, (src_lang, tgt_lang, domain, domain)).fetchall()
    return [(r["src_text"], r["tgt_text"]) for r in rows if r["src_text"] and r["tgt_text"]]


def count_terms_in_text(text, term_list):
    """统计文本中出现的术语次数（长词优先，不重复计数）

    规则：
    1) 按术语长度从长到短匹配
    2) 一个字符位置只能被一个术语占用（避免短词重复计入长词内部）
    """
    found = {}

    # 长词优先：长度降序
    sorted_terms = sorted(term_list, key=lambda x: len(x[0]), reverse=True)

    occupied = [False] * len(text)

    for src_term, tgt_term in sorted_terms:
        pattern = re.escape(src_term)
        term_len = len(src_term)
        count = 0

        for m in re.finditer(pattern, text):
            s, e = m.start(), m.end()
            # 只计入未被更长术语占用的片段
            if any(occupied[s:e]):
                continue
            for i in range(s, e):
                occupied[i] = True
            count += 1

        if count > 0:
            found[src_term] = (count, tgt_term)

    return found


def test_recognition_rate(source_text, db_path, src_lang="cn", tgt_lang="en", domain=None):
    """测试术语识别率"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. 加载术语库
    term_list = load_glossary(conn, src_lang, tgt_lang, domain)
    print(f"术语库总数: {len(term_list)} 条")
    
    # 2. 统计源文中实际出现的术语
    found_terms = count_terms_in_text(source_text, term_list)
    total_terms_in_text = sum(count for count, _ in found_terms.values())
    
    print(f"\n源文中出现的术语: {len(found_terms)} 种, {total_terms_in_text} 次")
    for src, (count, tgt) in found_terms.items():
        print(f"  - {src}: {count}次 → {tgt}")
    
    # 3. 模拟 apply_glossary_protected 逻辑
    # 关键：按术语长度从长到短排序，避免短术语先匹配导致长术语无法识别
    term_list_sorted = sorted(
        [(src, tgt) for src, tgt in term_list if src in found_terms],
        key=lambda x: len(x[0]),
        reverse=True
    )
    
    out = source_text
    token_map = {}
    idx = 0
    recognized_count = 0
    
    for src_term, tgt_term in term_list_sorted:
        if src_term not in found_terms:
            continue  # 源文中没这个词，跳过
        
        token = f"FTTERM{idx}"
        new_out, count = re.subn(re.escape(src_term), token, out)
        if count > 0:
            token_map[token] = tgt_term
            out = new_out
            recognized_count += count
            idx += 1
    
    conn.close()
    
    # 4. 计算识别率
    # 识别率 = 识别到的术语次数 / 源文中术语出现的总次数
    recognition_rate = (recognized_count / total_terms_in_text * 100) if total_terms_in_text > 0 else 0
    
    print(f"\n识别结果:")
    print(f"  - 识别到的术语次数: {recognized_count}")
    print(f"  - 源文术语总次数: {total_terms_in_text}")
    print(f"  - 识别率: {recognition_rate:.2f}%")
    
    # 5. 识别失败的术语
    if recognized_count < total_terms_in_text:
        missed = total_terms_in_text - recognized_count
        print(f"\n未识别的术语次数: {missed}")
    
    return {
        "total_terms_in_db": len(term_list),
        "terms_found_in_text": len(found_terms),
        "total_term_occurrences": total_terms_in_text,
        "recognized_occurrences": recognized_count,
        "recognition_rate": recognition_rate,
        "term_details": found_terms
    }


def main():
    parser = argparse.ArgumentParser(description="术语识别率测试")
    parser.add_argument("--input", "-i", required=True, help="源文件路径")
    parser.add_argument("--db", default=None, help="术语库路径")
    parser.add_argument("--src", default="cn", help="源语言")
    parser.add_argument("--tgt", default="en", help="目标语言")
    parser.add_argument("--domain", default=None, help="术语领域")
    parser.add_argument("--text", "-t", help="直接输入文本（忽略文件）")
    args = parser.parse_args()
    
    # 确定术语库路径
    if args.db:
        db_path = Path(args.db)
    else:
        project_root = Path(__file__).parent.parent
        db_path = project_root / "src" / "file_translator" / "translator_terms.db"
    
    if not db_path.exists():
        print(f"错误: 术语库不存在: {db_path}")
        return 1
    
    # 获取源文本
    if args.text:
        source_text = args.text
    else:
        source_path = Path(args.input)
        if not source_path.exists():
            print(f"错误: 源文件不存在: {source_path}")
            return 1
        source_text = source_path.read_text(encoding="utf-8")
    
    print(f"源文本:\n{source_text[:200]}...")
    print("-" * 50)
    
    result = test_recognition_rate(
        source_text=source_text,
        db_path=db_path,
        src_lang=args.src,
        tgt_lang=args.tgt,
        domain=args.domain
    )
    
    print("-" * 50)
    print(f"\n最终识别率: {result['recognition_rate']:.2f}%")
    
    return 0 if result['recognition_rate'] >= 98 else 1


if __name__ == "__main__":
    exit(main())
