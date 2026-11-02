"use client";

import { useMemo } from "react";
import { Task } from "@/lib/api";
import { IndianRupee, Layers, Home, Briefcase, CheckCircle2 } from "lucide-react";

interface MonthCommitmentBarProps {
  tasks: Task[];
}

export function MonthCommitmentBar({ tasks }: MonthCommitmentBarProps) {
  const commitments = useMemo(() => {
    let parentsTotal = 0;
    let loanEmiTotal = 0;
    let pendingCount = 0;

    tasks.forEach((t) => {
      if (t.status === "done") return;
      pendingCount++;

      // parse amount
      const amtStr = t.amount ? t.amount.replace(/[^\d]/g, "") : "0";
      const amt = parseInt(amtStr, 10) || 0;

      if (t.category === "loan_emi") {
        loanEmiTotal += amt;
      } else {
        parentsTotal += amt;
      }
    });

    return {
      parentsTotal,
      loanEmiTotal,
      grandTotal: parentsTotal + loanEmiTotal,
      pendingCount,
    };
  }, [tasks]);

  return (
    <div className="bg-white border-b border-khata-subtle px-6 py-2.5 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-6">
        {/* Main Combined Metric */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-khata-raised border border-khata-subtle flex items-center justify-center text-brand-600">
            <Layers size={17} />
          </div>
          <div>
            <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-khata-muted block">
              30-Day Family Commitment
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-khata-ink font-mono tabular-nums tracking-tight flex items-center">
                <IndianRupee size={16} className="text-brand-600 -mr-0.5" />
                {commitments.grandTotal.toLocaleString("en-IN")}
              </span>
              <span className="text-[11px] font-medium text-khata-muted">
                across 2 households
              </span>
            </div>
          </div>
        </div>

        {/* Dual-Household Breakdown Ledger Cards */}
        <div className="hidden sm:flex items-center gap-2 border-l border-khata-subtle pl-6">
          {/* Parents' Household */}
          <div className="bg-khata-canvas rounded-lg px-3 py-1.5 border border-khata-subtle flex items-center gap-2.5">
            <Home size={14} className="text-brand-500" />
            <div>
              <span className="text-[10px] text-khata-muted font-medium block">Parents' Bills & Care</span>
              <span className="text-xs font-bold text-khata-ink font-mono tabular-nums">
                ₹{commitments.parentsTotal.toLocaleString("en-IN")}
              </span>
            </div>
          </div>

          {/* Child's Commitments */}
          <div className="bg-khata-canvas rounded-lg px-3 py-1.5 border border-khata-subtle flex items-center gap-2.5">
            <Briefcase size={14} className="text-slate-600" />
            <div>
              <span className="text-[10px] text-khata-muted font-medium block">Earner's Loan EMIs</span>
              <span className="text-xs font-bold text-khata-ink font-mono tabular-nums">
                ₹{commitments.loanEmiTotal.toLocaleString("en-IN")}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Purpose Banner */}
      <div className="hidden lg:flex items-center gap-2 text-xs text-khata-muted bg-khata-raised border border-khata-subtle rounded-md px-3 py-1">
        <CheckCircle2 size={13} className="text-emerald-600" />
        <span className="font-medium">
          {commitments.pendingCount} active obligations · zero late penalties
        </span>
      </div>
    </div>
  );
}
