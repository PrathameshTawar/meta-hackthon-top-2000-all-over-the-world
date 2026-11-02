"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { simulateIngest, getHealthSummary, simulateDoseNow, simulateSkipHealth } from "@/lib/api";
import { X, Play, Sparkles, Mic, FileText, ShieldAlert, CopyCheck, HeartPulse, Clock, FastForward, Pill } from "lucide-react";
import clsx from "clsx";

interface SimulateModalProps {
  householdId: number;
  isOpen: boolean;
  onClose: () => void;
}

const PRESETS = [
  {
    title: "1. Parent Marathi Voice Note (Electricity Bill)",
    type: "voice",
    icon: Mic,
    color: "border-ochre-300 bg-ochre-50/40 hover:bg-ochre-50/70",
    text: "रोहन, महावितरणचे वीज बिल आले आहे. रक्कम ₹१,८४० आहे. ३ नोव्हेंबर पर्यंत भरायचे आहे.",
    note: "Extracts amount, payee, due date + quotes, translates reply to Marathi",
  },
  {
    title: "2. Earner Education Loan Notice (Rohan)",
    type: "image",
    icon: FileText,
    color: "border-brand-300 bg-brand-50/40 hover:bg-brand-50/70",
    text: "HDFC CREDILA FINANCIAL SERVICES. Monthly Education Loan EMI: INR 18,500. Due Date: 2026-11-10. Payee: HDFC Bank. Borrower: Rohan Kulkarni.",
    note: "Auto-assigned to Rohan; updates 30-day family financial total",
  },
  {
    title: "3. Medical Report (Guardrail Test)",
    type: "image",
    icon: ShieldAlert,
    color: "border-sindoor-300 bg-sindoor-50/40 hover:bg-sindoor-50/70",
    text: "DR LAL PATHLABS CLINICAL BIOCHEMISTRY REPORT. Fasting Glucose: 172 mg/dL. HbA1c: 8.1%. Consultation on 2026-11-08 at Sahyadri Hospital.",
    note: "Blocks diagnostic advice; records appointment logistics only; sends refusal reply",
  },
  {
    title: "4. Duplicate Bill Photo (Deduplication Test)",
    type: "image",
    icon: CopyCheck,
    color: "border-khata-subtle bg-white hover:bg-khata-raised/60",
    text: "MSEDCL Electricity Bill. Amount: ₹1,840. Due Date: 2026-11-03. Payee: Mahavitaran (MSEDCL). Duplicate invoice submission.",
    note: "Matches existing bill; merges evidence instead of creating a duplicate task",
  },
  {
    title: "5. Parent Voice: Blood Pressure Reading (Vitals)",
    type: "voice",
    icon: HeartPulse,
    color: "border-sage-300 bg-sage-50/40 hover:bg-sage-50/70",
    text: "आज बीपी १५०/९५ आहे",
    note: "Extracts BP 150/95, validates verbatim quote, checks family limit (value_1 > 150) and alerts child",
  },
];

export function SimulateModal({ householdId, isOpen, onClose }: SimulateModalProps) {
  const queryClient = useQueryClient();
  const [selectedText, setSelectedText] = useState(PRESETS[0].text);
  const [selectedType, setSelectedType] = useState(PRESETS[0].type);
  const [selectedMedId, setSelectedMedId] = useState<number | undefined>(undefined);
  const [healthActionMessage, setHealthActionMessage] = useState<string | null>(null);

  const { data: healthSummary } = useQuery({
    queryKey: ["healthSummary", householdId],
    queryFn: () => getHealthSummary(householdId),
    enabled: isOpen,
  });

  const medications = healthSummary?.active_medications || [];

  const ingestMutation = useMutation({
    mutationFn: () => simulateIngest({ type: selectedType, raw_text: selectedText, household_id: householdId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", householdId] });
      queryClient.invalidateQueries({ queryKey: ["events", householdId] });
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
      // Accelerated follow-up polls as agent finishes node execution
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["tasks", householdId] }), 600);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["tasks", householdId] }), 1400);
      onClose();
    },
  });

  const doseNowMutation = useMutation({
    mutationFn: (medId: number) => simulateDoseNow(medId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
      setHealthActionMessage("✅ Dose reminder sent to parent immediately!");
      setTimeout(() => setHealthActionMessage(null), 3500);
    },
  });

  const skipHealthMutation = useMutation({
    mutationFn: () => simulateSkipHealth(120),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
      setHealthActionMessage(`⚡ Advanced 2 hours: ${res.escalated_doses_count} missed dose(s) escalated to child!`);
      setTimeout(() => setHealthActionMessage(null), 3500);
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-khata-subtle">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-khata-subtle bg-khata-raised/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-600 shadow-2xs">
              <Sparkles size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-khata-ink">Try Live Agent Demo</h2>
              <p className="text-xs text-khata-muted font-medium">Feed voice transcript or document OCR into LangGraph</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-khata-muted hover:text-khata-ink rounded-lg hover:bg-white border border-transparent hover:border-khata-subtle transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Presets */}
        <div className="p-6 space-y-4 overflow-y-auto bg-khata-canvas/20">
          <label className="text-[11px] font-bold uppercase tracking-wider text-khata-muted block">
            Select a Demo Scenario
          </label>
          <div className="grid grid-cols-1 gap-2.5">
            {PRESETS.map((p, idx) => {
              const Icon = p.icon;
              const isSelected = selectedText === p.text;
              return (
                <button
                  key={idx}
                  onClick={() => {
                    setSelectedText(p.text);
                    setSelectedType(p.type);
                  }}
                  className={clsx(
                    "text-left p-3 rounded-xl border transition-all cursor-pointer flex items-start gap-3 shadow-2xs",
                    isSelected ? "border-brand-500 ring-2 ring-brand-500/20 bg-brand-50/40" : p.color
                  )}
                >
                  <div className="p-2 rounded-lg bg-white border border-khata-subtle shadow-2xs text-khata-ink mt-0.5">
                    <Icon size={16} />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-bold text-khata-ink">{p.title}</p>
                    <p className="text-[11px] text-khata-muted mt-0.5 font-medium">{p.note}</p>
                  </div>
                </button>
              );
            })}
          </div>

          <div>
            <label className="text-[11px] font-bold uppercase tracking-wider text-khata-muted block mb-1.5">
              Raw Text / Transcript Content (or Simulate Vital)
            </label>
            <textarea
              value={selectedText}
              onChange={(e) => setSelectedText(e.target.value)}
              rows={3}
              className="w-full text-xs font-mono p-3 rounded-xl border border-khata-subtle focus:outline-hidden focus:border-brand-500 focus:ring-1 focus:ring-brand-500 bg-white text-khata-ink shadow-2xs leading-relaxed"
            />
          </div>

          {/* Health Module Admin Tools */}
          <div className="border border-sage-200 rounded-xl p-4 bg-sage-50/40 space-y-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-khata-ink flex items-center gap-1.5">
                <Pill size={14} className="text-sage-700" />
                Health Module Simulation Tools (H-2 & H-3)
              </span>
              {healthActionMessage && (
                <span className="text-[11px] font-bold font-mono text-sage-800 bg-sage-100 px-2 py-0.5 rounded-md border border-sage-300">
                  {healthActionMessage}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {/* Send dose reminder now */}
              <div className="bg-white border border-sage-200/80 rounded-lg p-2.5 space-y-2 shadow-2xs">
                <label className="block text-[11px] font-bold text-khata-ink">
                  Send Dose Reminder Now
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={selectedMedId || medications[0]?.id || ""}
                    onChange={(e) => setSelectedMedId(Number(e.target.value))}
                    className="flex-1 text-xs border border-khata-subtle rounded-lg p-1.5 bg-khata-raised/30 text-khata-ink"
                  >
                    {medications.length === 0 ? (
                      <option value="">No active meds</option>
                    ) : (
                      medications.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.dose_text})
                        </option>
                      ))
                    )}
                  </select>
                  <button
                    onClick={() => {
                      const idToUse = selectedMedId || medications[0]?.id;
                      if (idToUse) doseNowMutation.mutate(idToUse);
                    }}
                    disabled={doseNowMutation.isPending || medications.length === 0}
                    className="px-2.5 py-1.5 rounded-lg bg-sage-600 text-white text-xs font-bold hover:bg-sage-700 disabled:opacity-50 cursor-pointer flex items-center gap-1 shrink-0 shadow-2xs active:scale-98"
                  >
                    <Clock size={12} />
                    Dose Now
                  </button>
                </div>
              </div>

              {/* Skip 2 hours */}
              <div className="bg-white border border-ochre-200/80 rounded-lg p-2.5 space-y-2 shadow-2xs">
                <label className="block text-[11px] font-bold text-khata-ink">
                  Adherence Escalation
                </label>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] text-khata-muted font-medium">
                    Advances clock +2h to test missed dose escalation
                  </span>
                  <button
                    onClick={() => skipHealthMutation.mutate()}
                    disabled={skipHealthMutation.isPending}
                    className="px-2.5 py-1.5 rounded-lg bg-ochre-700 text-white text-xs font-bold hover:bg-ochre-800 disabled:opacity-50 cursor-pointer flex items-center gap-1 shrink-0 shadow-2xs active:scale-98"
                  >
                    <FastForward size={12} />
                    Skip 2h
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-khata-subtle bg-khata-raised/50 flex items-center justify-between">
          <span className="text-[11px] font-mono text-khata-muted">
            Perceive ➔ Classify ➔ Extract ➔ Verify ➔ Dedupe ➔ Assign
          </span>
          <button
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending || !selectedText.trim()}
            className="flex items-center gap-1.5 text-xs font-bold bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-lg px-4 py-2 transition-all shadow-2xs cursor-pointer active:scale-98 disabled:opacity-50"
          >
            <Play size={14} />
            {ingestMutation.isPending ? "Processing Graph…" : "Run Agent Graph"}
          </button>
        </div>
      </div>
    </div>
  );
}
