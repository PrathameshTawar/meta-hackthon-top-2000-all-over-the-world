"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTasks, getMembers, simulateEscalation, resetDatabase, type Task, type TaskStatus } from "@/lib/api";
import { TaskColumn } from "./TaskColumn";
import { TaskDetailPanel } from "./TaskDetailPanel";
import { MembersBar } from "./MembersBar";
import { MonthCommitmentBar } from "./MonthCommitmentBar";
import { AuditLogModal } from "./AuditLogModal";
import { SimulateModal } from "./SimulateModal";
import { HealthPanel } from "./HealthPanel";
import { BoardSkeleton } from "./BoardSkeleton";
import { FastForward, Inbox, Activity, RotateCcw, AlertTriangle, CheckCircle2, HeartPulse, CheckSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const COLUMNS: { statuses: TaskStatus[]; labelKey: string; index: string; dotColor: string }[] = [
  { statuses: ["new", "confirmed", "escalated"], labelKey: "col_new", index: "01", dotColor: "bg-brand-500" },
  { statuses: ["needs_review"], labelKey: "col_needs_review", index: "02", dotColor: "bg-ochre-500" },
  { statuses: ["claimed"], labelKey: "col_claimed", index: "03", dotColor: "bg-blue-600" },
  { statuses: ["done"], labelKey: "col_done", index: "04", dotColor: "bg-sage-600" },
];

interface BoardProps {
  householdId: number;
}

export function Board({ householdId }: BoardProps) {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<"tasks" | "health">("tasks");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isAuditOpen, setIsAuditOpen] = useState(false);
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const { data: tasks = [], isLoading: tasksLoading, isError: tasksError } = useQuery({
    queryKey: ["tasks", householdId],
    queryFn: () => getTasks(householdId),
    refetchInterval: 3000, // 3s polling as spec in saath.md
  });

  const { data: members = [] } = useQuery({
    queryKey: ["members", householdId],
    queryFn: () => getMembers(householdId),
  });

  const escalateMutation = useMutation({
    mutationFn: () => simulateEscalation(3),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", householdId] });
      queryClient.invalidateQueries({ queryKey: ["events", householdId] });
      setToastMessage(`Skipped ahead 3 days. ${res.count} unclaimed task(s) escalated to siblings.`);
      setTimeout(() => setToastMessage(null), 4500);
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => resetDatabase(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", householdId] });
      queryClient.invalidateQueries({ queryKey: ["events", householdId] });
      setSelectedTask(null);
      setToastMessage("Demo database reset to clean take!");
      setTimeout(() => setToastMessage(null), 3000);
    },
  });

  if (tasksLoading && tasks.length === 0) {
    return <BoardSkeleton />;
  }

  if (tasksError && tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-65px)] bg-khata-canvas p-6 text-center space-y-3">
        <div className="w-12 h-12 rounded-xl bg-sindoor-100 text-sindoor-700 flex items-center justify-center font-bold text-lg border border-sindoor-200">
          !
        </div>
        <h3 className="text-sm font-bold text-khata-ink">Unable to Load Family Ledger</h3>
        <p className="text-xs text-khata-muted max-w-sm">
          Backend server connection check failed. Ensure the FastAPI backend is running on port 8000.
        </p>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ["tasks", householdId] })}
          className="mt-2 px-4 py-2 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-lg text-xs font-bold shadow-2xs cursor-pointer"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-65px)] bg-khata-canvas">
      {/* 30-Day Family Financial Commitments */}
      <MonthCommitmentBar tasks={tasks} />

      {/* Action / Toolbar */}
      <div className="bg-khata-raised/90 backdrop-blur-xs border-b border-khata-subtle px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-2xs">
        {/* Tab Switcher & Members status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 bg-white border border-khata-subtle p-1 rounded-xl shadow-2xs">
            <button
              onClick={() => setActiveTab("tasks")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${activeTab === "tasks"
                  ? "bg-khata-ink text-white shadow-2xs"
                  : "text-khata-muted hover:text-khata-ink"
                }`}
            >
              <CheckSquare size={13} />
              {t("tab_tasks")}
            </button>
            <button
              onClick={() => setActiveTab("health")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${activeTab === "health"
                  ? "bg-sindoor-600 text-white shadow-2xs"
                  : "text-khata-muted hover:text-khata-ink"
                }`}
            >
              <HeartPulse size={13} />
              {t("tab_health")}
            </button>
          </div>

          <MembersBar members={members} tasks={tasks} />
        </div>

        {/* Demo buttons */}
        <div className="flex items-center gap-2">
          {toastMessage && (
            <span className="text-xs font-medium text-ochre-900 bg-ochre-100 border border-ochre-200 rounded-lg px-2.5 py-1">
              {toastMessage}
            </span>
          )}

          <button
            onClick={() => setIsSimulateOpen(true)}
            className="flex items-center gap-1.5 text-xs font-semibold bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-lg px-3.5 py-1.5 transition-all shadow-2xs cursor-pointer hover:shadow-xs"
          >
            <Inbox size={14} />
            {t("try_live_agent")}
          </button>

          <button
            onClick={() => escalateMutation.mutate()}
            disabled={escalateMutation.isPending}
            className="flex items-center gap-1.5 text-xs font-semibold bg-ochre-700 hover:bg-ochre-800 active:bg-ochre-900 text-white rounded-lg px-3 py-1.5 transition-all shadow-2xs cursor-pointer hover:shadow-xs disabled:opacity-50"
            title="Simulate advancing clock by 3 days to test escalation near deadline"
          >
            <FastForward size={14} />
            {escalateMutation.isPending ? "Fast-forwarding…" : t("simulate_3_days")}
          </button>

          <button
            onClick={() => setIsAuditOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium bg-white hover:bg-khata-raised text-khata-ink border border-khata-subtle rounded-lg px-3 py-1.5 transition-colors cursor-pointer shadow-2xs"
            title="Inspect append-only agent decision audit log"
          >
            <Activity size={14} className="text-khata-muted" />
            {t("audit_log")}
          </button>

          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="p-1.5 text-khata-muted hover:text-khata-ink hover:bg-white border border-transparent hover:border-khata-subtle rounded-lg transition-colors cursor-pointer"
            title="Reset demo data to initial state"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </div>

      {/* Main Content: Tasks Board vs Health Panel */}
      {activeTab === "health" ? (
        <HealthPanel householdId={householdId} members={members} />
      ) : (
        <div className="flex flex-1 overflow-hidden bg-khata-canvas">
          <div className="flex flex-1 gap-4 p-6 overflow-x-auto">
            {COLUMNS.map((col) => {
              const colTasks = tasks.filter((t) => col.statuses.includes(t.status));
              return (
                <TaskColumn
                  key={col.labelKey}
                  index={col.index}
                  dotColor={col.dotColor}
                  label={t(col.labelKey)}
                  tasks={colTasks}
                  members={members}
                  onSelect={setSelectedTask}
                  selectedId={selectedTask?.id ?? null}
                />
              );
            })}
          </div>

          {/* Evidence / detail side panel */}
          {selectedTask && (
            <TaskDetailPanel
              task={selectedTask}
              members={members}
              onClose={() => setSelectedTask(null)}
            />
          )}
        </div>
      )}

      {/* Modals */}
      <AuditLogModal
        householdId={householdId}
        isOpen={isAuditOpen}
        onClose={() => setIsAuditOpen(false)}
      />

      <SimulateModal
        householdId={householdId}
        isOpen={isSimulateOpen}
        onClose={() => setIsSimulateOpen(false)}
      />
    </div>
  );
}
