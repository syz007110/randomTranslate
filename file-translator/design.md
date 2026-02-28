# File Translator 设计文档（v1）

## 1. 架构概览
- Parser 层：按文件类型解析可翻译文本节点。
- Router 层：根据格式/文本特征选择翻译引擎。
- Translator 层：统一调用接口（LLM、DeepL、Google 等）。
- Terminology 层：术语约束与替换。
- Cache 层：翻译结果缓存，减少重复请求。
- Writer 层：将译文回写到原结构。
- Validator 层：结构一致性校验并生成报告。

## 2. 术语库设计（概念中心模型）

### 2.1 term_concept
- id (PK)
- concept_key (UNIQUE)
- domain
- note
- created_at
- updated_at

### 2.2 term_lexeme
- id (PK)
- concept_id (FK -> term_concept.id)
- lang
- text
- is_preferred (0/1)
- priority
- status (approved/draft)
- created_at
- updated_at

> 含义：先定义“概念”，再给该概念挂多语言表达。

## 3. 缓存表设计

### translation_cache
- id (PK)
- source_hash
- source_text
- src_lang
- tgt_lang
- engine
- glossary_version
- translated_text
- quality_score (nullable)
- created_at
- last_hit_at
- hit_count

唯一索引建议：
`(source_hash, src_lang, tgt_lang, engine, glossary_version)`

## 4. SQLite 建表示例
```sql
CREATE TABLE term_concept (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept_key TEXT NOT NULL UNIQUE,
  domain TEXT,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE term_lexeme (
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

CREATE UNIQUE INDEX idx_term_lexeme_unique
ON term_lexeme(concept_id, lang, text);

CREATE TABLE translation_cache (
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

CREATE UNIQUE INDEX idx_cache_lookup
ON translation_cache(source_hash, src_lang, tgt_lang, engine, glossary_version);
```

## 5. 翻译流程
1. 解析文件 -> 抽取可翻译文本块。
2. 文本块预处理 -> 术语约束注入。
3. 查缓存 -> 命中则直接返回。
4. 未命中 -> 调用路由引擎翻译。
5. 翻译后回写 -> 结构校验。
6. 记录缓存与报告。
