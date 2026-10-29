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
import { FastForward, Sparkles, Activity, RotateCcw, AlertTriangle, CheckCircle2 } from "lucide-react";

const COLUMNS: { statuses: TaskStatus[]; label: string; color: string }[] = [
  { statuses: ["new", "confirmed", "escalated"], label: "New & Pending", color: "bg-blue-50/70 border-blue-200" },
  { statuses: ["needs_review"], label: "Needs Confirmation", color: "bg-amber-50/70 border-amber-200" },
  { statuses: ["claimed"], label: "Claimed by Sibling", color: "bg-purple-50/70 border-purple-200" },
  { statuses: ["done"], label: "Done & Verified", color: "bg-emerald-50/70 border-emerald-200" },
];

interface BoardProps {
  householdId: number;
}

export function Board({ householdId }: BoardProps) {
  const queryClient = useQueryClient();
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isAuditOpen, setIsAuditOpen] = useState(false);
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
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
      setToastMessage(`⚡ Fast-forwarded 3 days: ${res.count} unclaimed task(s) escalated to siblings!`);
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
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading family coordination board…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-65px)]">
      {/* 30-Day Family Financial Commitments */}
      <MonthCommitmentBar tasks={tasks} />

      {/* Action / Toolbar */}
      <div className="bg-white border-b border-gray-200 px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-2xs">
        {/* Members status */}
        <div className="flex items-center gap-4">
          <MembersBar members={members} tasks={tasks} />
        </div>

        {/* Demo buttons */}
        <div className="flex items-center gap-2">
          {toastMessage && (
            <span className="text-xs font-medium text-amber-900 bg-amber-100 border border-amber-200 rounded-lg px-2.5 py-1 animate-pulse">
              {toastMessage}
            </span>
          )}

          <button
            onClick={() => setIsSimulateOpen(true)}
            className="flex items-center gap-1.5 text-xs font-semibold bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-3 py-1.5 transition-colors shadow-2xs cursor-pointer"
          >
            <Sparkles size={14} />
            Try Live Agent
          </button>

          <button
            onClick={() => escalateMutation.mutate()}
            disabled={escalateMutation.isPending}
            className="flex items-center gap-1.5 text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white rounded-lg px-3 py-1.5 transition-colors shadow-2xs cursor-pointer"
            title="Simulate advancing clock by 3 days to test escalation near deadline"
          >
            <FastForward size={14} />
            {escalateMutation.isPending ? "Fast-forwarding…" : "Simulate 3 Days Later"}
          </button>

          <button
            onClick={() => setIsAuditOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-3 py-1.5 transition-colors cursor-pointer"
            title="Inspect append-only agent decision audit log"
          >
            <Activity size={14} />
            Audit Log
          </button>

          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
            title="Reset demo data to initial state"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </div>

      {/* Kanban columns + detail panel */}
      <div className="flex flex-1 overflow-hidden bg-slate-50/50">
        <div className="flex flex-1 gap-4 p-6 overflow-x-auto">
          {COLUMNS.map((col) => {
            const colTasks = tasks.filter((t) => col.statuses.includes(t.status));
            return (
              <TaskColumn
                key={col.label}
                label={col.label}
                colorClass={col.color}
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
