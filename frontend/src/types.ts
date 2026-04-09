export type StageKey =
  | "analysis"
  | "retrieval"
  | "planning"
  | "routing"
  | "market"
  | "product"
  | "development"
  | "summary"
  | "feedback";

export type StageStatus = "idle" | "running" | "done" | "waiting" | "error";

export type TimelineEvent = {
  id: string;
  type: "status" | "payload" | "message" | "error";
  title: string;
  detail: string;
  timestamp: string;
  stage?: StageKey;
  raw?: unknown;
};

export type StageCard = {
  key: StageKey;
  title: string;
  caption: string;
  accent: string;
  status: StageStatus;
  detail: string;
  updatedAt: string;
  node?: string;
};

export type SessionState = {
  threadId: string;
  assistantId: string;
  userQuery?: string;
  summary?: string;
  parsedQueries?: string[];
  plan?: string[];
  nextAgent?: string;
  marketOutput?: unknown;
  productOutput?: unknown;
  devOutput?: unknown;
  reportUrl?: string;
  reportDownloadUrl?: string;
  reportPdfUrl?: string;
  retrievedDocsCount?: number;
  terminal?: boolean;
};

export type StreamPayload = {
  kind: string;
  title?: string;
  detail?: string;
  timestamp?: string;
  raw?: unknown;
  stage?: StageKey;
  status?: StageStatus;
  node?: string;
  patch?: Partial<SessionState>;
  session?: SessionState;
};
