from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents import create_agents
from nodes import (
    analysis_interrupt_node,
    human_input_title,
    init_agent_nodes_message,
    init_state_nodes,
    planner_interrupt_node,
    planner_node,
    retrieve_context_node,
    supervisor_node,
    user_query_analysis,
)
from state import LiuliumeiState


def create_graph():
    """Create the LangGraph workflow."""

    _, agent_dict = create_agents()

    market_agent = agent_dict["market_agent"]
    dev_agent = agent_dict["dev_agent"]
    product_agent = agent_dict["product_agent"]
    summary_agent = agent_dict["summary_agent"]
    human_input_agent = agent_dict["human_input_agent"]

    graph = StateGraph(LiuliumeiState)

    graph.add_node("init_state_nodes", init_state_nodes)
    graph.add_node("init_agent_nodes_message", init_agent_nodes_message)
    graph.add_node("user_query_analysis", user_query_analysis)
    graph.add_node("analysis_interrupt", analysis_interrupt_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("planner_node", planner_node)
    graph.add_node("planner_interrupt", planner_interrupt_node)
    graph.add_node("supervisor_node", supervisor_node)

    graph.add_node("market_agent", market_agent.invoke)
    graph.add_node("dev_agent", dev_agent.invoke)
    graph.add_node("product_agent", product_agent.invoke)
    graph.add_node("summary_agent", summary_agent.invoke)
    graph.add_node("human_input_title", human_input_title)
    graph.add_node("human_input_agent", human_input_agent.invoke)

    graph.add_edge(START, "init_state_nodes")
    graph.add_edge("init_state_nodes", "init_agent_nodes_message")
    graph.add_edge("init_agent_nodes_message", "user_query_analysis")
    graph.add_edge("user_query_analysis", "analysis_interrupt")
    graph.add_edge("analysis_interrupt", "retrieve_context")
    graph.add_edge("retrieve_context", "planner_node")
    graph.add_edge("planner_node", "planner_interrupt")
    graph.add_edge("planner_interrupt", "supervisor_node")

    graph.add_conditional_edges(
        "supervisor_node",
        lambda state: state.get("next_agent", "end"),
        {
            "market_agent": "market_agent",
            "dev_agent": "dev_agent",
            "product_agent": "product_agent",
            "summary_agent": "summary_agent",
            "human_input_agent": "human_input_title",
            "end": END,
        },
    )

    for agent_name in ["market_agent", "dev_agent", "product_agent", "summary_agent"]:
        graph.add_edge(agent_name, "supervisor_node")

    graph.add_edge("human_input_title", "human_input_agent")
    graph.add_conditional_edges(
        "human_input_agent",
        lambda state: "supervisor_node" if state.get("terminal") else "user_query_analysis",
        {
            "supervisor_node": "supervisor_node",
            "user_query_analysis": "user_query_analysis",
        },
    )

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


def make_graph(config=None):
    """LangGraph CLI entrypoint for `langgraph dev`."""

    return create_graph()


if __name__ == "__main__":
    app = create_graph()
    config = {"configurable": {"thread_id": "test-1"}}
    initial_state = {
        "user_query": "请基于知识库和当前市场趋势，给出一份适合年轻用户的低糖青梅零食产品方向建议。",
    }

    print("开始执行工作流...")
    for event in app.stream(initial_state, config, stream_mode="values"):
        if "agent_history" in event and event["agent_history"]:
            print(f"执行节点: {event['agent_history'][-1]}")
