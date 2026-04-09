"""Shared configuration helpers for model and tracing setup."""

import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", os.getenv("OPENAI_API_KEY", ""))
DASHSCOPE_MODEL_NAME = os.getenv("DASHSCOPE_MODEL_NAME", os.getenv("OPENAI_MODEL", "qwen-plus"))
MODEL_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "liuliumei-product-workflow")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
STUDIO_DEBUG_IN_CHAT = os.getenv("STUDIO_DEBUG_IN_CHAT", "true").lower() == "true"
REPORT_BASE_URL = os.getenv("REPORT_BASE_URL", "http://127.0.0.1:2024")
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "knowledge")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000"))


AGENT_CONFIGS = {
    "market_agent": {
        "name": "Market Research Agent",
        "description": "Analyze market trends, users, and competitors.",
        "model": DASHSCOPE_MODEL_NAME,
        "temperature": 0.7,
    },
    "product_agent": {
        "name": "Product Design Agent",
        "description": "Generate product concepts and design directions.",
        "model": DASHSCOPE_MODEL_NAME,
        "temperature": 0.8,
    },
    "dev_agent": {
        "name": "Development Agent",
        "description": "Evaluate technical feasibility and implementation paths.",
        "model": DASHSCOPE_MODEL_NAME,
        "temperature": 0.6,
    },
    "summary_agent": {
        "name": "Summary Agent",
        "description": "Combine outputs into the final product proposal.",
        "model": DASHSCOPE_MODEL_NAME,
        "temperature": 0.5,
    },
}


WORKFLOW_CONFIG = {
    "max_iterations": 20,
    "enable_interrupts": True,
    "interrupt_points": ["analysis_interrupt", "planner_interrupt", "human_input_agent"],
}


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "liuliumei.log")


def build_llm(model: str | None = None, temperature: float | None = None) -> ChatOpenAI:
    """Create a ChatOpenAI client against the DashScope compatible endpoint."""

    if not DASHSCOPE_API_KEY:
        raise ValueError(
            "Missing DASHSCOPE_API_KEY. Please set it in your environment or .env file."
        )

    return ChatOpenAI(
        model=model or DASHSCOPE_MODEL_NAME,
        temperature=MODEL_TEMPERATURE if temperature is None else temperature,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        streaming=True,
    )


def build_run_config(
    thread_id: str,
    run_name: str = "liuliumei-product-workflow",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a LangGraph runnable config that is easy to inspect in LangSmith."""

    merged_tags = ["liuliumei", "langgraph", "dashscope"]
    if tags:
        merged_tags.extend(tags)

    merged_metadata: dict[str, Any] = {
        "llm_provider": "dashscope",
        "llm_model": DASHSCOPE_MODEL_NAME,
        "langsmith_enabled": LANGSMITH_TRACING,
    }
    if metadata:
        merged_metadata.update(metadata)

    return {
        "configurable": {"thread_id": thread_id},
        "run_name": run_name,
        "tags": merged_tags,
        "metadata": merged_metadata,
    }
