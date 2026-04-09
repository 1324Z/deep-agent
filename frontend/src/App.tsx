import {
  type CSSProperties,
  type FormEvent,
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import { asStringList, clipText, formatJson, nowLabel } from "./lib.format";
import {
  type SessionState,
  type StageCard,
  type StageKey,
  type StageStatus,
  type StreamPayload,
  type TimelineEvent,
} from "./types";

const DEFAULT_QUESTION =
  "六溜梅计划推出一款面向 Z 世代的青梅类休闲零食，请基于当前市场趋势、用户需求和技术可行性提出 3 个创新产品方向。";

const STAGE_BLUEPRINTS = [
  { key: "analysis", title: "需求解析", caption: "拆解问题目标", accent: "#4f6bff" },
  { key: "retrieval", title: "知识检索", caption: "提取知识上下文", accent: "#22a37a" },
  { key: "planning", title: "执行规划", caption: "生成任务计划", accent: "#7b5cff" },
  { key: "routing", title: "路由决策", caption: "选择执行智能体", accent: "#64748b" },
  { key: "market", title: "市场研究", caption: "输出市场洞察", accent: "#f97316" },
  { key: "product", title: "产品设计", caption: "形成产品方案", accent: "#ec4899" },
  { key: "development", title: "技术评估", caption: "分析技术可行性", accent: "#0ea5e9" },
  { key: "summary", title: "总结输出", caption: "汇总最终结论", accent: "#22c55e" },
  { key: "feedback", title: "反馈确认", caption: "处理中断与确认", accent: "#eab308" },
] satisfies Array<{
  key: StageKey;
  title: string;
  caption: string;
  accent: string;
}>;

const STAGE_AGENT_NAMES: Record<StageKey, string> = {
  analysis: "需求解析智能体",
  retrieval: "知识检索节点",
  planning: "规划智能体",
  routing: "监督路由节点",
  market: "市场研究智能体",
  product: "产品设计智能体",
  development: "技术评估智能体",
  summary: "总结输出智能体",
  feedback: "反馈确认节点",
};

type ConversationRecord = {
  id: string;
  title: string;
  question: string;
  answer: string;
  updatedAt: string;
  createdAtMs: number;
  stages: Record<StageKey, StageCard>;
  timeline: TimelineEvent[];
  session: SessionState | null;
  finalAnswer: string;
  elapsedSeconds: number;
  isComplete: boolean;
};

function createInitialStages(): Record<StageKey, StageCard> {
  return Object.fromEntries(
    STAGE_BLUEPRINTS.map((item) => [
      item.key,
      {
        ...item,
        status: "idle",
        detail: "等待执行",
        updatedAt: "--",
      },
    ]),
  ) as Record<StageKey, StageCard>;
}

function cloneStages(source: Record<StageKey, StageCard>): Record<StageKey, StageCard> {
  return Object.fromEntries(
    Object.entries(source).map(([key, value]) => [key, { ...value }]),
  ) as Record<StageKey, StageCard>;
}

function statusLabel(status: StageStatus): string {
  if (status === "running") return "执行中";
  if (status === "done") return "已完成";
  if (status === "waiting") return "待确认";
  if (status === "error") return "异常";
  return "未开始";
}

function mergeSessionState(
  current: SessionState | null,
  patch: Partial<SessionState>,
): SessionState | null {
  if (!current && !patch.threadId && !patch.assistantId) {
    return null;
  }

  return {
    threadId: current?.threadId ?? patch.threadId ?? "",
    assistantId: current?.assistantId ?? patch.assistantId ?? "",
    ...current,
    ...patch,
  };
}

function getConversationTitle(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "新对话";
  return clipText(trimmed.replace(/\s+/g, " "), 22);
}

function formatDuration(seconds: number): string {
  if (seconds <= 0) return "0 秒";
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes} 分 ${remaining} 秒`;
}

function historyBucketLabel(createdAtMs: number): string {
  const ageDays = Math.floor((Date.now() - createdAtMs) / (1000 * 60 * 60 * 24));
  if (ageDays <= 0) return "今天";
  if (ageDays <= 7) return "7 天内";
  if (ageDays <= 30) return "30 天内";
  return "更早";
}

function formatHistoryTime(createdAtMs: number): string {
  return new Date(createdAtMs).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function splitParagraphs(text: string): string[] {
  if (!text) return [];
  return text
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter((p) => {
      if (!p) return false;
      // 过滤掉包含报告链接的原始文本行，避免界面重复
      const reportKeywords = ["报告链接", "在线预览", "下载 HTML", "/reports/"];
      if (reportKeywords.some((key) => p.includes(key))) {
        return false;
      }
      return true;
    });
}

function getStageSnapshot(
  stageKey: StageKey,
  context: {
    session: SessionState | null;
    parsedQueries: string[];
    plan: string[];
    finalAnswer: string;
    fallback: string;
  },
  maxLength = 180,
): string {
  if (stageKey === "analysis") {
    return clipText(context.parsedQueries.join("；") || context.fallback, maxLength);
  }

  if (stageKey === "retrieval") {
    if (context.session?.retrievedDocsCount != null) {
      return `已检索 ${context.session.retrievedDocsCount} 条相关资料，正在压缩为后续分析上下文。`;
    }
    return clipText(context.fallback || "正在检索知识上下文。", maxLength);
  }

  if (stageKey === "planning") {
    return clipText(context.plan.join("；") || context.fallback, maxLength);
  }

  if (stageKey === "routing") {
    return clipText(
      context.session?.nextAgent
        ? `下一步由 ${context.session.nextAgent} 接管处理。`
        : context.fallback || "正在决定交给哪个智能体继续执行。",
      maxLength,
    );
  }

  if (stageKey === "market") {
    return clipText(formatJson(context.session?.marketOutput) || context.fallback, maxLength);
  }

  if (stageKey === "product") {
    return clipText(formatJson(context.session?.productOutput) || context.fallback, maxLength);
  }

  if (stageKey === "development") {
    return clipText(formatJson(context.session?.devOutput) || context.fallback, maxLength);
  }

  if (stageKey === "summary") {
    return clipText(context.finalAnswer || context.session?.summary || context.fallback, maxLength);
  }

  return clipText(context.fallback || "等待执行。", maxLength);
}

function App() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [stages, setStages] = useState<Record<StageKey, StageCard>>(createInitialStages);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [session, setSession] = useState<SessionState | null>(null);
  const [finalAnswer, setFinalAnswer] = useState("");
  const [serviceState, setServiceState] = useState("连接中");
  const [isThinkingOpen, setIsThinkingOpen] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [historyRecords, setHistoryRecords] = useState<ConversationRecord[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isBrowsingHistory, setIsBrowsingHistory] = useState(false);
  const deferredTimeline = useDeferredValue(timeline);

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const response = await fetch("/api/health");
        if (!response.ok) {
          throw new Error(String(response.status));
        }

        const payload = (await response.json()) as {
          assistantId?: string;
          langgraphBaseUrl?: string;
        };

        if (!cancelled) {
          setServiceState(
            `BFF 已连接 · ${payload.assistantId || "unknown"} · ${payload.langgraphBaseUrl || "no-url"}`,
          );
        }
      } catch {
        if (!cancelled) {
          setServiceState("未检测到 BFF 服务，请先启动 server");
        }
      }
    }

    void checkHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isRunning || runStartedAt == null) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setElapsedSeconds(Math.max(1, Math.floor((Date.now() - runStartedAt) / 1000)));
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isRunning, runStartedAt]);

  const stageList = useMemo(() => STAGE_BLUEPRINTS.map((item) => stages[item.key]), [stages]);
  const hasTimeline = deferredTimeline.length > 0;
  const parsedQueries = asStringList(session?.parsedQueries);
  const plan = asStringList(session?.plan);

  const currentStage = useMemo(() => {
    const runningStage = stageList.find((item) => item.status === "running");
    if (runningStage) {
      return runningStage;
    }

    const recentEvent = [...deferredTimeline].reverse().find((item) => item.stage);
    if (recentEvent?.stage) {
      return stages[recentEvent.stage];
    }

    const latestResolvedStage = [...stageList]
      .reverse()
      .find((item) => item.status === "done" || item.status === "waiting" || item.status === "error");

    return latestResolvedStage ?? stageList[0];
  }, [deferredTimeline, stageList, stages]);

  const currentAgentName = STAGE_AGENT_NAMES[currentStage.key];
  const currentAgentPreview = useMemo(
    () =>
      getStageSnapshot(
        currentStage.key,
        {
          session,
          parsedQueries,
          plan,
          finalAnswer,
          fallback: currentStage.detail,
        },
        420,
      ),
    [currentStage, finalAnswer, parsedQueries, plan, session],
  );

  const visibleStages = useMemo(
    () => stageList.filter((item) => item.status !== "idle" || item.key === currentStage.key),
    [currentStage.key, stageList],
  );

  const detailCards = useMemo(() => {
    const cards: Array<{ title: string; subtitle: string; content: string }> = [];

    if (parsedQueries.length) {
      cards.push({
        title: "需求解析",
        subtitle: "Parsed Query",
        content: parsedQueries.join("\n"),
      });
    }

    if (plan.length) {
      cards.push({
        title: "执行计划",
        subtitle: "Plan",
        content: plan.join("\n"),
      });
    }

    if (session?.marketOutput) {
      cards.push({
        title: "市场研究",
        subtitle: "Market Agent",
        content: clipText(formatJson(session.marketOutput), 360),
      });
    }

    if (session?.productOutput) {
      cards.push({
        title: "产品设计",
        subtitle: "Product Agent",
        content: clipText(formatJson(session.productOutput), 360),
      });
    }

    if (session?.devOutput) {
      cards.push({
        title: "技术评估",
        subtitle: "Development Agent",
        content: clipText(formatJson(session.devOutput), 360),
      });
    }

    return cards;
  }, [parsedQueries, plan, session]);

  const recentTimeline = useMemo(() => [...deferredTimeline].slice(-6).reverse(), [deferredTimeline]);

  const answerText = useMemo(() => {
    if (finalAnswer) {
      return finalAnswer;
    }

    if (submittedQuestion && isRunning) {
      return "我正在整合多智能体的分析结果，稍后会把最终答案整理在这里。展开上方的“深度思考”可以查看每个智能体当前做到哪一步。";
    }

    if (submittedQuestion) {
      return "这一轮已经结束，但还没有拿到完整的总结输出。你可以展开“深度思考”查看中间结果。";
    }

    return "你好，我可以把你的问题交给多个智能体协同处理，并把每一步过程收进“深度思考”里。你既可以直接看最终答案，也可以展开查看内部过程。";
  }, [finalAnswer, isRunning, submittedQuestion]);

  const answerParagraphs = useMemo(() => splitParagraphs(answerText), [answerText]);
  const thinkingLabel = hasTimeline
    ? `${isRunning ? "深度思考中" : "已思考"}（用时 ${formatDuration(elapsedSeconds)}）`
    : "深度思考";
  const sessionMeta = session
    ? `thread: ${session.threadId} · graph: ${session.assistantId}`
    : "thread 未创建";
  const currentConversationTitle = submittedQuestion ? getConversationTitle(submittedQuestion) : "新对话";
  const groupedHistory = useMemo(() => {
    const buckets = new Map<string, ConversationRecord[]>();

    for (const record of historyRecords) {
      const label = historyBucketLabel(record.createdAtMs);
      const current = buckets.get(label) ?? [];
      current.push(record);
      buckets.set(label, current);
    }

    return ["今天", "7 天内", "30 天内", "更早"]
      .map((label) => ({ label, items: buckets.get(label) ?? [] }))
      .filter((group) => group.items.length > 0);
  }, [historyRecords]);

  useEffect(() => {
    if (!activeConversationId || !submittedQuestion || isBrowsingHistory) {
      return;
    }

    const answerPreview = finalAnswer || (isRunning ? currentAgentPreview : "");

    setHistoryRecords((current) =>
      current.map((record) =>
        record.id === activeConversationId
          ? {
              ...record,
              title: getConversationTitle(submittedQuestion),
              question: record.question || submittedQuestion,
              answer: answerPreview || record.answer,
              updatedAt: nowLabel(),
              stages: cloneStages(stages),
              timeline: timeline.map((item) => ({ ...item })),
              session: session ? { ...session } : null,
              finalAnswer,
              elapsedSeconds,
              isComplete: !isRunning && Boolean(finalAnswer),
            }
          : record,
      ),
    );
  }, [
    activeConversationId,
    currentAgentPreview,
    elapsedSeconds,
    finalAnswer,
    isBrowsingHistory,
    isRunning,
    session,
    stages,
    submittedQuestion,
    timeline,
  ]);

  function appendTimeline(entry: TimelineEvent) {
    startTransition(() => {
      setTimeline((current) => [...current, entry]);
    });
  }

  function upsertSummaryTimeline(payload: StreamPayload) {
    const title = payload.title ?? "最终总结";
    const detail = payload.detail ?? "";
    const timestamp = payload.timestamp ?? nowLabel();

    startTransition(() => {
      setTimeline((current) => {
        let summaryIndex = -1;
        for (let index = current.length - 1; index >= 0; index -= 1) {
          if (current[index].stage === "summary" && current[index].title === title) {
            summaryIndex = index;
            break;
          }
        }

        const previousDetail = summaryIndex >= 0 ? current[summaryIndex].detail : "";
        const nextDetail = detail.length >= previousDetail.length ? detail : previousDetail;
        const nextEntry: TimelineEvent = {
          id: summaryIndex >= 0 ? current[summaryIndex].id : crypto.randomUUID(),
          type: "payload",
          title,
          detail: nextDetail,
          timestamp,
          stage: "summary",
          raw: payload.raw,
        };

        if (summaryIndex === -1) {
          return [...current, nextEntry];
        }

        return current.map((item, index) => (index === summaryIndex ? nextEntry : item));
      });
    });
  }

  function updateStage(payload: StreamPayload) {
    if (!payload.stage) return;

    startTransition(() => {
      setStages((current) => ({
        ...current,
        [payload.stage as StageKey]: {
          ...current[payload.stage as StageKey],
          status: (payload.status as StageStatus) || current[payload.stage as StageKey].status,
          detail: payload.detail || current[payload.stage as StageKey].detail,
          updatedAt: payload.timestamp || nowLabel(),
          node: payload.node || current[payload.stage as StageKey].node,
        },
      }));
    });
  }

  function handlePayload(payload: StreamPayload) {
    if (payload.kind === "session" && payload.session) {
      startTransition(() => {
        setSession(payload.session ?? null);
      });
      return;
    }

    if (payload.kind === "state" && payload.patch) {
      startTransition(() => {
        setSession((current) => mergeSessionState(current, payload.patch ?? {}));
      });
      return;
    }

    if (payload.kind === "summary") {
      startTransition(() => {
        setFinalAnswer((current) => {
          const nextDetail = payload.detail ?? "";
          return nextDetail.length >= current.length ? nextDetail : current;
        });
        setSession((current) => {
          const nextDetail = payload.detail ?? "";
          const currentSummary = current?.summary ?? "";
          const nextSummary = nextDetail.length >= currentSummary.length ? nextDetail : currentSummary;
          return mergeSessionState(current, { summary: nextSummary });
        });
      });
      upsertSummaryTimeline(payload); /*
        title: payload.title ?? "最终总结",
      */ return;
    }

    if (payload.kind === "stage") {
      updateStage(payload);
      appendTimeline({
        id: crypto.randomUUID(),
        type: payload.status === "error" ? "error" : "payload",
        title: payload.title ?? "阶段更新",
        detail: payload.detail ?? "",
        timestamp: payload.timestamp ?? nowLabel(),
        stage: payload.stage,
        raw: payload.raw,
      });
      return;
    }

    if (payload.kind === "error") {
      appendTimeline({
        id: crypto.randomUUID(),
        type: "error",
        title: payload.title ?? "运行失败",
        detail: payload.detail ?? "未知错误",
        timestamp: payload.timestamp ?? nowLabel(),
        raw: payload.raw,
      });
      return;
    }

    appendTimeline({
      id: crypto.randomUUID(),
      type: payload.kind === "message" ? "message" : "status",
      title: payload.title ?? "运行状态",
      detail: payload.detail ?? "",
      timestamp: payload.timestamp ?? nowLabel(),
      raw: payload.raw,
    });
  }

  function resetConversation() {
    if (isRunning) return;

    setActiveConversationId(null);
    setIsBrowsingHistory(false);
    setQuestion("");
    setSubmittedQuestion("");
    setStages(createInitialStages());
    setTimeline([]);
    setSession(null);
    setFinalAnswer("");
    setElapsedSeconds(0);
    setRunStartedAt(null);
    setIsThinkingOpen(false);
  }

  function openConversation(record: ConversationRecord) {
    if (isRunning) return;

    setActiveConversationId(record.id);
    setIsBrowsingHistory(true);
    setQuestion("");
    setSubmittedQuestion(record.question);
    setStages(cloneStages(record.stages));
    setTimeline(record.timeline.map((item) => ({ ...item })));
    setSession(record.session ? { ...record.session } : null);
    setFinalAnswer(record.finalAnswer);
    setElapsedSeconds(record.elapsedSeconds);
    setRunStartedAt(null);
    setIsThinkingOpen(false);
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    if (event) event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isRunning) return;

    const conversationId = crypto.randomUUID();
    const startedAt = Date.now();
    const initialStages = createInitialStages();

    setActiveConversationId(conversationId);
    setIsBrowsingHistory(false);
    setHistoryRecords((current) => [
      {
        id: conversationId,
        title: getConversationTitle(trimmed),
        question: trimmed,
        answer: "正在启动多智能体处理流程...",
        updatedAt: nowLabel(),
        createdAtMs: startedAt,
        stages: cloneStages(initialStages),
        timeline: [],
        session: null,
        finalAnswer: "",
        elapsedSeconds: 0,
        isComplete: false,
      },
      ...current,
    ]);

    setStages(initialStages);
    setTimeline([]);
    setSession(null);
    setFinalAnswer("");
    setSubmittedQuestion(trimmed);
    setElapsedSeconds(0);
    setRunStartedAt(startedAt);
    setIsRunning(true);
    setIsThinkingOpen(false);

    updateStage({
      kind: "stage",
      stage: "analysis",
      status: "running",
      title: "需求解析",
      detail: "已收到问题，准备开始拆解需求。",
      timestamp: nowLabel(),
    });
    appendTimeline({
      id: crypto.randomUUID(),
      type: "status",
      title: "问题已提交",
      detail: trimmed,
      timestamp: nowLabel(),
      stage: "analysis",
    });

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: trimmed }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let splitIndex = buffer.indexOf("\n");
        while (splitIndex !== -1) {
          const line = buffer.slice(0, splitIndex).trim();
          buffer = buffer.slice(splitIndex + 1);
          if (line) {
            handlePayload(JSON.parse(line) as StreamPayload);
          }
          splitIndex = buffer.indexOf("\n");
        }
      }

      if (buffer.trim()) {
        handlePayload(JSON.parse(buffer.trim()) as StreamPayload);
      }

      setQuestion("");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "未知错误";
      updateStage({
        kind: "stage",
        stage: "feedback",
        status: "error",
        title: "流程异常",
        detail,
        timestamp: nowLabel(),
      });
      appendTimeline({
        id: crypto.randomUUID(),
        type: "error",
        title: "运行失败",
        detail,
        timestamp: nowLabel(),
      });
    } finally {
      setElapsedSeconds(Math.max(1, Math.round((Date.now() - startedAt) / 1000)));
      setRunStartedAt(null);
      setIsRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M13 10V3L4 14H11V21L20 10H13Z" />
            </svg>
          </div>
          <h1>Deep Agent</h1>
          <span className="brand-tag">LangGraph</span>
        </div>

        <button className="new-chat-button" type="button" onClick={resetConversation} disabled={isRunning}>
          <span className="new-chat-plus">+</span>
          开启新对话
        </button>

        <section className="history-group">
          <div className="history-group-title">历史对话</div>
          <div className="history-list">
            {groupedHistory.length ? (
              groupedHistory.map((group) => (
                <section className="history-section" key={group.label}>
                  <div className="history-section-title">{group.label}</div>
                  <div className="history-section-items">
                    {group.items.map((record) => (
                      <button
                        className={`history-item ${record.id === activeConversationId ? "active" : ""}`}
                        key={record.id}
                        onClick={() => openConversation(record)}
                        type="button"
                        disabled={isRunning}
                        title={record.question}
                      >
                        <span className="history-item-main">
                          <span className="history-icon">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                          </span>
                          <span className="history-item-title">{clipText(record.question, 22)}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <div className="history-empty">
                历史问题会显示在这里。点击某个问题，才会进入对应对话查看完整回复。
              </div>
            )}
          </div>
        </section>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">CS</div>
            <span className="user-name">长安不起风</span>
          </div>
          <button className="sidebar-settings" type="button">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        </div>
        <div className="service-status-bar">
          <span className="status-dot" />
          <span>{serviceState}</span>
        </div>
      </aside>

      <div className="main-panel">
        <header className="chat-header">
          <div className="header-left">
            <div className="header-logo">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M13 10V3L4 14H11V21L20 10H13Z" />
              </svg>
            </div>
            <div className="header-title">Deep Agent</div>
            <span className="brand-tag">LangGraph</span>
          </div>
          <div className="header-right">
            <button className="chat-header-action" type="button" title="设置">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>
        </header>

        <main className="conversation-scroll">
          <div className="conversation-inner">
            {!submittedQuestion ? (
            <section className="landing">
              <div className="landing-badge">深度思考 + 多智能体协作</div>
              <h2>把最终答案和内部推理过程分开展示</h2>
              <p>
                输入问题后，主区域优先展示最终回答；每个智能体的处理过程、阶段输出和关键日志会被收进上方的“深度思考”面板，支持展开和收起。
              </p>
            </section>
          ) : null}

          {submittedQuestion ? (
            <div className="message-row user">
              <div className="question-bubble">{submittedQuestion}</div>
            </div>
          ) : null}

          {submittedQuestion ? (
            <section className="assistant-block">
              <button
                className={`thinking-pill ${isThinkingOpen ? "open" : ""}`}
                type="button"
                onClick={() => setIsThinkingOpen((current) => !current)}
              >
                <span className="thinking-dot" />
                <span className="thinking-text">{thinkingLabel}</span>
                <span className="thinking-divider">|</span>
                <span className="thinking-action">
                  {isThinkingOpen ? "收起执行过程" : "展开执行过程"}
                  <span className="thinking-arrow">›</span>
                </span>
              </button>

              {hasTimeline && isThinkingOpen ? (
                <div className="thinking-panel">
                  <div className="thinking-focus-card">
                    <div className="thinking-focus-head">
                      <div>
                        <div className="mini-kicker">当前智能体</div>
                        <h3>{currentAgentName}</h3>
                      </div>
                      <span className={`status-pill status-${currentStage.status}`}>
                        {currentStage.title} · {statusLabel(currentStage.status)}
                      </span>
                    </div>
                    <p>{currentAgentPreview}</p>
                    <div className="thinking-meta">{sessionMeta}</div>
                  </div>

                  <div className="thinking-stage-list">
                    {visibleStages.map((stage) => (
                      <article
                        className={`thinking-stage-card ${stage.key === currentStage.key ? "current" : ""}`}
                        key={stage.key}
                        style={{ "--stage-accent": stage.accent } as CSSProperties}
                      >
                        <div className="thinking-stage-head">
                          <div>
                            <strong>{stage.title}</strong>
                            <span>{STAGE_AGENT_NAMES[stage.key]}</span>
                          </div>
                          <span className={`status-pill status-${stage.status}`}>
                            {statusLabel(stage.status)}
                          </span>
                        </div>
                        <p>
                          {getStageSnapshot(
                            stage.key,
                            {
                              session,
                              parsedQueries,
                              plan,
                              finalAnswer,
                              fallback: stage.detail,
                            },
                            160,
                          )}
                        </p>
                      </article>
                    ))}
                  </div>

                  {detailCards.length ? (
                    <div className="detail-grid">
                      {detailCards.map((card) => (
                        <article className="detail-card" key={card.title}>
                          <div className="mini-kicker">{card.subtitle}</div>
                          <h4>{card.title}</h4>
                          <pre>{card.content}</pre>
                        </article>
                      ))}
                    </div>
                  ) : null}

                  {recentTimeline.length ? (
                    <div className="log-stack">
                      {recentTimeline.map((item) => (
                        <article className={`log-card type-${item.type}`} key={item.id}>
                          <div className="log-card-head">
                            <strong>{item.title}</strong>
                            <span>{item.timestamp}</span>
                          </div>
                          <pre>{item.detail}</pre>
                        </article>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <article className="answer-panel">
                <div className="answer-head">
                  <div>
                    <div className="mini-kicker">最终回答</div>
                    <h3>智能体回复</h3>
                  </div>
                  <div className="answer-actions">
                    <span className="ghost-pill">{currentAgentName}</span>
                    <span className="ghost-pill">{statusLabel(currentStage.status)}</span>
                  </div>
                </div>

                <div className="answer-content">
                  {answerParagraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>

                  {session?.reportPdfUrl ? (
                    <div className="answer-links">
                      <a href={session.reportPdfUrl} target="_blank" rel="noreferrer" className="pdf-download-btn">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '6px' }}>
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                          <line x1="12" y1="18" x2="12" y2="12" />
                          <polyline points="9 15 12 12 15 15" />
                        </svg>
                        下载 PDF 报告
                      </a>
                    </div>
                  ) : null}
              </article>
            </section>
          ) : null}
        </div>
      </main>

        <div className="composer-shell">
          <div className="composer-wrapper">
            <form className="composer-container" onSubmit={handleSubmit}>
              <textarea
                className="composer-input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder="给 Deep Agent 发送消息"
                rows={1}
              />
              <div className="composer-footer">
                <div className="composer-left">
                  <button 
                    className={`composer-chip ${isThinkingOpen ? "active" : ""}`} 
                    type="button"
                    onClick={() => setIsThinkingOpen(!isThinkingOpen)}
                  >
                    <span className="chip-icon">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 3" />
                      </svg>
                    </span>
                    深度思考
                  </button>
                  <button className="composer-chip" type="button">
                    <span className="chip-icon">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8" />
                        <path d="m21 21-4.3-4.3" />
                      </svg>
                    </span>
                    联网搜索
                  </button>
                </div>
                <div className="composer-right">
                  <button className="composer-action-btn" type="button" title="附件">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="m21.4 11.6-9.4 9.4a6.6 6.6 0 1 1-9.4-9.4l9.4-9.4a4.7 4.7 0 1 1 6.6 6.6l-9.4 9.4a2.8 2.8 0 1 1-4-4l9.4-9.4" />
                    </svg>
                  </button>
                  <button className="composer-send-btn" type="submit" disabled={isRunning || !question.trim()}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M12 19V5M5 12l7-7 7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </form>
            <div className="composer-disclaimer">内容由 AI 生成，请仔细甄别。</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
