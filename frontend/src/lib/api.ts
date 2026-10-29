import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({ baseURL: BASE });

// ---------------------------------------------------------------------------
// Types (mirroring backend Pydantic schemas)
// ---------------------------------------------------------------------------

export type TaskStatus = "new" | "confirmed" | "needs_review" | "claimed" | "done" | "escalated";
export type TaskCategory =
  | "bill" | "loan_emi" | "pension" | "govt_letter"
  | "insurance" | "appointment" | "medical" | "chit_chat" | "unknown";

export interface Evidence {
  id: number;
  artifact_id: number;
  quoted_span: string;
  field_name: string;
}

export interface Task {
  id: number;
  household_id: number;
  category: TaskCategory;
  title: string;
  amount: string | null;
  due_date: string | null;
  payee: string | null;
  status: TaskStatus;
  assignee_id: number | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
  evidence_items: Evidence[];
}

export interface Member {
  id: number;
  household_id: number;
  name: string;
  role: "parent" | "child" | "helper";
  telegram_id: string | null;
  categories_owned: string[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const getTasks = (householdId: number) =>
  api.get<Task[]>(`/tasks/${householdId}`).then((r) => r.data);

export const updateTask = (taskId: number, patch: Partial<Pick<Task, "status" | "assignee_id">>) =>
  api.patch<Task>(`/tasks/${taskId}`, patch).then((r) => r.data);

export const getMembers = (householdId: number) =>
  api.get<Member[]>(`/members/${householdId}`).then((r) => r.data);

export interface EventItem {
  id: number;
  household_id: number | null;
  task_id: number | null;
  actor: string;
  action: string;
  reason: string | null;
  payload: any;
  created_at: string;
}

export const getEvents = (householdId: number) =>
  api.get<EventItem[]>(`/events/${householdId}`).then((r) => r.data);

export const simulateEscalation = (daysAhead: number = 3) =>
  api.post<{ status: string; escalated_task_ids: number[]; count: number }>("/admin/escalate/simulate", {
    days_ahead: daysAhead,
  }).then((r) => r.data);

export const simulateIngest = (data: { type: string; raw_text: string; household_id?: number }) =>
  api.post("/admin/ingest/simulate", { household_id: 1, ...data }).then((r) => r.data);

export const resetDatabase = () =>
  api.post("/admin/reset").then((r) => r.data);

