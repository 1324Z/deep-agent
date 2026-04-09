import json

from config import LANGSMITH_PROJECT, build_run_config
from graph import create_graph

try:
    from langchain_core.tracers.langchain import wait_for_all_tracers
except Exception:  # pragma: no cover - compatibility fallback
    def wait_for_all_tracers() -> None:
        return None


def main() -> None:
    """Run the interactive product discussion workflow."""

    app = create_graph()
    config = build_run_config(
        thread_id="session-1",
        run_name="interactive-product-workflow",
        tags=["cli", "interactive"],
    )

    user_query = input("请输入您的产品需求问题：\n")
    initial_state = {"user_query": user_query}

    print("\n" + "=" * 80)
    print("产品讨论系统启动")
    if LANGSMITH_PROJECT:
        print(f"LangSmith project: {LANGSMITH_PROJECT}")
    print("=" * 80)

    try:
        print("\n[阶段1] 问题分析中...")
        for _event in app.stream(initial_state, config, stream_mode="values"):
            pass

        state = app.get_state(config)
        print("\n解析后的需求：")
        for i, query in enumerate(state.values.get("parsed_queries", []), 1):
            print(f"{i}. {query}")

        confirm = input("\n是否继续？(yes/no): ")
        if confirm.lower() != "yes":
            print("已取消。")
            return

        app.update_state(config, {"user_query": user_query})

        print("\n[阶段2] 生成执行计划中...")
        for event in app.stream(None, config, stream_mode="values"):
            if "plan" in event:
                break

        state = app.get_state(config)
        plan = state.values.get("plan", [])
        print("\n执行计划：")
        for i, step in enumerate(plan, 1):
            print(f"{i}. {step}")

        confirm = input("\n是否执行此计划？(yes/no): ")
        if confirm.lower() != "yes":
            print("已取消。")
            return

        print("\n[阶段3] 执行智能体协作...")
        print("-" * 80)

        last_agent = ""
        for event in app.stream(None, config, stream_mode="values"):
            agent_history = event.get("agent_history", [])
            if agent_history:
                last_agent = agent_history[-1]

                if last_agent == "market_agent":
                    print("\n[市场研究智能体] 完成分析")
                    market_output = event.get("market_output", {})
                    if market_output:
                        print(json.dumps(market_output, ensure_ascii=False, indent=2))
                    print("-" * 80)
                elif last_agent == "product_agent":
                    print("\n[产品设计智能体] 完成设计")
                    product_output = event.get("product_output", {})
                    if product_output:
                        print(json.dumps(product_output, ensure_ascii=False, indent=2))
                    print("-" * 80)
                elif last_agent == "dev_agent":
                    print("\n[产品研发智能体] 完成评估")
                    dev_output = event.get("dev_output", {})
                    if dev_output:
                        print(json.dumps(dev_output, ensure_ascii=False, indent=2))
                    print("-" * 80)
                elif last_agent == "summary_agent":
                    print("\n[总结智能体] 完成总结")
                    summary_output = event.get("summary_output", "")
                    if summary_output:
                        print(summary_output)
                    print("-" * 80)

            next_agent = event.get("next_agent", "")
            if next_agent == "human_input_agent" or last_agent == "human_input_title":
                print("\n等待用户反馈...")
                break

            if event.get("terminal", False) or next_agent == "end":
                print("\n工作流执行完成。")
                break

        state = app.get_state(config)
        if state.values.get("next_agent") == "human_input_agent":
            print("\n当前总结：")
            print(state.values.get("summary_output", ""))

            feedback = input(
                "\n请输入您的反馈（输入 'APPROVE' 表示确认结束，或输入具体反馈继续优化）：\n"
            )

            if feedback.upper() == "APPROVE":
                app.update_state(config, {"human_feedback": feedback, "terminal": True})
                print("\n感谢使用，最终方案已确认。")
            else:
                app.update_state(config, {"human_feedback": feedback, "terminal": False})
                print("\n根据您的反馈继续优化...")

                for event in app.stream(None, config, stream_mode="values"):
                    agent_history = event.get("agent_history", [])
                    if agent_history:
                        print(f"\n执行: {agent_history[-1]}")
                    if event.get("terminal", False):
                        break

        print("\n" + "=" * 80)
        print("产品讨论系统结束")
        print("=" * 80)
    finally:
        # Ensure LangSmith receives all pending traces before the CLI exits.
        wait_for_all_tracers()


if __name__ == "__main__":
    main()
