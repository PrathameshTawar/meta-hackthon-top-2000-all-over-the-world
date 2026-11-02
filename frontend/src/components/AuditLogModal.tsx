"use client";

import { useQuery } from "@tanstack/react-query";
import { getEvents, EventItem } from "@/lib/api";
import { format, parseISO } from "date-fns";
import { X, ShieldCheck, Activity, RefreshCw } from "lucide-react";
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
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-khata-subtle">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-khata-subtle bg-khata-raised/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 shadow-2xs">
              <Activity size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-khata-ink">Agent Decision Audit Log</h2>
              <p className="text-xs text-khata-muted font-medium">Append-only record of all perception, verification & guardrails</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              className="p-1.5 text-khata-muted hover:text-khata-ink rounded-lg hover:bg-white border border-transparent hover:border-khata-subtle transition-colors cursor-pointer"
              title="Refresh events"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-khata-muted hover:text-khata-ink rounded-lg hover:bg-white border border-transparent hover:border-khata-subtle transition-colors cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-khata-canvas/30">
          {isLoading && (
            <div className="text-center py-8 text-khata-muted text-sm font-medium">Loading audit events…</div>
          )}

          {!isLoading && events.length === 0 && (
            <div className="text-center py-8 text-khata-muted text-sm font-medium">No recorded events yet.</div>
          )}

          {events.map((ev) => {
            const isGuardrail = ev.action === "medical_blocked";
            const isEscalation = ev.action === "escalated";
            const isVerified = ev.action === "verified";

            return (
              <div
                key={ev.id}
                className={clsx(
                  "p-3.5 rounded-xl border transition-all text-xs shadow-2xs",
                  isGuardrail
                    ? "bg-sindoor-50/80 border-sindoor-200 text-sindoor-900"
                    : isEscalation
                      ? "bg-ochre-50/80 border-ochre-200 text-ochre-900"
                      : isVerified
                        ? "bg-sage-50/80 border-sage-200 text-sage-900"
                        : "bg-white border-khata-subtle text-khata-ink"
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded-md bg-white border border-khata-subtle shadow-2xs">
                      {ev.actor}
                    </span>
                    <span className="font-bold text-xs">
                      {ev.action}
                      {ev.task_id ? ` · Task #${ev.task_id}` : ""}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-khata-muted">
                    {format(parseISO(ev.created_at), "HH:mm:ss · dd MMM")}
                  </span>
                </div>

                {ev.reason && (
                  <p className="font-medium text-khata-ink mb-1">{ev.reason}</p>
                )}

                {ev.payload && (
                  <pre className="text-[10px] font-mono bg-white/90 p-2.5 rounded-md border border-khata-subtle overflow-x-auto text-khata-ink mt-1.5 shadow-2xs">
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-khata-subtle bg-khata-raised/50 flex items-center justify-between text-xs text-khata-muted font-medium">
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} className="text-sage-700" />
            Meta LLM Hackathon Verification Audit Trail
          </span>
          <span className="font-mono">{events.length} decisions logged</span>
        </div>
      </div>
    </div>
  );
}
