"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Task, type Member, updateTask } from "@/lib/api";
import { format, parseISO } from "date-fns";
import clsx from "clsx";
import { X, CheckCircle2, User } from "lucide-react";
import { EvidenceHighlight } from "./EvidenceHighlight";
import { useI18n } from "@/lib/i18n";

interface TaskDetailPanelProps {
  task: Task;
  members: Member[];
  onClose: () => void;
}

export function TaskDetailPanel({ task, members, onClose }: TaskDetailPanelProps) {
  const queryClient = useQueryClient();
  const { t } = useI18n();
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
    <aside className="w-[380px] flex-shrink-0 border-l border-khata-subtle bg-white flex flex-col h-full overflow-hidden shadow-sm">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-khata-subtle bg-khata-raised/50">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-brand-500/10 text-brand-600 flex items-center justify-center font-bold text-xs">
            त
          </div>
          <h2 className="text-sm font-bold text-khata-ink line-clamp-1">{task.title}</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded-md text-khata-muted hover:text-khata-ink hover:bg-khata-raised transition-colors cursor-pointer">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
        {/* Fields with evidence */}
        <section>
          <p className="text-[11px] font-bold uppercase tracking-wider text-khata-muted mb-3">
            {t("extracted_fields")}
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
                    "w-full text-left rounded-lg border p-3 transition-all cursor-pointer shadow-2xs",
                    isActive
                      ? "border-brand-500 bg-brand-50/60 ring-1 ring-brand-500/30"
                      : "border-khata-subtle hover:border-khata-ink/30 bg-white"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-khata-muted uppercase tracking-wider">{t(`field_${field}`)}</span>
                    {evidence && (
                      <span className="text-[10px] text-brand-600 font-semibold flex items-center gap-1">
                        {isActive ? t("hide_quote") : t("show_quote")}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-bold text-khata-ink mt-1 font-mono">
                    {value ?? <span className="text-khata-muted font-normal italic font-sans">{t("not_found")}</span>}
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
            <p className="text-[11px] font-bold uppercase tracking-wider text-khata-muted mb-3">
              {t("all_evidence", { count: task.evidence_items.length })}
            </p>
            <div className="space-y-2">
              {task.evidence_items.map((ev) => (
                <div
                  key={ev.id}
                  className="rounded-lg bg-khata-raised/60 border border-khata-subtle p-3 shadow-2xs"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-khata-muted">
                    {t(`field_${ev.field_name}`)}
                  </span>
                  <p className="verbatim-box text-xs text-khata-ink mt-1 font-mono leading-relaxed">
                    &ldquo;…{ev.quoted_span}…&rdquo;
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Assignee */}
        <section>
          <p className="text-[11px] font-bold uppercase tracking-wider text-khata-muted mb-2">
            {t("assigned_to")}
          </p>
          {assignee ? (
            <div className="flex items-center gap-2.5 p-2 rounded-lg bg-khata-raised/40 border border-khata-subtle">
              <div className="w-7 h-7 rounded-full bg-brand-500 text-white flex items-center justify-center font-bold text-xs shadow-2xs">
                {assignee.name[0].toUpperCase()}
              </div>
              <div>
                <span className="text-xs font-bold text-khata-ink">{assignee.name}</span>
                <span className="text-[11px] text-khata-muted block capitalize font-medium">{assignee.role}</span>
              </div>
            </div>
          ) : (
            <span className="text-xs text-khata-muted italic">{t("unassigned")}</span>
          )}
        </section>

        {/* Confidence */}
        {task.confidence !== null && (
          <section>
            <p className="text-[11px] font-bold uppercase tracking-wider text-khata-muted mb-2">
              {t("agent_confidence")}
            </p>
            <div className="flex items-center gap-3">
              <div className="flex-1 bg-khata-raised rounded-full h-2 border border-khata-subtle overflow-hidden">
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-500",
                    task.confidence >= 0.8 ? "bg-sage-600" :
                    task.confidence >= 0.6 ? "bg-ochre-500" : "bg-sindoor-600"
                  )}
                  style={{ width: `${Math.round((task.confidence ?? 0) * 100)}%` }}
                />
              </div>
              <span className="text-xs font-mono font-bold text-khata-ink w-9 text-right">
                {Math.round((task.confidence ?? 0) * 100)}%
              </span>
            </div>
          </section>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-khata-subtle px-5 py-4 flex gap-2 bg-khata-raised/30">
        {task.status !== "claimed" && task.status !== "done" && (
          <button
            onClick={() => claimMutation.mutate()}
            disabled={claimMutation.isPending}
            className="flex-1 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-lg px-4 py-2.5 text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-2xs cursor-pointer active:scale-98 disabled:opacity-50"
          >
            {claimMutation.isPending ? t("claiming") : t("claim_task")}
          </button>
        )}
        {(task.status === "claimed" || task.status === "confirmed") && (
          <button
            onClick={() => doneMutation.mutate()}
            disabled={doneMutation.isPending}
            className="flex-1 bg-sage-600 hover:bg-sage-700 active:bg-sage-800 text-white rounded-lg px-4 py-2.5 text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-2xs cursor-pointer active:scale-98 disabled:opacity-50"
          >
            <CheckCircle2 size={15} />
            {doneMutation.isPending ? t("marking") : t("mark_done")}
          </button>
        )}
      </div>
    </aside>
  );
}
