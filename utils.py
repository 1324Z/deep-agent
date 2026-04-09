"""
工具函数集合
"""
import json
from typing import Dict, Any, List


def parse_json_output(content: str) -> Dict:
    """
    解析JSON输出，处理可能的格式错误
    
    Args:
        content: 原始输出内容
        
    Returns:
        解析后的字典
    """
    try:
        # 尝试直接解析
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试提取JSON部分
        try:
            # 移除markdown代码块标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except:
            # 返回原始内容
            return {"原始输出": content}


def format_agent_output(agent_name: str, output: Dict) -> str:
    """
    格式化智能体输出
    
    Args:
        agent_name: 智能体名称
        output: 输出字典
        
    Returns:
        格式化后的字符串
    """
    lines = [f"\n{'='*80}"]
    lines.append(f"【{agent_name}】输出结果")
    lines.append('='*80)
    
    for key, value in output.items():
        lines.append(f"\n{key}:")
        lines.append("-" * 40)
        lines.append(str(value))
    
    lines.append('='*80 + '\n')
    return '\n'.join(lines)


def extract_keywords(text: str, max_keywords: int = 6) -> List[str]:
    """
    从文本中提取关键词（简单实现）
    
    Args:
        text: 输入文本
        max_keywords: 最大关键词数量
        
    Returns:
        关键词列表
    """
    # 这里可以使用更复杂的NLP方法
    # 简单实现：分词并过滤
    words = text.split()
    
    # 过滤停用词（简化版）
    stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    
    keywords = [w for w in words if w not in stop_words and len(w) > 1]
    
    return keywords[:max_keywords]


def validate_plan(plan: List[str], agent_names: List[str]) -> bool:
    """
    验证计划的合理性
    
    Args:
        plan: 执行计划列表
        agent_names: 可用的智能体名称列表
        
    Returns:
        是否合理
    """
    if not plan:
        return False
    
    # 检查是否包含总结智能体
    has_summary = any("总结" in step or "summary" in step.lower() for step in plan)
    
    if not has_summary:
        return False
    
    # 检查是否有连续重复的智能体
    last_agent = None
    for step in plan:
        current_agent = None
        for agent in agent_names:
            if agent in step or agent.replace("_agent", "") in step:
                current_agent = agent
                break
        
        if current_agent and current_agent == last_agent:
            return False
        
        last_agent = current_agent
    
    return True


def merge_outputs(market_output: Dict, product_output: Dict, dev_output: Dict) -> Dict:
    """
    合并各智能体的输出
    
    Args:
        market_output: 市场研究输出
        product_output: 产品设计输出
        dev_output: 技术评估输出
        
    Returns:
        合并后的字典
    """
    merged = {
        "市场研究": market_output or {},
        "产品设计": product_output or {},
        "技术评估": dev_output or {}
    }
    
    return merged


def format_summary_for_display(summary: str) -> str:
    """
    格式化总结输出用于显示
    
    Args:
        summary: 原始总结文本
        
    Returns:
        格式化后的文本
    """
    lines = ["\n" + "="*80]
    lines.append("【最终产品方案总结】")
    lines.append("="*80 + "\n")
    lines.append(summary)
    lines.append("\n" + "="*80)
    
    return '\n'.join(lines)


def create_agent_description(agents: List[Any]) -> str:
    """
    创建智能体描述文本
    
    Args:
        agents: 智能体列表
        
    Returns:
        描述文本
    """
    descriptions = []
    for i, agent in enumerate(agents, 1):
        if hasattr(agent, 'name') and hasattr(agent, 'description'):
            descriptions.append(f"{i}. {agent.name} - {agent.description}")
    
    return '\n'.join(descriptions)


def check_agent_balance(agent_history: List[str]) -> Dict[str, int]:
    """
    检查智能体调用是否均衡
    
    Args:
        agent_history: 智能体调用历史
        
    Returns:
        各智能体的调用次数统计
    """
    from collections import Counter
    return dict(Counter(agent_history))


def is_consecutive_call(agent_history: List[str], agent_name: str) -> bool:
    """
    检查是否会造成连续调用同一智能体
    
    Args:
        agent_history: 智能体调用历史
        agent_name: 待调用的智能体名称
        
    Returns:
        是否连续调用
    """
    if not agent_history:
        return False
    
    return agent_history[-1] == agent_name
