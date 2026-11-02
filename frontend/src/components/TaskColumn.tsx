"use client";

import { type Task, type Member } from "@/lib/api";
import { TaskCard } from "./TaskCard";

interface TaskColumnProps {
  label: string;
  index: string;
  dotColor: string;
  tasks: Task[];
  members: Member[];
  onSelect: (task: Task) => void;
  selectedId: number | null;
}

export function TaskColumn({
  label,
  index,
  dotColor,
  tasks,
  members,
  onSelect,
  selectedId,
}: TaskColumnProps) {
  return (
    <div className="flex flex-col rounded-xl border border-khata-subtle bg-khata-raised/40 min-w-[300px] w-[300px] p-3 shadow-2xs">
      {/* Column Header */}
      <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-khata-subtle/80 px-1">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${dotColor}`} />
          <span className="font-mono text-[10px] text-khata-muted font-bold tracking-wider">{index}</span>
          <span className="text-xs font-bold text-khata-ink tracking-tight uppercase">{label}</span>
        </div>
        <span className="bg-white border border-khata-subtle rounded-md px-1.5 py-0.5 text-khata-ink font-mono text-[10px] font-bold shadow-2xs">
          {tasks.length}
        </span>
      </div>

      {/* Task List */}
      <div className="flex flex-col gap-2.5 overflow-y-auto flex-1 pr-0.5">
        {tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 border border-dashed border-khata-subtle rounded-lg text-center p-4">
            <span className="text-xs text-khata-muted font-medium">No tasks in this lane</span>
          </div>
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
