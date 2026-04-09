# LangSmith Setup

This project can be visualized in LangSmith after you enable tracing and run the
workflow normally.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Set environment variables

Add these values to your `.env` file:

```env
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_MODEL_NAME=qwen-plus
OPENAI_TEMPERATURE=0.7

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=liuliumei-product-workflow
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

## 3. Run the workflow

Interactive mode:

```bash
python main.py
```

Example mode:

```bash
python example.py
```

## 4. What you will see in LangSmith

The code now sends runs with:

- `run_name` such as `interactive-product-workflow`
- tags such as `liuliumei`, `langgraph`, `dashscope`
- metadata including the model name

This makes the LangGraph execution easier to find and inspect in LangSmith.

## Notes

- `main.py` and `example.py` now call `wait_for_all_tracers()` before exit so
  short CLI runs are less likely to disappear before traces are uploaded.
- If traces still do not appear, first confirm that `LANGSMITH_API_KEY` and
  `LANGSMITH_TRACING=true` are both set in the same shell session that runs the
  app.
