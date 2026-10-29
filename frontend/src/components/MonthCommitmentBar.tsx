"use client";

import { useMemo } from "react";
import { Task } from "@/lib/api";
import { IndianRupee, TrendingUp, AlertTriangle, CalendarCheck2 } from "lucide-react";

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
    <div className="bg-gradient-to-r from-amber-500/10 via-orange-500/5 to-transparent border-b border-orange-200/60 px-6 py-3 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-6">
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-700 flex items-center gap-1">
            <CalendarCheck2 size={12} />
            Next 30 Days Total Commitment
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-bold text-gray-900 tracking-tight flex items-center">
              <IndianRupee size={18} className="text-amber-600" />
              {commitments.grandTotal.toLocaleString("en-IN")}
            </span>
            <span className="text-xs text-gray-500">across 2 households</span>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 border-l border-orange-200 pl-6">
          <div className="bg-white/80 rounded-lg px-3 py-1.5 border border-orange-100 shadow-xs">
            <span className="text-[10px] text-gray-500 block">Parents' Bills & Insurance</span>
            <span className="text-xs font-semibold text-gray-800">
              ₹{commitments.parentsTotal.toLocaleString("en-IN")}
            </span>
          </div>

          <div className="bg-white/80 rounded-lg px-3 py-1.5 border border-orange-100 shadow-xs">
            <span className="text-[10px] text-gray-500 block">Earner's Loan EMIs</span>
            <span className="text-xs font-semibold text-rose-700">
              ₹{commitments.loanEmiTotal.toLocaleString("en-IN")}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-amber-900 bg-amber-100/70 border border-amber-200 rounded-full px-3 py-1">
        <TrendingUp size={13} className="text-amber-700" />
        <span>One phone, complete family cashflow clarity</span>
      </div>
    </div>
  );
}
