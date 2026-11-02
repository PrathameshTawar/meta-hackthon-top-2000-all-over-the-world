import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_SECRET;

export const api = axios.create({
  baseURL: BASE,
  headers: ADMIN_TOKEN ? { "X-Admin-Token": ADMIN_TOKEN } : {},
});

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

export const updateTask = (
  taskId: number,
  patch: Partial<Pick<Task, "status" | "assignee_id">>,
  householdId?: number
) =>
  api
    .patch<Task>(`/tasks/${taskId}`, patch, {
      params: householdId ? { household_id: householdId } : undefined,
      headers: householdId ? { "X-Household-Id": String(householdId) } : undefined,
    })
    .then((r) => r.data);

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

// ---------------------------------------------------------------------------
// Health Module (H-1 to H-5)
// ---------------------------------------------------------------------------

export interface Medication {
  id: number;
  household_id: number;
  member_id: number;
  name: string;
  dose_text: string;
  times: string[];
  owner_child_id: number | null;
  active: boolean;
  created_at?: string;
}

export interface DoseLog {
  id: number;
  medication_id: number;
  scheduled_for: string;
  status: "pending" | "taken" | "missed";
  reminder_sent_at: string | null;
  responded_at: string | null;
  escalated_at: string | null;
  medication_name?: string;
  member_name?: string;
}

export interface Vital {
  id: number;
  household_id: number;
  member_id: number;
  kind: "bp" | "sugar" | "weight" | "spo2" | "pulse" | "temperature";
  value_1: number;
  value_2: number | null;
  unit: string;
  measured_at: string;
  artifact_id: number | null;
  quote: string;
}

export interface VitalThreshold {
  id: number;
  household_id: number;
  member_id: number;
  kind: "bp" | "sugar" | "weight" | "spo2" | "pulse" | "temperature";
  field: "value_1" | "value_2";
  op: "gt" | "lt";
  limit: number;
  note: string | null;
  set_by_member_id: number | null;
  active: boolean;
}

export interface HealthSummary {
  todays_doses: (DoseLog & { medication_name?: string; member_name?: string })[];
  recent_vitals: Vital[];
  active_thresholds: VitalThreshold[];
  active_medications: Medication[];
}

export const getHealthSummary = (householdId: number) =>
  api.get<HealthSummary>(`/health/${householdId}/summary`).then((r) => r.data);

export const createMedication = (data: Partial<Medication>) =>
  api.post<Medication>("/health/medications", data).then((r) => r.data);

export const updateMedication = (id: number, data: Partial<Medication>) =>
  api.patch<Medication>(`/health/medications/${id}`, data).then((r) => r.data);

export const createThreshold = (data: Partial<VitalThreshold>) =>
  api.post<VitalThreshold>("/health/thresholds", data).then((r) => r.data);

export const updateThreshold = (id: number, data: Partial<VitalThreshold>) =>
  api.patch<VitalThreshold>(`/health/thresholds/${id}`, data).then((r) => r.data);

export const simulateDoseNow = (medicationId: number) =>
  api.post<{ status: string; reminder_sent: boolean }>("/admin/health/dose-now", { medication_id: medicationId }).then((r) => r.data);

export const simulateSkipHealth = (minutes: number = 120) =>
  api.post<{ status: string; escalated_doses_count: number }>("/admin/health/skip", { minutes }).then((r) => r.data);


