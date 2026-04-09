import json
from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from config import build_llm
from prompt import (
    dev_system_message,
    market_system_message,
    product_system_message,
    summary_system_message,
)
from reporting import create_report_files
from state import LiuliumeiState


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _build_chat_content(agent_name: str, content: str) -> str:
    text = content.strip() if isinstance(content, str) else _to_text(content)
    return f"[{agent_name}]\n{text}"


def _parse_json_response(content: str) -> Dict:
    try:
        return json.loads(content)
    except Exception:
        return {"raw_output": content}


def _build_knowledge_context(state: LiuliumeiState) -> str:
    relevant_contents = str(state.get("relevant_contents", "") or "").strip()
    references = str(state.get("digit_reference", "") or "").strip()
    retrieval_query = str(state.get("retrieval_query", "") or "").strip()

    if not relevant_contents:
        return "本轮未命中本地知识库内容，请主要基于当前流程上下文作答。"

    parts = [
        f"检索查询：{retrieval_query or state.get('user_query', '')}",
        f"知识库内容：\n{relevant_contents}",
    ]
    if references:
        parts.append(f"知识库来源：\n{references}")
    return "\n\n".join(parts)


class Agent:
    def __init__(
        self,
        name: str,
        description: str,
        system_message: str,
        llm=None,
        temperature: float = 0.7,
        create_llm: bool = True,
    ):
        self.name = name
        self.description = description
        self.system_message = system_message
        self.llm = llm if llm is not None else (build_llm(temperature=temperature) if create_llm else None)

    def invoke(self, state: LiuliumeiState) -> Dict:
        raise NotImplementedError

    def _build_result(
        self,
        output_key: str,
        output_value: Any,
        message_content: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict:
        trace_entry = {
            "node_type": "agent",
            "agent": self.name,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output": output_value,
        }

        trace_message = AIMessage(
            name=self.name,
            content=_build_chat_content(self.name, message_content),
        )

        return {
            output_key: output_value,
            "agent_history": [self.name],
            "last_agent": self.name,
            "agent_traces": [trace_entry],
            "messages": [trace_message],
        }


class MarketAgent(Agent):
    def __init__(self, llm=None):
        super().__init__(
            name="market_agent",
            description="Analyze market trends, user needs, and competitors.",
            system_message=market_system_message,
            llm=llm,
            temperature=0.7,
        )

    def invoke(self, state: LiuliumeiState) -> Dict:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.system_message.format(date=current_date)
        user_prompt = (
            f"用户问题：{state.get('user_query', '')}\n\n"
            f"解析后的需求：{state.get('parsed_queries', [])}\n\n"
            f"{_build_knowledge_context(state)}\n\n"
            "请基于以上信息进行市场研究分析。"
        )

        response = self.llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        raw_content = _to_text(response.content)
        output = _parse_json_response(raw_content)
        return self._build_result("market_output", output, raw_content, system_prompt, user_prompt)


class DevAgent(Agent):
    def __init__(self, llm=None):
        super().__init__(
            name="dev_agent",
            description="Evaluate technical feasibility and implementation paths.",
            system_message=dev_system_message,
            llm=llm,
            temperature=0.6,
        )

    def invoke(self, state: LiuliumeiState) -> Dict:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.system_message.format(date=current_date)
        user_prompt = (
            f"用户问题：{state.get('user_query', '')}\n\n"
            f"市场研究结果：{json.dumps(state.get('market_output', {}), ensure_ascii=False)}\n\n"
            f"产品设计方案：{json.dumps(state.get('product_output', {}), ensure_ascii=False)}\n\n"
            f"{_build_knowledge_context(state)}\n\n"
            "请基于以上信息进行技术可行性评估。"
        )

        response = self.llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        raw_content = _to_text(response.content)
        output = _parse_json_response(raw_content)
        return self._build_result("dev_output", output, raw_content, system_prompt, user_prompt)


class ProductAgent(Agent):
    def __init__(self, llm=None):
        super().__init__(
            name="product_agent",
            description="Generate product concepts and design directions.",
            system_message=product_system_message,
            llm=llm,
            temperature=0.8,
        )

    def invoke(self, state: LiuliumeiState) -> Dict:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.system_message.format(date=current_date)
        user_prompt = (
            f"用户问题：{state.get('user_query', '')}\n\n"
            f"市场研究结果：{json.dumps(state.get('market_output', {}), ensure_ascii=False)}\n\n"
            f"技术评估结果：{json.dumps(state.get('dev_output', {}), ensure_ascii=False)}\n\n"
            f"{_build_knowledge_context(state)}\n\n"
            "请基于以上信息进行产品设计。"
        )

        response = self.llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        raw_content = _to_text(response.content)
        output = _parse_json_response(raw_content)
        return self._build_result("product_output", output, raw_content, system_prompt, user_prompt)


class SummaryAgent(Agent):
    def __init__(self, llm=None):
        super().__init__(
            name="summary_agent",
            description="Combine prior outputs into a final proposal.",
            system_message=summary_system_message,
            llm=llm,
            temperature=0.5,
        )

    def invoke(self, state: LiuliumeiState) -> Dict:
        system_prompt = self.system_message
        user_prompt = (
            f"用户问题：{state.get('user_query', '')}\n\n"
            "市场研究结果：\n"
            f"{json.dumps(state.get('market_output', {}), ensure_ascii=False, indent=2)}\n\n"
            "产品设计方案：\n"
            f"{json.dumps(state.get('product_output', {}), ensure_ascii=False, indent=2)}\n\n"
            "技术评估结果：\n"
            f"{json.dumps(state.get('dev_output', {}), ensure_ascii=False, indent=2)}\n\n"
            f"{_build_knowledge_context(state)}\n\n"
            "请基于以上所有信息进行综合总结。"
        )

        response = self.llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        raw_content = _to_text(response.content).strip() or "未生成到有效总结内容。"
        report_info = None
        report_error = ""
        final_content = raw_content

        try:
            report_info = create_report_files(
                user_query=state.get("user_query", ""),
                market_output=state.get("market_output", {}),
                product_output=state.get("product_output", {}),
                dev_output=state.get("dev_output", {}),
                summary_output=raw_content,
            )
            report_error = report_info.get("pdf_error", "")
            pdf_line = f"- 下载 PDF: {report_info['pdf_url']}\n" if report_info.get("pdf_url") else ""
            final_content = (
                f"{raw_content}\n\n"
                "报告链接：\n"
                f"- 在线预览: {report_info['preview_url']}\n"
                f"- 下载 HTML: {report_info['download_url']}\n"
                f"{pdf_line}"
            ).rstrip()
            if report_error and not report_info.get("pdf_url"):
                final_content = (
                    f"{final_content}\n\n"
                    "PDF 导出失败，当前保留 HTML 预览和下载。\n"
                    f"错误信息: {report_error}"
                )
        except Exception as exc:
            report_error = str(exc)
            final_content = (
                f"{raw_content}\n\n"
                "报告导出失败，但总结内容已保留。\n"
                f"错误信息: {report_error}"
            )

        result = self._build_result("summary_output", final_content, final_content, system_prompt, user_prompt)
        result["summary_statement"] = final_content
        result["report_url"] = report_info["preview_url"] if report_info else ""
        result["report_download_url"] = report_info["download_url"] if report_info else ""
        result["report_markdown_url"] = ""
        result["report_pdf_url"] = report_info["pdf_url"] if report_info else ""
        result["agent_traces"] = [
            {
                "node_type": "agent",
                "agent": self.name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "output": final_content,
                "report": report_info or {},
                "report_error": report_error,
            }
        ]
        return result


class HumanInputAgent(Agent):
    def __init__(self):
        super().__init__(
            name="human_input_agent",
            description="Pause for user feedback.",
            system_message="",
            llm=None,
            create_llm=False,
        )

    def invoke(self, state: LiuliumeiState) -> Dict:
        prompt_text = (
            "请提供反馈。\n\n"
            f"当前总结：\n{state.get('summary_output', '')}\n\n"
            "输入 APPROVE 表示确认结束；输入其他内容则会继续优化。"
        )
        feedback = interrupt(
            {
                "kind": "human_input_agent",
                "prompt": prompt_text,
                "summary_output": state.get("summary_output", ""),
            }
        )

        feedback_text = _to_text(feedback).strip()
        is_approved = feedback_text.upper() == "APPROVE"
        result_text = "已确认结束，准备收尾。" if is_approved else "已收到反馈，准备继续优化。"

        return {
            "agent_history": [self.name],
            "last_agent": self.name,
            "human_feedback": feedback_text,
            "terminal": is_approved,
            "agent_traces": [
                {
                    "node_type": "interrupt",
                    "agent": self.name,
                    "prompt": prompt_text,
                    "user_input": feedback,
                    "status": "approved" if is_approved else "continue_iteration",
                }
            ],
            "messages": [
                AIMessage(name=self.name, content=prompt_text),
                HumanMessage(content=feedback_text),
                AIMessage(name=self.name, content=f"[{self.name}]\n{result_text}"),
            ],
        }


def create_agents(llm=None):
    market_agent = MarketAgent(llm)
    dev_agent = DevAgent(llm)
    product_agent = ProductAgent(llm)
    summary_agent = SummaryAgent(llm)
    human_input_agent = HumanInputAgent()

    agents = [market_agent, dev_agent, product_agent, summary_agent, human_input_agent]

    return agents, {
        "market_agent": market_agent,
        "dev_agent": dev_agent,
        "product_agent": product_agent,
        "summary_agent": summary_agent,
        "human_input_agent": human_input_agent,
    }
