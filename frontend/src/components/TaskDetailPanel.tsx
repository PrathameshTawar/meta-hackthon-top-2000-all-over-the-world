"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Task, type Member, updateTask } from "@/lib/api";
import { format, parseISO } from "date-fns";
import clsx from "clsx";
import { X, CheckCircle2, User } from "lucide-react";
import { EvidenceHighlight } from "./EvidenceHighlight";

interface TaskDetailPanelProps {
  task: Task;
  members: Member[];
  onClose: () => void;
}

const FIELD_LABELS: Record<string, string> = {
  amount:   "Amount",
  due_date: "Due date",
  payee:    "Payee",
  title:    "Title",
};

export function TaskDetailPanel({ task, members, onClose }: TaskDetailPanelProps) {
  const queryClient = useQueryClient();
  const [activeField, setActiveField] = useState<string | null>(null);

  const claimMutation = useMutation({
    mutationFn: () => updateTask(task.id, { status: "claimed" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", task.household_id] });
    },
  });

  const doneMutation = useMutation({
    mutationFn: () => updateTask(task.id, { status: "done" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", task.household_id] });
      onClose();
    },
  });

  const assignee = members.find((m) => m.id === task.assignee_id);
  const activeEvidence = task.evidence_items.find((e) => e.field_name === activeField);

  return (
    <aside className="w-[380px] flex-shrink-0 border-l border-gray-200 bg-white flex flex-col h-full overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800 line-clamp-1">{task.title}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition-colors">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
        {/* Fields with evidence */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            Extracted Fields
          </p>
          <div className="space-y-2">
            {(["amount", "due_date", "payee"] as const).map((field) => {
              const value =
                field === "due_date" && task[field]
                  ? format(parseISO(task[field]!), "dd MMM yyyy")
                  : task[field];
              const evidence = task.evidence_items.find((e) => e.field_name === field);
              const isActive = activeField === field;

              return (
                <button
                  key={field}
                  onClick={() => setActiveField(isActive ? null : field)}
                  className={clsx(
                    "w-full text-left rounded-lg border px-3 py-2.5 transition-all",
                    isActive
                      ? "border-brand-500 bg-brand-50"
                      : "border-gray-200 hover:border-gray-300 bg-white"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">{FIELD_LABELS[field]}</span>
                    {evidence && (
                      <span className="text-[10px] text-brand-600 font-medium">
                        {isActive ? "▲ Hide quote" : "▼ Show quote"}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-gray-800 mt-0.5">
                    {value ?? <span className="text-gray-400 font-normal italic">Not found</span>}
                  </p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Evidence quote panel */}
        {activeEvidence && (
          <EvidenceHighlight
            quote={activeEvidence.quoted_span}
            fieldName={activeEvidence.field_name}
          />
        )}

        {/* All evidence list */}
        {task.evidence_items.length > 0 && (
          <section>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
              All Evidence ({task.evidence_items.length})
            </p>
            <div className="space-y-2">
              {task.evidence_items.map((ev) => (
                <div
                  key={ev.id}
                  className="rounded-lg bg-gray-50 border border-gray-100 px-3 py-2"
                >
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
                    {FIELD_LABELS[ev.field_name] ?? ev.field_name}
                  </span>
                  <p className="text-xs text-gray-700 mt-0.5 font-mono leading-relaxed">
                    "…{ev.quoted_span}…"
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Assignee */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-2">
            Assigned to
          </p>
          {assignee ? (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-xs">
                {assignee.name[0].toUpperCase()}
              </div>
              <span className="text-sm text-gray-700">{assignee.name}</span>
              <span className="text-xs text-gray-400 capitalize">({assignee.role})</span>
            </div>
          ) : (
            <span className="text-sm text-gray-400 italic">Unassigned</span>
          )}
        </section>

        {/* Confidence */}
        {task.confidence !== null && (
          <section>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-2">
              Agent confidence
            </p>
            <div className="flex items-center gap-3">
              <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                <div
                  className={clsx(
                    "h-1.5 rounded-full",
                    task.confidence >= 0.8 ? "bg-green-500" :
                    task.confidence >= 0.6 ? "bg-yellow-400" : "bg-red-400"
                  )}
                  style={{ width: `${Math.round((task.confidence ?? 0) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-500 w-8">
                {Math.round((task.confidence ?? 0) * 100)}%
              </span>
            </div>
          </section>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-gray-100 px-5 py-4 flex gap-2">
        {task.status !== "claimed" && task.status !== "done" && (
          <button
            onClick={() => claimMutation.mutate()}
            disabled={claimMutation.isPending}
            className="btn-primary flex-1"
          >
            {claimMutation.isPending ? "Claiming…" : "Claim task"}
          </button>
        )}
        {(task.status === "claimed" || task.status === "confirmed") && (
          <button
            onClick={() => doneMutation.mutate()}
            disabled={doneMutation.isPending}
            className="flex-1 bg-green-600 hover:bg-green-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
          >
            <CheckCircle2 size={14} />
            {doneMutation.isPending ? "Marking…" : "Mark done"}
          </button>
        )}
      </div>
    </aside>
  );
}
