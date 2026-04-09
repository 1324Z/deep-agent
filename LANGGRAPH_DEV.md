# LangGraph Dev

This project can be launched with `langgraph dev` to visualize the full agent
workflow in LangGraph Studio.

## 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## 2. Start the local LangGraph dev server

```bash
langgraph dev
```

The CLI will read [langgraph.json](/d:/毕业设计/langgraph.json) and load the
graph entrypoint from [graph.py](/d:/毕业设计/graph.py).

## 3. Open Studio

After the server starts, open the local Studio URL shown in the terminal.

## Current graph entrypoint

- Graph id: `liuliumei_workflow`
- Entry function: `make_graph`
- File: [graph.py](/d:/毕业设计/graph.py)

## Notes

- The server uses `.env`, so your DashScope and LangSmith variables will be
  loaded automatically.
- If `langgraph` or `langgraph-cli` is missing, run the install command again.
- If you want traces to also appear in LangSmith, keep `LANGSMITH_TRACING=true`
  in `.env`.
