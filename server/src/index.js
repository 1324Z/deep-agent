import http from "node:http";
import { randomUUID } from "node:crypto";

const PORT = Number(process.env.PORT || 3001);
const LANGGRAPH_BASE_URL = process.env.LANGGRAPH_BASE_URL || "http://127.0.0.1:2024";
const GRAPH_ID = process.env.LANGGRAPH_ASSISTANT_ID || "liuliumei_workflow";
const STREAM_MODE = ["updates"];
const MAX_AUTO_RESUMES = 6;
const PSEUDO_SUMMARY_CHAR_DELAY_MS = 45;
const PSEUDO_SUMMARY_SPACE_DELAY_MS = 25;
const PSEUDO_SUMMARY_PUNCTUATION_DELAY_MS = 110;
const PSEUDO_SUMMARY_NEWLINE_DELAY_MS = 160;

const NODE_STAGE_META = {
  user_query_analysis: { stage: "analysis", title: "需求解析" },
  analysis_interrupt: { stage: "analysis", title: "需求确认" },
  retrieve_context: { stage: "retrieval", title: "知识检索" },
  planner_node: { stage: "planning", title: "执行规划" },
  planner_interrupt: { stage: "planning", title: "计划确认" },
  supervisor_node: { stage: "routing", title: "路由决策" },
  market_agent: { stage: "market", title: "市场研究" },
  product_agent: { stage: "product", title: "产品设计" },
  dev_agent: { stage: "development", title: "技术评估" },
  summary_agent: { stage: "summary", title: "总结输出" },
  human_input_title: { stage: "feedback", title: "结果审阅" },
  human_input_agent: { stage: "feedback", title: "反馈处理" },
};

const NEXT_AGENT_STAGE = {
  market_agent: "market",
  product_agent: "product",
  dev_agent: "development",
  summary_agent: "summary",
  human_input_agent: "feedback",
};

const NEXT_AGENT_LABEL = {
  market_agent: "市场研究",
  product_agent: "产品设计",
  dev_agent: "技术评估",
  summary_agent: "总结输出",
  human_input_agent: "人工反馈",
  end: "结束",
};

const INTERRUPT_RESUME_VALUE = {
  analysis_interrupt: "OK",
  planner_interrupt: "OK",
  human_input_agent: "APPROVE",
};

function nowLabel() {
  return new Date().toLocaleTimeString("zh-CN");
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  });
  response.end(JSON.stringify(payload));
}

function clipText(value, maxLength = 180) {
  const text =
    typeof value === "string" ? value : value == null ? "" : JSON.stringify(value, null, 2);
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function createThread() {
  const response = await fetch(`${LANGGRAPH_BASE_URL}/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ metadata: { source: "frontend-ui" } }),
  });
  if (!response.ok) {
    throw new Error(`创建 thread 失败: ${response.status}`);
  }
  return response.json();
}

function getThreadId(thread) {
  return thread.thread_id ?? thread.threadId ?? thread.id ?? "";
}

function buildStreamBody(question, command) {
  const body = {
    assistant_id: GRAPH_ID,
    stream_mode: STREAM_MODE,
  };

  if (question) {
    body.input = { user_query: question };
  }
  if (command) {
    body.command = command;
  }

  return body;
}

function parseSseEvent(block) {
  const lines = block.split(/\r?\n/);
  let eventName = "";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  return {
    event: eventName,
    data: dataLines.join("\n"),
  };
}

async function consumeSse(body, onChunk) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.search(/\r?\n\r?\n/);
    while (separatorIndex !== -1) {
      const rawBlock = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + (buffer[separatorIndex] === "\r" ? 4 : 2));
      if (rawBlock.trim()) {
        await onChunk(parseSseEvent(rawBlock));
      }
      separatorIndex = buffer.search(/\r?\n\r?\n/);
    }
  }

  if (buffer.trim()) {
    await onChunk(parseSseEvent(buffer));
  }
}

function normalizeStreamEvent(sseEvent) {
  if (!sseEvent.data) {
    return { mode: sseEvent.event || "message", payload: null };
  }

  const parsed = safeJsonParse(sseEvent.data);
  if (Array.isArray(parsed) && parsed.length === 2 && typeof parsed[0] === "string") {
    return { mode: parsed[0], payload: parsed[1] };
  }

  if (parsed && typeof parsed === "object" && typeof parsed.type === "string" && "data" in parsed) {
    return { mode: parsed.type, payload: parsed.data };
  }

  return {
    mode: sseEvent.event || "message",
    payload: parsed ?? sseEvent.data,
  };
}

function extractInterrupts(payload) {
  if (!payload || typeof payload !== "object") {
    return [];
  }
  if (Array.isArray(payload.__interrupt__)) {
    return payload.__interrupt__;
  }
  if (payload.data && typeof payload.data === "object" && Array.isArray(payload.data.__interrupt__)) {
    return payload.data.__interrupt__;
  }
  return [];
}

function normalizeInterrupt(interrupt) {
  const value = interrupt?.value ?? interrupt ?? {};
  const kind = typeof value === "object" && value ? value.kind ?? "" : "";
  const title = NODE_STAGE_META[kind]?.title || "流程中断";
  const stage = NODE_STAGE_META[kind]?.stage || "feedback";
  const resumeValue = INTERRUPT_RESUME_VALUE[kind] ?? "OK";

  return {
    kind,
    title,
    stage,
    resumeValue,
  };
}

function summarizeOutput(value, fallback) {
  if (value == null) {
    return fallback;
  }
  if (typeof value === "string") {
    return clipText(value, 160);
  }
  const keys = Object.keys(value);
  if (!keys.length) {
    return fallback;
  }
  return `已生成 ${keys.slice(0, 3).join(" / ")}${keys.length > 3 ? " 等字段" : ""}`;
}

function getPseudoSummaryDelay(currentChar) {
  if (currentChar === "\n") {
    return PSEUDO_SUMMARY_NEWLINE_DELAY_MS;
  }

  if (currentChar === " " || currentChar === "\t") {
    return PSEUDO_SUMMARY_SPACE_DELAY_MS;
  }

  if ("，。！？；：,.!?;:".includes(currentChar)) {
    return PSEUDO_SUMMARY_PUNCTUATION_DELAY_MS;
  }

  return PSEUDO_SUMMARY_CHAR_DELAY_MS;
}

async function emitPseudoSummary(summaryOutput, onEvent) {
  const detail =
    typeof summaryOutput === "string"
      ? summaryOutput
      : summaryOutput == null
        ? ""
        : JSON.stringify(summaryOutput, null, 2);
  const chars = Array.from(detail);

  if (!chars.length) {
    onEvent({
      kind: "summary",
      title: "最终总结",
      detail,
      timestamp: nowLabel(),
      raw: summaryOutput,
    });
    return;
  }

  let currentDetail = "";
  for (let index = 0; index < chars.length; index += 1) {
    currentDetail += chars[index];
    onEvent({
      kind: "summary",
      title: "最终总结",
      detail: currentDetail,
      timestamp: nowLabel(),
      raw: summaryOutput,
    });

    if (index < chars.length - 1) {
      await sleep(getPseudoSummaryDelay(chars[index]));
    }
  }
}

function buildStageDetail(nodeName, delta) {
  switch (nodeName) {
    case "user_query_analysis":
      return `解析需求 ${Array.isArray(delta.parsed_queries) ? delta.parsed_queries.length : 0} 条`;
    case "analysis_interrupt":
      return "已自动确认需求解析，可继续后续流程";
    case "retrieve_context":
      return `知识库命中 ${Array.isArray(delta.retrieved_docs) ? delta.retrieved_docs.length : 0} 条内容`;
    case "planner_node":
      return `生成 ${Array.isArray(delta.plan) ? delta.plan.length : 0} 步执行计划`;
    case "planner_interrupt":
      return "已自动确认执行计划";
    case "supervisor_node":
      return `下一步：${NEXT_AGENT_LABEL[delta.next_agent] || delta.next_agent || "待定"}`;
    case "market_agent":
      return summarizeOutput(delta.market_output, "已完成市场研究分析");
    case "product_agent":
      return summarizeOutput(delta.product_output, "已产出产品设计方案");
    case "dev_agent":
      return summarizeOutput(delta.dev_output, "已完成技术可行性评估");
    case "summary_agent":
      return clipText(delta.summary_output || "已生成最终总结", 160);
    case "human_input_title":
      return "总结结果准备完成，等待最终确认";
    case "human_input_agent":
      return delta.terminal ? "演示模式已自动 APPROVE，流程收尾" : "收到反馈，准备继续迭代";
    default:
      return clipText(delta, 160);
  }
}

function extractStatePatch(delta) {
  const patch = {};

  if ("user_query" in delta) patch.userQuery = delta.user_query;
  if ("parsed_queries" in delta) patch.parsedQueries = delta.parsed_queries;
  if ("plan" in delta) patch.plan = delta.plan;
  if ("next_agent" in delta) patch.nextAgent = delta.next_agent;
  if ("terminal" in delta) patch.terminal = Boolean(delta.terminal);
  if ("market_output" in delta) patch.marketOutput = delta.market_output;
  if ("product_output" in delta) patch.productOutput = delta.product_output;
  if ("dev_output" in delta) patch.devOutput = delta.dev_output;
  if ("report_url" in delta) patch.reportUrl = delta.report_url;
  if ("report_download_url" in delta) patch.reportDownloadUrl = delta.report_download_url;
  if ("report_pdf_url" in delta) patch.reportPdfUrl = delta.report_pdf_url;
  if ("retrieved_docs" in delta) {
    patch.retrievedDocsCount = Array.isArray(delta.retrieved_docs) ? delta.retrieved_docs.length : 0;
  }

  return patch;
}

async function processUpdatePayload(payload, onEvent) {
  if (!payload || typeof payload !== "object") {
    return;
  }

  for (const [nodeName, delta] of Object.entries(payload)) {
    if (nodeName === "__interrupt__" || !delta || typeof delta !== "object") {
      continue;
    }

    const meta = NODE_STAGE_META[nodeName] || {
      stage: "routing",
      title: nodeName,
    };
    const timestamp = nowLabel();

    onEvent({
      kind: "stage",
      stage: meta.stage,
      node: nodeName,
      status: "done",
      title: meta.title,
      detail: buildStageDetail(nodeName, delta),
      timestamp,
      raw: delta,
    });

    if (delta.summary_output) {
      await emitPseudoSummary(delta.summary_output, onEvent);
    }

    const patch = extractStatePatch(delta);
    if (Object.keys(patch).length > 0) {
      onEvent({
        kind: "state",
        patch,
        timestamp,
      });
    }

    if (nodeName === "supervisor_node" && delta.next_agent && NEXT_AGENT_STAGE[delta.next_agent]) {
      onEvent({
        kind: "stage",
        stage: NEXT_AGENT_STAGE[delta.next_agent],
        node: delta.next_agent,
        status: "running",
        title: NEXT_AGENT_LABEL[delta.next_agent] || delta.next_agent,
        detail: `已被调度，准备执行 ${NEXT_AGENT_LABEL[delta.next_agent] || delta.next_agent}`,
        timestamp,
      });
    }
  }
}

async function streamPass(threadId, question, command, onEvent) {
  const response = await fetch(`${LANGGRAPH_BASE_URL}/threads/${threadId}/runs/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildStreamBody(question, command)),
  });

  if (!response.ok || !response.body) {
    throw new Error(`工作流流式调用失败: ${response.status}`);
  }

  let interrupts = [];

  await consumeSse(response.body, async (sseEvent) => {
    if (!sseEvent.data || sseEvent.data === "[DONE]") {
      return;
    }

    const { mode, payload } = normalizeStreamEvent(sseEvent);
    const foundInterrupts = extractInterrupts(payload);
    if (foundInterrupts.length) {
      interrupts = foundInterrupts;
      return;
    }

    if (mode === "updates") {
      await processUpdatePayload(payload, onEvent);
      return;
    }

    if (mode === "metadata") {
      return;
    }

    onEvent({
      kind: "payload",
      title: `${mode} 事件`,
      detail: clipText(payload, 220),
      timestamp: nowLabel(),
      raw: payload,
    });
  });

  return interrupts;
}

async function streamRun(question, onEvent) {
  const thread = await createThread();
  const threadId = getThreadId(thread);

  onEvent({
    kind: "session",
    session: {
      threadId,
      assistantId: GRAPH_ID,
      userQuery: question,
    },
  });

  onEvent({
    kind: "status",
    title: "工作流已启动",
    detail: "已创建 LangGraph 线程，开始执行需求解析。",
    timestamp: nowLabel(),
  });

  let questionInput = question;
  let command = null;

  for (let index = 0; index < MAX_AUTO_RESUMES; index += 1) {
    const interrupts = await streamPass(threadId, questionInput, command, onEvent);
    if (!interrupts.length) {
      onEvent({
        kind: "status",
        title: "工作流完成",
        detail: "所有阶段执行结束，前端已收到完整结果。",
        timestamp: nowLabel(),
      });
      return;
    }

    const interruptInfo = normalizeInterrupt(interrupts[0]);
    onEvent({
      kind: "stage",
      stage: interruptInfo.stage,
      node: interruptInfo.kind,
      status: "waiting",
      title: interruptInfo.title,
      detail: `检测到人工确认节点，演示模式自动提交 ${JSON.stringify(interruptInfo.resumeValue)} 继续执行。`,
      timestamp: nowLabel(),
    });

    questionInput = null;
    command = { resume: interruptInfo.resumeValue };
  }

  throw new Error("自动续跑次数过多，请检查工作流是否重复中断。");
}

const server = http.createServer((request, response) => {
  if (!request.url) {
    sendJson(response, 404, { error: "Not found" });
    return;
  }

  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    });
    response.end();
    return;
  }

  if (request.method === "GET" && request.url === "/api/health") {
    sendJson(response, 200, {
      ok: true,
      langgraphBaseUrl: LANGGRAPH_BASE_URL,
      assistantId: GRAPH_ID,
    });
    return;
  }

  if (request.method === "POST" && request.url === "/api/chat/stream") {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });

    request.on("end", async () => {
      try {
        const parsed = JSON.parse(body || "{}");
        const question = String(parsed.question || "").trim();
        if (!question) {
          sendJson(response, 400, { error: "question 不能为空" });
          return;
        }

        response.writeHead(200, {
          "Content-Type": "application/x-ndjson; charset=utf-8",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
          "Access-Control-Allow-Origin": "*",
        });

        const onEvent = (payload) => {
          response.write(`${JSON.stringify(payload)}\n`);
        };

        await streamRun(question, onEvent);
        response.end();
      } catch (error) {
        const detail = error instanceof Error ? error.message : "未知错误";
        if (!response.headersSent) {
          sendJson(response, 500, { error: detail });
          return;
        }
        response.write(
          `${JSON.stringify({
            id: randomUUID(),
            kind: "error",
            title: "服务端错误",
            detail,
            timestamp: nowLabel(),
          })}\n`,
        );
        response.end();
      }
    });
    return;
  }

  sendJson(response, 404, { error: "Not found" });
});

server.listen(PORT, () => {
  console.log(`BFF server running at http://127.0.0.1:${PORT}`);
  console.log(`Proxying LangGraph server: ${LANGGRAPH_BASE_URL}`);
  console.log(`Assistant graph id: ${GRAPH_ID}`);
});
