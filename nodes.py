import json
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from config import RAG_TOP_K, build_llm
from prompt import liuliumei_supervisor_prompt, planner_prompt_template
from retriever import format_references, format_relevant_contents, retrieve_knowledge
from state import LiuliumeiState


DEFAULT_PLAN = [
    "调用 market_agent，进行市场与竞品分析",
    "调用 product_agent，形成产品方案",
    "调用 dev_agent，评估技术可行性",
    "调用 summary_agent，基于前面各智能体结果形成最终总结",
]

APPROVE_WORDS = {"ok", "yes", "approve", "确认", "继续", "同意", "通过"}
SUMMARY_FALLBACK_STEP = "调用 summary_agent，基于前面各智能体结果形成最终总结"
VALID_NEXT_AGENTS = {
    "market_agent",
    "product_agent",
    "dev_agent",
    "summary_agent",
    "human_input_agent",
    "end",
}


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _extract_user_query(state: LiuliumeiState) -> str:
    if state.get("user_query"):
        return str(state["user_query"])

    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", "") == "human":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if content:
                return _to_text(content).strip()
    return ""


def _load_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text or text[0] not in "[{":
        return value

    try:
        return json.loads(text)
    except Exception:
        return value


def _is_approve(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in APPROVE_WORDS
    if isinstance(value, dict):
        approved = value.get("approved")
        if isinstance(approved, bool):
            return approved
        if isinstance(approved, str):
            return approved.strip().lower() in APPROVE_WORDS
    return False


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _is_summary_step(step: Any) -> bool:
    original = str(step)
    lowered = original.strip().lower()
    if not lowered:
        return False
    return "总结" in original or "summary" in lowered


def _ensure_summary_last(plan: Any) -> list[str]:
    steps = _as_string_list(plan)
    if not steps:
        return DEFAULT_PLAN.copy()
    if _is_summary_step(steps[-1]):
        return steps
    return [*steps, SUMMARY_FALLBACK_STEP]


def _build_interrupt_messages(name: str, prompt_text: str, user_value: Any, result_text: str) -> list:
    user_text = _to_text(user_value)
    return [
        AIMessage(name=name, content=f"[{name}]\n{prompt_text}"),
        HumanMessage(content=user_text),
        AIMessage(name=name, content=f"[{name}]\n{result_text}"),
    ]


def _apply_analysis_feedback(state: LiuliumeiState, review: Any) -> tuple[str, list[str], str]:
    current_user_query = state.get("user_query", "")
    current_parsed_queries = state.get("parsed_queries", [])
    review = _load_json_if_possible(review)

    if _is_approve(review):
        return current_user_query, current_parsed_queries, _to_text(review)

    if isinstance(review, dict):
        user_query = str(review.get("user_query", current_user_query))
        parsed_queries = review.get("parsed_queries", current_parsed_queries)
        return user_query, _as_string_list(parsed_queries), _to_text(review)

    if isinstance(review, list):
        return current_user_query, _as_string_list(review), _to_text(review)

    review_text = _to_text(review).strip()
    if not review_text:
        return current_user_query, current_parsed_queries, ""
    return review_text, [review_text], review_text


def _apply_plan_feedback(state: LiuliumeiState, review: Any) -> tuple[list[str], str]:
    current_plan = state.get("plan", [])
    review = _load_json_if_possible(review)

    if _is_approve(review):
        return _ensure_summary_last(current_plan), _to_text(review)
    if isinstance(review, dict):
        return _ensure_summary_last(review.get("plan", current_plan)), _to_text(review)
    if isinstance(review, list):
        return _ensure_summary_last(review), _to_text(review)

    review_text = _to_text(review).strip()
    if not review_text:
        return _ensure_summary_last(current_plan), ""
    return _ensure_summary_last([review_text]), review_text


def _build_retrieval_query(state: LiuliumeiState) -> str:
    parsed_queries = _as_string_list(state.get("parsed_queries", []))
    if parsed_queries:
        return "\n".join(parsed_queries)
    return str(state.get("user_query", "")).strip()


def init_state_nodes(state: LiuliumeiState) -> Dict:
    return {
        "current_step": 0,
        "agent_history": [],
        "agent_traces": [],
        "last_agent": "",
        "terminal": False,
        "human_feedback": "",
        "analysis_feedback": "",
        "planner_feedback": "",
        "summary_statement": "",
        "pending_interrupt": "",
        "market_output": None,
        "dev_output": None,
        "product_output": None,
        "summary_output": None,
        "report_url": "",
        "report_download_url": "",
        "report_markdown_url": "",
        "report_pdf_url": "",
        "digit_view": "",
        "digit_reference": "",
        "relevant_contents": "",
        "retrieval_query": "",
        "retrieved_docs": [],
    }


def init_agent_nodes_message(state: LiuliumeiState) -> Dict:
    agent_descriptions = """
1. market_agent - 市场研究智能体：负责市场洞察、用户需求分析、竞品分析
2. product_agent - 产品设计智能体：负责产品创意构思与设计
3. dev_agent - 产品研发智能体：负责评估技术可行性、提供实现方案
4. summary_agent - 总结智能体：负责综合各方信息形成最终产出
"""

    agent_configs = [
        {"name": "市场研究专家", "desc": "负责市场洞察、用户需求分析、竞品分析"},
        {"name": "产品设计师", "desc": "负责产品创意构思与设计"},
        {"name": "技术研发专家", "desc": "负责评估技术可行性、提供实现方案"},
        {"name": "产品总结专家", "desc": "负责综合各方信息形成最终产出"},
    ]

    return {
        "agent_descriptions": agent_descriptions,
        "agent_configs": agent_configs,
    }


def user_query_analysis(state: LiuliumeiState) -> Dict:
    user_query = _extract_user_query(state)
    parsed_queries = [user_query] if user_query else []

    return {
        "user_query": user_query,
        "parsed_queries": parsed_queries,
        "agent_traces": [
            {
                "node_type": "node",
                "node": "user_query_analysis",
                "input": user_query,
                "output": parsed_queries,
            }
        ],
    }


def analysis_interrupt_node(state: LiuliumeiState) -> Dict:
    prompt_text = (
        "请确认或修改需求解析。\n\n"
        f"当前用户问题：\n{state.get('user_query', '')}\n\n"
        f"当前解析结果：\n{_to_text(state.get('parsed_queries', []))}\n\n"
        "你可以直接输入新的文本，也可以输入 JSON，例如 "
        '{"parsed_queries": ["..."]}；输入 OK / 继续 则保持不变。'
    )

    review = interrupt(
        {
            "kind": "analysis_interrupt",
            "prompt": prompt_text,
            "current_user_query": state.get("user_query", ""),
            "parsed_queries": state.get("parsed_queries", []),
        }
    )

    user_query, parsed_queries, feedback_text = _apply_analysis_feedback(state, review)
    result_text = (
        "已收到需求分析阶段输入，继续执行。\n\n"
        f"最新用户问题：\n{user_query}\n\n"
        f"最新解析结果：\n{_to_text(parsed_queries)}"
    )

    return {
        "user_query": user_query,
        "parsed_queries": parsed_queries,
        "analysis_feedback": feedback_text,
        "pending_interrupt": "",
        "agent_traces": [
            {
                "node_type": "interrupt",
                "node": "analysis_interrupt",
                "prompt": prompt_text,
                "user_input": review,
                "output": parsed_queries,
            }
        ],
        "messages": _build_interrupt_messages("analysis_interrupt", prompt_text, review, result_text),
    }


def retrieve_context_node(state: LiuliumeiState) -> Dict:
    retrieval_query = _build_retrieval_query(state)
    results = retrieve_knowledge(retrieval_query, top_k=RAG_TOP_K)
    relevant_contents = format_relevant_contents(results)
    references = format_references(results)

    return {
        "retrieval_query": retrieval_query,
        "retrieved_docs": results,
        "relevant_contents": relevant_contents,
        "digit_reference": references,
        "agent_traces": [
            {
                "node_type": "retrieval",
                "node": "retrieve_context",
                "query": retrieval_query,
                "hit_count": len(results),
                "sources": [
                    {
                        "source": item["source"],
                        "chunk_id": item["chunk_id"],
                        "score": item["score"],
                    }
                    for item in results
                ],
            }
        ],
    }


def planner_node(state: LiuliumeiState) -> Dict:
    llm = build_llm(temperature=0.7)
    planner_prompt = planner_prompt_template.format(
        agent_descriptions=state.get("agent_descriptions", ""),
        summary_statement=state.get("summary_statement", ""),
        human_feedback=state.get("human_feedback", ""),
    )

    retrieval_context = state.get("relevant_contents", "")
    references = state.get("digit_reference", "")
    user_prompt = (
        f"用户问题：{state.get('user_query', '')}\n\n"
        f"解析后的需求：{_to_text(state.get('parsed_queries', []))}\n\n"
        f"知识库检索结果：\n{retrieval_context or '当前未命中本地知识库内容。'}\n\n"
        f"知识库来源：\n{references or '[]'}"
    )

    response = llm.invoke(
        [
            SystemMessage(content=planner_prompt),
            HumanMessage(content=user_prompt),
        ]
    )

    try:
        plan = json.loads(response.content)
        if not isinstance(plan, list):
            plan = DEFAULT_PLAN.copy()
    except Exception:
        plan = DEFAULT_PLAN.copy()

    plan = _ensure_summary_last(plan)
    return {
        "plan": plan,
        "current_step": 0,
        "agent_traces": [
            {
                "node_type": "node",
                "node": "planner_node",
                "system_prompt": planner_prompt,
                "user_prompt": user_prompt,
                "output": plan,
            }
        ],
    }


def planner_interrupt_node(state: LiuliumeiState) -> Dict:
    prompt_text = (
        "请确认或修改执行计划。\n\n"
        f"当前计划：\n{_to_text(state.get('plan', []))}\n\n"
        "你可以直接输入新的计划文本，也可以输入 JSON，例如 "
        '{"plan": ["..."]}；输入 OK / 继续 则保持不变。'
    )

    review = interrupt(
        {
            "kind": "planner_interrupt",
            "prompt": prompt_text,
            "plan": state.get("plan", []),
        }
    )

    plan, feedback_text = _apply_plan_feedback(state, review)
    result_text = f"已收到计划阶段输入，继续执行。\n\n最新计划：\n{_to_text(plan)}"

    return {
        "plan": plan,
        "planner_feedback": feedback_text,
        "pending_interrupt": "",
        "agent_traces": [
            {
                "node_type": "interrupt",
                "node": "planner_interrupt",
                "prompt": prompt_text,
                "user_input": review,
                "output": plan,
            }
        ],
        "messages": _build_interrupt_messages("planner_interrupt", prompt_text, review, result_text),
    }


def supervisor_node(state: LiuliumeiState) -> Dict:
    llm = build_llm(temperature=0.3)
    plan = _ensure_summary_last(state.get("plan", []))
    current_step = state.get("current_step", 0)
    last_agent = state.get("last_agent", "")
    agent_history = state.get("agent_history", [])
    has_summary_output = "summary_agent" in agent_history or bool(state.get("summary_output"))

    if current_step >= len(plan):
        if not has_summary_output:
            return {
                "plan": plan,
                "next_agent": "summary_agent",
                "terminal": False,
                "agent_traces": [
                    {
                        "node_type": "node",
                        "node": "supervisor_node",
                        "status": "force_final_summary",
                        "selected_next_agent": "summary_agent",
                    }
                ],
            }

        return {
            "plan": plan,
            "next_agent": "end",
            "terminal": True,
            "agent_traces": [
                {
                    "node_type": "node",
                    "node": "supervisor_node",
                    "status": "complete",
                }
            ],
        }

    current_plan_step = str(plan[current_step])
    lower_step = current_plan_step.lower()
    next_agent = "end"

    if "市场研究" in current_plan_step or "market" in lower_step:
        next_agent = "market_agent"
    elif "产品设计" in current_plan_step or "product" in lower_step:
        next_agent = "product_agent"
    elif "产品研发" in current_plan_step or "研发" in current_plan_step or "dev" in lower_step:
        next_agent = "dev_agent"
    elif "总结" in current_plan_step or "summary" in lower_step:
        next_agent = "summary_agent"
    elif "人工" in current_plan_step or "human" in lower_step:
        next_agent = "human_input_agent"

    if next_agent == "human_input_agent" and not has_summary_output:
        next_agent = "summary_agent"

    supervisor_prompt = ""
    if next_agent == last_agent and next_agent != "end":
        supervisor_prompt = liuliumei_supervisor_prompt + f"""

当前情况：
- 计划步骤：{current_plan_step}
- 上次调用的智能体：{last_agent}
- 智能体调用历史：{agent_history}
- 当前步骤索引：{current_step}

请根据规则选择下一个智能体，注意不能连续调用同一个智能体。
只返回智能体名称，可选项：market_agent, product_agent, dev_agent, summary_agent, human_input_agent, end
"""
        response = llm.invoke(
            [
                SystemMessage(content=supervisor_prompt),
                HumanMessage(content="请选择下一个智能体"),
            ]
        )
        candidate = str(response.content).strip()
        if candidate in VALID_NEXT_AGENTS:
            next_agent = candidate

    if next_agent == "human_input_agent" and not has_summary_output:
        next_agent = "summary_agent"

    return {
        "plan": plan,
        "next_agent": next_agent,
        "current_step": current_step + 1,
        "agent_traces": [
            {
                "node_type": "node",
                "node": "supervisor_node",
                "current_plan_step": current_plan_step,
                "last_agent": last_agent,
                "agent_history": agent_history,
                "routing_prompt": supervisor_prompt,
                "selected_next_agent": next_agent,
            }
        ],
    }


def human_input_title(state: LiuliumeiState) -> Dict:
    summary_text = state.get("summary_output", "")
    return {
        "agent_history": ["human_input_title"],
        "agent_traces": [
            {
                "node_type": "node",
                "node": "human_input_title",
                "summary_output": summary_text,
                "status": "waiting_for_feedback",
            }
        ],
    }
