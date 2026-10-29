"use client";

import { type Task, type Member } from "@/lib/api";
import { format, parseISO, isPast } from "date-fns";
import clsx from "clsx";
import { AlertCircle, Calendar, IndianRupee, Paperclip } from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  bill:        "Bill",
  loan_emi:    "Loan EMI",
  pension:     "Pension",
  govt_letter: "Govt Letter",
  insurance:   "Insurance",
  appointment: "Appointment",
  medical:     "Medical",
  chit_chat:   "Chit-chat",
  unknown:     "Unknown",
};

const CATEGORY_COLORS: Record<string, string> = {
  bill:        "bg-orange-100 text-orange-700",
  loan_emi:    "bg-red-100 text-red-700",
  pension:     "bg-teal-100 text-teal-700",
  govt_letter: "bg-slate-100 text-slate-700",
  insurance:   "bg-indigo-100 text-indigo-700",
  appointment: "bg-sky-100 text-sky-700",
  medical:     "bg-rose-100 text-rose-700",
  chit_chat:   "bg-gray-100 text-gray-600",
  unknown:     "bg-gray-100 text-gray-500",
};

const STATUS_DOT: Record<string, string> = {
  new:          "bg-blue-400",
  confirmed:    "bg-blue-400",
  needs_review: "bg-yellow-400",
  claimed:      "bg-purple-400",
  done:         "bg-green-400",
  escalated:    "bg-red-500",
};

interface TaskCardProps {
  task: Task;
  members: Member[];
  isSelected: boolean;
  onClick: () => void;
}

export function TaskCard({ task, members, isSelected, onClick }: TaskCardProps) {
  const assignee = members.find((m) => m.id === task.assignee_id);
  const dueDate = task.due_date ? parseISO(task.due_date) : null;
  const overdue = dueDate ? isPast(dueDate) && task.status !== "done" : false;
  const hasEvidence = task.evidence_items.length > 0;

  return (
    <button
      onClick={onClick}
      className={clsx(
        "task-card w-full text-left transition-all",
        isSelected && "ring-2 ring-brand-500",
        task.status === "escalated" && "border-red-400 bg-red-50/30 ring-1 ring-red-400/50 shadow-xs",
        overdue && task.status !== "escalated" && "border-red-300"
      )}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span
          className={clsx(
            "badge",
            CATEGORY_COLORS[task.category] ?? CATEGORY_COLORS.unknown
          )}
        >
          {CATEGORY_LABELS[task.category] ?? task.category}
        </span>
        <span
          className={clsx(
            "w-2 h-2 rounded-full mt-1 flex-shrink-0",
            STATUS_DOT[task.status] ?? "bg-gray-300"
          )}
        />
      </div>

      {/* Title */}
      <p className="text-sm font-medium text-gray-800 leading-snug mb-2 line-clamp-2">
        {task.title}
      </p>

      {/* Meta row */}
      <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
        {task.amount && (
          <span className="flex items-center gap-0.5">
            <IndianRupee size={11} />
            {task.amount}
          </span>
        )}
        {dueDate && (
          <span
            className={clsx(
              "flex items-center gap-0.5",
              overdue && "text-red-500 font-medium"
            )}
          >
            <Calendar size={11} />
            {format(dueDate, "dd MMM")}
            {overdue && " ⚠"}
          </span>
        )}
        {hasEvidence && (
          <span className="flex items-center gap-0.5">
            <Paperclip size={11} />
            {task.evidence_items.length}
          </span>
        )}
        {task.status === "needs_review" && (
          <span className="flex items-center gap-0.5 text-yellow-600 font-medium">
            <AlertCircle size={11} />
            Review
          </span>
        )}
        {task.status === "escalated" && (
          <span className="flex items-center gap-0.5 text-red-600 font-bold bg-red-100 px-1.5 py-0.5 rounded text-[10px]">
            <AlertCircle size={10} />
            ESCALATED
          </span>
        )}
      </div>

      {/* Assignee chip */}
      {assignee && (
        <div className="mt-2.5 flex items-center gap-1.5">
          <div className="w-5 h-5 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 text-[10px] font-bold">
            {assignee.name[0].toUpperCase()}
          </div>
          <span className="text-xs text-gray-500">{assignee.name}</span>
        </div>
      )}

      {/* Low confidence warning */}
      {task.confidence !== null && task.confidence < 0.6 && (
        <p className="mt-2 text-[10px] text-yellow-600 bg-yellow-50 rounded px-1.5 py-0.5">
          Low confidence · {Math.round((task.confidence ?? 0) * 100)}%
        </p>
      )}
    </button>
  );
}
