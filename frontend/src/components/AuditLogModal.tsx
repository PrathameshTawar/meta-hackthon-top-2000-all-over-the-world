"use client";

import { useQuery } from "@tanstack/react-query";
import { getEvents, EventItem } from "@/lib/api";
import { format, parseISO } from "date-fns";
import { X, ShieldCheck, Activity, Bot, AlertTriangle, RefreshCw } from "lucide-react";
import clsx from "clsx";

interface AuditLogModalProps {
  householdId: number;
  isOpen: boolean;
  onClose: () => void;
}

export function AuditLogModal({ householdId, isOpen, onClose }: AuditLogModalProps) {
  const { data: events = [], isLoading, refetch } = useQuery({
    queryKey: ["events", householdId],
    queryFn: () => getEvents(householdId),
    enabled: isOpen,
    refetchInterval: isOpen ? 3000 : false,
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-gray-100">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Activity size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Agent Decision Audit Log</h2>
              <p className="text-xs text-gray-500">Append-only record of all perception, verification & guardrails</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              title="Refresh events"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {isLoading && (
            <div className="text-center py-8 text-gray-400 text-sm">Loading audit events…</div>
          )}

          {!isLoading && events.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">No recorded events yet.</div>
          )}

          {events.map((ev) => {
            const isGuardrail = ev.action === "medical_blocked";
            const isEscalation = ev.action === "escalated";
            const isVerified = ev.action === "verified";

            return (
              <div
                key={ev.id}
                className={clsx(
                  "p-3.5 rounded-xl border transition-all text-xs",
                  isGuardrail
                    ? "bg-rose-50/70 border-rose-200 text-rose-900"
                    : isEscalation
                    ? "bg-amber-50/70 border-amber-200 text-amber-900"
                    : isVerified
                    ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
                    : "bg-gray-50 border-gray-200 text-gray-800"
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded-md bg-white border border-gray-200">
                      {ev.actor}
                    </span>
                    <span className="font-medium text-xs">
                      {ev.action}
                      {ev.task_id ? ` · Task #${ev.task_id}` : ""}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-400">
                    {format(parseISO(ev.created_at), "HH:mm:ss · dd MMM")}
                  </span>
                </div>

                {ev.reason && (
                  <p className="font-medium text-gray-700 mb-1">{ev.reason}</p>
                )}

                {ev.payload && (
                  <pre className="text-[10px] font-mono bg-white/80 p-2 rounded-md border border-gray-200/60 overflow-x-auto text-gray-600 mt-1.5">
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-100 bg-gray-50 flex items-center justify-between text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} className="text-emerald-600" />
            Meta LLM Hackathon Verification Audit Trail
          </span>
          <span>{events.length} decisions logged</span>
        </div>
      </div>
    </div>
  );
}
