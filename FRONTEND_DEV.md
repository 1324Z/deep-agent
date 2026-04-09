# 前端调试说明

这个项目现在增加了一套独立前端脚手架，用来把 `langgraph dev` 的处理过程展示在浏览器里。

## 启动顺序

### 1. 启动 LangGraph

在项目根目录执行：

```powershell
conda activate agent
langgraph dev
```

默认 LangGraph 本地服务地址是：

```text
http://127.0.0.1:2024
```

### 2. 启动 BFF 服务

新开一个终端：

```powershell
cd server
npm install
npm run dev
```

如果你的 LangGraph 服务不是 `127.0.0.1:2024`，可以这样改：

```powershell
$env:LANGGRAPH_BASE_URL="http://127.0.0.1:2024"
$env:LANGGRAPH_ASSISTANT_ID="liuliumei_workflow"
npm run dev
```

### 3. 启动前端

再开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5180
```

## 当前版本功能

- 输入问题并提交给 LangGraph 工作流
- 自动处理分析确认、计划确认和最终 `APPROVE`
- 阶段看板展示需求解析、检索、规划、路由和各 Agent 输出
- 活动流展示每一步的状态更新
- 展示 `summary_output` 和报告链接
- 展示 thread 和 graph 标识

## 下一步建议

- 如果要保留人工确认，可把 BFF 的自动续跑改成前端手动确认
- 如果要做答辩版本，可以再补历史会话列表和品牌化视觉

