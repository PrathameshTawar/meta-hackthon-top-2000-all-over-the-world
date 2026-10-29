"use client";

import { type Task, type Member } from "@/lib/api";
import { TaskCard } from "./TaskCard";

interface TaskColumnProps {
  label: string;
  colorClass: string;
  tasks: Task[];
  members: Member[];
  onSelect: (task: Task) => void;
  selectedId: number | null;
}

export function TaskColumn({
  label,
  colorClass,
  tasks,
  members,
  onSelect,
  selectedId,
}: TaskColumnProps) {
  return (
    <div className={`flex flex-col rounded-2xl border ${colorClass} min-w-[280px] w-[280px] p-3`}>
      <div className="column-header flex items-center justify-between mb-2 px-1">
        <span>{label}</span>
        <span className="bg-white/70 border border-gray-200 rounded-full px-2 py-0.5 text-gray-600 text-xs font-semibold">
          {tasks.length}
        </span>
      </div>

      <div className="flex flex-col gap-3 overflow-y-auto flex-1 pr-0.5">
        {tasks.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-6">No tasks here</p>
        )}
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            members={members}
            isSelected={task.id === selectedId}
            onClick={() => onSelect(task)}
          />
        ))}
      </div>
    </div>
  );
}
