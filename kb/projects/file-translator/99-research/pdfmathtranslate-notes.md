# PDFMathTranslate 学习笔记（2026-02-28）

项目：<https://github.com/PDFMathTranslate/PDFMathTranslate>

## 基本信息
- Stars: 31k+
- 方向：科学 PDF 翻译并尽量保留原排版
- 技术：Python 生态
- 入口：CLI / GUI / Docker / 在线服务
- 支持翻译后端：Google / DeepL / OpenAI / Ollama 等

## 可借鉴点
1. **多翻译引擎抽象**：同一任务可切换引擎，方便成本/质量平衡。
2. **版式保留优先**：把“格式不破坏”当核心目标，不是附加项。
3. **部署形态完整**：本地 CLI + Docker + Web，适配不同用户。
4. **工程化成熟**：文档、发行包、跨平台支持做得较完整。

## 对我们 file-translator 的启发
1. 当前 v0.1 先支持 docx/md/json/txt，后续可扩展 PDF（高难度路线）。
2. v0.2 必须落实“多引擎适配层”（DeepL/Google/LLM）。
3. 增加任务化与并发（队列 + 分块并行 + 回填校验）。
4. 输出统一质量报告（结构一致性、术语命中率、缓存命中率）。

## 注意点
- PDF 翻译难度远高于 docx/md/json/txt：版式重建、公式、图表、跨页块处理都更复杂。
- 生产环境应优先使用官方 API，不建议依赖网页翻译抓取。
