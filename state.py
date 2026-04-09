import operator
from typing import Annotated, Dict, List, Optional

from langgraph.graph import MessagesState


class LiuliumeiState(MessagesState):
    """State definition for the product discussion workflow."""

    user_query: str
    parsed_queries: List[str]

    plan: List[str]
    current_step: int
    next_agent: str
    last_agent: str

    agent_history: Annotated[List[str], operator.add]
    agent_traces: Annotated[List[Dict], operator.add]

    market_output: Optional[Dict]
    dev_output: Optional[Dict]
    product_output: Optional[Dict]
    summary_output: Optional[str]
    report_url: str
    report_download_url: str
    report_markdown_url: str
    report_pdf_url: str

    human_feedback: str
    analysis_feedback: str
    planner_feedback: str
    summary_statement: str
    terminal: bool
    pending_interrupt: str

    agent_descriptions: str
    agent_configs: List[Dict]

    digit_view: str
    digit_reference: str
    relevant_contents: str
    retrieval_query: str
    retrieved_docs: List[Dict]
