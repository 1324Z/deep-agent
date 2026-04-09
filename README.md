# 项目启动文档

## 项目描述

本项目是一个基于 LangGraph 的多智能体协作产品策划系统，面向“六溜梅”相关产品讨论场景，能够围绕用户问题自动完成需求解析、知识检索、任务规划、市场研究、产品设计、技术评估、总结输出与报告生成。系统会把多个智能体的处理过程串联成一条完整工作流，并以流式方式在前端展示最终结论与中间阶段结果。

## 功能概述

- 需求解析：对用户输入问题进行拆解和结构化处理。
- 知识检索：结合本地知识库补充上下文信息。
- 任务规划：自动生成多智能体执行顺序与计划。
- 多智能体协作：分别完成市场研究、产品设计、技术评估与最终总结。
- 流式展示：前端可查看总结输出、阶段进度和执行日志。
- 报告导出：支持生成并下载 PDF 报告。

## 技术栈与架构

项目不是“前端 + 单一后端”，而是以下 3 个进程协同运行：

1. LangGraph 主服务
   负责核心工作流编排、状态流转和智能体调用。
2. `server` 目录中的 Node BFF
   负责对接 LangGraph，并向前端提供业务接口与流式输出。
3. `frontend` 目录中的 React + Vite 前端
   负责展示最终回答、阶段过程和报告下载入口。

你可以把它理解成：

- 真正的 AI 工作流后端：`langgraph dev`
- 给前端用的业务接口层：`server`
- 页面层：`frontend`

## 启动顺序

按当前代码，建议严格按照下面顺序启动。

### 终端 1：根目录启动 LangGraph

```powershell
conda activate agent
python -m pip install -r requirements.txt
langgraph dev
```

说明：

- LangGraph 默认地址是 `http://127.0.0.1:2024`
- 图 ID 是 `liuliumei_workflow`
- 这部分可以在 `LANGGRAPH_DEV.md` 和 `server/src/index.js` 中对照确认

### 终端 2：启动 BFF

```powershell
cd server
npm install
npm run dev
```

说明：

- `server` 默认监听 `http://127.0.0.1:3001`
- 它会代理到 LangGraph 的 `http://127.0.0.1:2024`
- 如果 LangGraph 地址不是默认值，可以先设置环境变量再启动：

```powershell
$env:LANGGRAPH_BASE_URL="http://127.0.0.1:2024"
$env:LANGGRAPH_ASSISTANT_ID="liuliumei_workflow"
npm run dev
```

### 终端 3：启动前端

```powershell
cd frontend
npm install
npm run dev
```

说明：

- 前端默认运行在 `http://127.0.0.1:5180`
- Vite 已经把 `/api` 代理到 `http://127.0.0.1:3001`
- 对应配置文件是 `frontend/vite.config.ts`

## 访问地址

- LangGraph：`http://127.0.0.1:2024`
- BFF：`http://127.0.0.1:3001`
- Frontend：`http://127.0.0.1:5180`



前端页面：
<img width="3183" height="1704" alt="image" src="https://github.com/user-attachments/assets/58b3eb20-0df7-4b48-9a0c-fae4e8961ec6" />

智能体工作流页面：
<img width="1107" height="863" alt="image" src="https://github.com/user-attachments/assets/45e025ca-99e5-46eb-8379-c539fcacbefa" />

