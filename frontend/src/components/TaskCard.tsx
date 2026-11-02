"use client";

import { type Task, type Member } from "@/lib/api";
import { format, parseISO, isPast } from "date-fns";
import clsx from "clsx";
import { AlertTriangle, Calendar, IndianRupee, FileText, CheckCircle2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const CATEGORY_STYLES: Record<string, { label: string; badge: string; rail: string }> = {
  bill: {
    label: "Utility Bill",
    badge: "bg-amber-100/80 text-amber-900 border-amber-200",
    rail: "border-l-amber-600",
  },
  loan_emi: {
    label: "Loan EMI",
    badge: "bg-rose-100/80 text-rose-900 border-rose-200",
    rail: "border-l-rose-600",
  },
  pension: {
    label: "Pension",
    badge: "bg-teal-100/80 text-teal-900 border-teal-200",
    rail: "border-l-teal-600",
  },
  govt_letter: {
    label: "Govt Notice",
    badge: "bg-slate-100 text-slate-800 border-slate-200",
    rail: "border-l-slate-600",
  },
  insurance: {
    label: "Insurance",
    badge: "bg-sky-100/80 text-sky-900 border-sky-200",
    rail: "border-l-sky-600",
  },
  appointment: {
    label: "Appointment",
    badge: "bg-indigo-100/80 text-indigo-900 border-indigo-200",
    rail: "border-l-indigo-600",
  },
  medical: {
    label: "Medical Care",
    badge: "bg-red-100/80 text-red-900 border-red-200",
    rail: "border-l-red-600",
  },
  chit_chat: {
    label: "Note",
    badge: "bg-stone-100 text-stone-700 border-stone-200",
    rail: "border-l-stone-400",
  },
  unknown: {
    label: "General",
    badge: "bg-stone-100 text-stone-700 border-stone-200",
    rail: "border-l-stone-400",
  },
};

interface TaskCardProps {
  task: Task;
  members: Member[];
  isSelected: boolean;
  onClick: () => void;
}

export function TaskCard({ task, members, isSelected, onClick }: TaskCardProps) {
  const { t } = useI18n();
  const assignee = members.find((m) => m.id === task.assignee_id);
  const dueDate = task.due_date ? parseISO(task.due_date) : null;
  const overdue = dueDate ? isPast(dueDate) && task.status !== "done" : false;
  const hasEvidence = task.evidence_items.length > 0;
  const style = CATEGORY_STYLES[task.category] ?? CATEGORY_STYLES.unknown;

  return (
    <button
      onClick={onClick}
      className={clsx(
        "task-card w-full text-left transition-all border-l-[3px]",
        style.rail,
        isSelected && "ring-2 ring-brand-500 border-brand-500 shadow-md",
        task.status === "escalated" && "border-sindoor-600 bg-sindoor-50/40 ring-1 ring-sindoor-600/40",
        overdue && task.status !== "escalated" && "border-sindoor-400"
      )}
    >
      {/* Header Row: Category Badge & Due Date Pill */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={clsx("text-[10px] font-semibold px-2 py-0.5 rounded border tracking-tight", style.badge)}>
          {style.label}
        </span>

        {dueDate && (
          <span
            className={clsx(
              "text-[10px] font-mono font-medium flex items-center gap-1",
              overdue ? "text-sindoor-700 font-bold" : "text-khata-muted"
            )}
          >
            <Calendar size={10} className={overdue ? "text-sindoor-600" : "text-khata-muted"} />
            {format(dueDate, "dd MMM")}
            {overdue && " ⚠️"}
          </span>
        )}
      </div>

      {/* Title */}
      <h4 className="text-xs font-semibold text-khata-ink leading-snug mb-2 line-clamp-2">
        {task.title}
      </h4>

      {/* Payee / Organisation */}
      {task.payee && (
        <p className="text-[11px] text-khata-muted mb-2 font-medium truncate">
          {task.payee}
        </p>
      )}

      {/* Footer: Amount & Assignee / Evidence Provenance */}
      <div className="flex items-center justify-between pt-2 border-t border-khata-subtle/60 mt-1">
        {/* Amount */}
        {task.amount ? (
          <div className="flex items-baseline font-mono font-bold text-xs text-khata-ink tabular-nums">
            <span className="text-brand-600 mr-0.5">₹</span>
            {task.amount.replace(/[^\d,.]/g, "")}
          </div>
        ) : (
          <span className="text-[10px] font-mono text-khata-muted italic">Non-monetary</span>
        )}

        {/* Right side: Assignee or Evidence tag */}
        <div className="flex items-center gap-1.5">
          {hasEvidence && (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-khata-raised text-khata-muted px-1.5 py-0.5 rounded border border-khata-subtle" title="Document evidence attached">
              <FileText size={10} />
              {task.evidence_items.length}
            </span>
          )}

          {assignee ? (
            <div className="flex items-center gap-1 bg-brand-50 border border-brand-200/60 rounded px-1.5 py-0.5">
              <div className="w-3.5 h-3.5 rounded-full bg-brand-500 text-white font-bold text-[8px] flex items-center justify-center">
                {assignee.name[0].toUpperCase()}
              </div>
              <span className="text-[10px] font-medium text-brand-900">{assignee.name.split(" ")[0]}</span>
            </div>
          ) : (
            task.status === "done" && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700">
                <CheckCircle2 size={11} />
                Settled
              </span>
            )
          )}
        </div>
      </div>

      {/* Escalated / Review Alerts */}
      {task.status === "escalated" && (
        <div className="mt-2 text-[10px] font-bold text-sindoor-800 bg-sindoor-100/90 border border-sindoor-300 rounded px-2 py-0.5 flex items-center gap-1">
          <AlertTriangle size={10} className="text-sindoor-600" />
          {t("escalated")} · Approaching Due Date
        </div>
      )}

      {task.confidence !== null && task.confidence < 0.6 && task.status !== "escalated" && (
        <div className="mt-2 text-[10px] font-medium text-ochre-900 bg-ochre-100/80 border border-ochre-200 rounded px-2 py-0.5 flex items-center gap-1">
          <AlertTriangle size={10} className="text-ochre-700" />
          {t("low_confidence", { percent: Math.round((task.confidence ?? 0) * 100) })}
        </div>
      )}
    </button>
  );
}
