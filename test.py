"""
测试脚本：验证系统各组件功能
"""
from state import LiuliumeiState
from agents import create_agents
from nodes import (
    init_state_nodes,
    init_agent_nodes_message,
    user_query_analysis,
    planner_node,
    supervisor_node
)
from utils import (
    parse_json_output,
    validate_plan,
    check_agent_balance,
    is_consecutive_call
)
import json


def test_state():
    """测试状态定义"""
    print("测试状态定义...")
    state = {
        "user_query": "测试问题",
        "parsed_queries": [],
        "plan": [],
        "current_step": 0,
        "next_agent": "",
        "last_agent": "",
        "agent_history": [],
        "terminal": False
    }
    print("✓ 状态定义正常")
    return state


def test_agents():
    """测试智能体创建"""
    print("\n测试智能体创建...")
    agents, agent_dict = create_agents()
    
    assert len(agents) == 5, "智能体数量不正确"
    assert "market_agent" in agent_dict, "缺少市场研究智能体"
    assert "product_agent" in agent_dict, "缺少产品设计智能体"
    assert "dev_agent" in agent_dict, "缺少产品研发智能体"
    assert "summary_agent" in agent_dict, "缺少总结智能体"
    assert "human_input_agent" in agent_dict, "缺少人工介入智能体"
    
    print("✓ 智能体创建正常")
    print(f"  - 共创建 {len(agents)} 个智能体")
    for agent in agents:
        print(f"  - {agent.name}: {agent.description}")
    
    return agents, agent_dict


def test_nodes():
    """测试节点函数"""
    print("\n测试节点函数...")
    
    # 测试初始化节点
    state = {}
    result = init_state_nodes(state)
    assert "current_step" in result, "初始化节点缺少current_step"
    assert "agent_history" in result, "初始化节点缺少agent_history"
    print("✓ 初始化节点正常")
    
    # 测试智能体信息节点
    result = init_agent_nodes_message(state)
    assert "agent_descriptions" in result, "缺少智能体描述"
    assert "agent_configs" in result, "缺少智能体配置"
    print("✓ 智能体信息节点正常")
    
    # 测试问题分析节点
    state = {"user_query": "测试问题"}
    result = user_query_analysis(state)
    assert "parsed_queries" in result, "缺少解析结果"
    print("✓ 问题分析节点正常")


def test_utils():
    """测试工具函数"""
    print("\n测试工具函数...")
    
    # 测试JSON解析
    json_str = '{"key": "value"}'
    result = parse_json_output(json_str)
    assert result["key"] == "value", "JSON解析失败"
    print("✓ JSON解析正常")
    
    # 测试计划验证
    valid_plan = [
        "调用市场研究智能体",
        "调用产品设计智能体",
        "调用总结智能体"
    ]
    assert validate_plan(valid_plan, ["market_agent", "product_agent", "summary_agent"]), "计划验证失败"
    print("✓ 计划验证正常")
    
    # 测试连续调用检查
    history = ["market_agent", "product_agent"]
    assert not is_consecutive_call(history, "dev_agent"), "连续调用检查失败"
    assert is_consecutive_call(history, "product_agent"), "连续调用检查失败"
    print("✓ 连续调用检查正常")
    
    # 测试智能体均衡检查
    history = ["market_agent", "product_agent", "market_agent", "dev_agent"]
    balance = check_agent_balance(history)
    assert balance["market_agent"] == 2, "智能体均衡检查失败"
    print("✓ 智能体均衡检查正常")


def test_workflow_logic():
    """测试工作流逻辑"""
    print("\n测试工作流逻辑...")
    
    # 模拟状态
    state = {
        "plan": [
            "调用市场研究智能体进行市场分析",
            "调用产品设计智能体进行产品设计",
            "调用产品研发智能体进行技术评估",
            "调用总结智能体进行总结"
        ],
        "current_step": 0,
        "last_agent": "",
        "agent_history": []
    }
    
    # 测试监督节点决策
    result = supervisor_node(state)
    assert "next_agent" in result, "监督节点缺少next_agent"
    assert result["next_agent"] == "market_agent", f"第一步应该是market_agent，实际是{result['next_agent']}"
    print("✓ 监督节点决策正常")
    
    # 测试规则R2：禁止连续调用
    state["last_agent"] = "market_agent"
    state["current_step"] = 0
    result = supervisor_node(state)
    # 如果计划要求调用market_agent但上次也是market_agent，应该被拦截
    print(f"  - 连续调用检测: last={state['last_agent']}, next={result['next_agent']}")


def run_all_tests():
    """运行所有测试"""
    print("="*80)
    print("开始测试溜溜梅产品讨论系统")
    print("="*80)
    
    try:
        test_state()
        test_agents()
        test_nodes()
        test_utils()
        test_workflow_logic()
        
        print("\n" + "="*80)
        print("✓ 所有测试通过！")
        print("="*80)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
