"use client";

import { type Member, type Task } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface MembersBarProps {
  members: Member[];
  tasks: Task[];
}

export function MembersBar({ members, tasks }: MembersBarProps) {
  const { t } = useI18n();
  const children = members.filter((m) => m.role === "child");
  const guardians = members.filter((m) => m.role === "helper");

  if (children.length === 0 && guardians.length === 0) return null;

  return (
    <div className="flex items-center gap-3 overflow-x-auto py-1">
      <span className="text-[10px] font-mono uppercase tracking-wider text-khata-muted font-semibold whitespace-nowrap">
        Siblings:
      </span>
      {[...children, ...guardians].map((m) => {
        const isGuardian = m.role === "helper";
        const assigned = tasks.filter(
          (t) => t.assignee_id === m.id && t.status !== "done"
        ).length;
        const overdue = tasks.filter(
          (t) =>
            t.assignee_id === m.id &&
            t.status !== "done" &&
            t.due_date &&
            new Date(t.due_date) < new Date()
        ).length;

        return (
          <div
            key={m.id}
            className="flex items-center gap-2 bg-khata-raised border border-khata-subtle rounded-md px-2.5 py-1 whitespace-nowrap shadow-2xs"
          >
            <div
              className={
                isGuardian
                  ? "w-5 h-5 rounded-full bg-sage-100 border border-sage-200 flex items-center justify-center text-sage-800 font-bold text-[10px] flex-shrink-0"
                  : "w-5 h-5 rounded-full bg-brand-100 border border-brand-200/80 flex items-center justify-center text-brand-700 font-bold text-[10px] flex-shrink-0"
              }
            >
              {m.name[0].toUpperCase()}
            </div>
            <div className="leading-tight">
              <span className="text-xs font-semibold text-khata-ink">{m.name}</span>
              {isGuardian && (
                <span className="ml-1.5 text-[10px] font-semibold text-sage-800 bg-sage-50 border border-sage-200 rounded px-1 py-px">
                  {t("role_guardian")}
                </span>
              )}
              <span className="text-[10px] font-mono text-khata-muted ml-1.5">
                {assigned} claimed
                {overdue > 0 && (
                  <span className="text-sindoor-600 font-bold ml-1">· {overdue} due</span>
                )}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
