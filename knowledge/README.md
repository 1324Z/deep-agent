# Knowledge Directory

把你希望 RAG 检索的资料放到这个目录里，当前版本会递归读取以下文件类型：

- `.md`
- `.txt`
- `.json`
- `.csv`

建议：

- 一个主题一份文件，避免单个文件过大
- 文件名尽量有语义，例如 `market_insights_2025.md`
- 内容尽量是纯文本，便于切块和检索

示例：

- `knowledge/品牌调研.md`
- `knowledge/竞品分析.txt`
- `knowledge/技术资料/原料说明.md`

放好资料后，重新运行 `langgraph dev` 或 `python main.py`，流程会在需求确认后自动检索这些内容，并把命中的上下文传给各个智能体。
