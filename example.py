"""Examples for running the workflow with LangSmith-friendly metadata."""

import json

from config import LANGSMITH_PROJECT, build_run_config
from graph import create_graph

try:
    from langchain_core.tracers.langchain import wait_for_all_tracers
except Exception:  # pragma: no cover - compatibility fallback
    def wait_for_all_tracers() -> None:
        return None


def simple_example() -> None:
    print("=" * 80)
    print("Simple example: Liuliumei product discussion workflow")
    if LANGSMITH_PROJECT:
        print(f"LangSmith project: {LANGSMITH_PROJECT}")
    print("=" * 80)

    app = create_graph()
    config = build_run_config(
        thread_id="example-1",
        run_name="simple-example-workflow",
        tags=["example", "simple"],
    )

    user_query = (
        "溜溜梅计划推出一款面向Z世代的青梅类休闲零食，主打健康、低糖、解压。"
        "请基于当前市场趋势、用户需求和技术可行性，提出3个创新的产品方向。"
    )
    initial_state = {"user_query": user_query}

    print(f"\n用户问题：\n{user_query}\n")
    print("-" * 80)
    print("\n开始执行工作流...\n")

    try:
        step_count = 0
        for event in app.stream(initial_state, config, stream_mode="values"):
            agent_history = event.get("agent_history", [])
            if agent_history:
                last_agent = agent_history[-1]
                step_count += 1

                print(f"\n[步骤 {step_count}] {last_agent}")
                print("-" * 40)

                if last_agent == "market_agent" and "market_output" in event:
                    print("市场研究结果：")
                    for key, value in event["market_output"].items():
                        value_str = str(value)
                        print(f"\n{key}:")
                        print(value_str[:200] + "..." if len(value_str) > 200 else value_str)
                elif last_agent == "product_agent" and "product_output" in event:
                    print("产品设计结果：")
                    for key, value in event["product_output"].items():
                        value_str = str(value)
                        print(f"\n{key}:")
                        print(value_str[:200] + "..." if len(value_str) > 200 else value_str)
                elif last_agent == "dev_agent" and "dev_output" in event:
                    print("技术评估结果：")
                    for key, value in event["dev_output"].items():
                        value_str = str(value)
                        print(f"\n{key}:")
                        print(value_str[:200] + "..." if len(value_str) > 200 else value_str)
                elif last_agent == "summary_agent" and "summary_output" in event:
                    summary = event["summary_output"]
                    print("总结结果：")
                    print(summary[:500] + "..." if len(summary) > 500 else summary)

            if event.get("terminal", False) or event.get("next_agent") == "end":
                break
    finally:
        wait_for_all_tracers()

    print("\n" + "=" * 80)
    print("工作流执行完成")
    print("=" * 80)


def interactive_example() -> None:
    print("=" * 80)
    print("Interactive example: Liuliumei product discussion workflow")
    if LANGSMITH_PROJECT:
        print(f"LangSmith project: {LANGSMITH_PROJECT}")
    print("=" * 80)

    app = create_graph()
    config = build_run_config(
        thread_id="interactive-1",
        run_name="interactive-example-workflow",
        tags=["example", "interactive"],
    )

    user_query = input("\n请输入您的产品需求问题：\n")
    initial_state = {"user_query": user_query}

    print("\n开始分析...")

    try:
        for event in app.stream(initial_state, config, stream_mode="values"):
            if "parsed_queries" in event:
                print("\n解析后的需求：")
                for i, query in enumerate(event["parsed_queries"], 1):
                    print(f"{i}. {query}")
                break

        confirm = input("\n继续执行？(yes/no): ")
        if confirm.lower() != "yes":
            print("已取消。")
            return

        for event in app.stream(None, config, stream_mode="values"):
            agent_history = event.get("agent_history", [])
            if agent_history:
                print(f"\n执行: {agent_history[-1]}")
            if event.get("terminal", False):
                break
    finally:
        wait_for_all_tracers()

    print("\n完成。")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_example()
    else:
        simple_example()
