"use client";

import { type Member, type Task } from "@/lib/api";
import clsx from "clsx";

interface MembersBarProps {
  members: Member[];
  tasks: Task[];
}

export function MembersBar({ members, tasks }: MembersBarProps) {
  const children = members.filter((m) => m.role === "child");

  if (children.length === 0) return null;

  return (
    <div className="flex items-center gap-4 overflow-x-auto py-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
        Family:
      </span>
      {children.map((m) => {
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
          <div key={m.id} className="flex items-center gap-2 whitespace-nowrap">
            <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-xs flex-shrink-0">
              {m.name[0].toUpperCase()}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-700">{m.name}</p>
              <p className="text-[10px] text-gray-400">
                {assigned} open
                {overdue > 0 && (
                  <span className="text-red-500 font-medium ml-1">· {overdue} overdue</span>
                )}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
