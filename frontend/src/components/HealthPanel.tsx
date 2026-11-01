"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getHealthSummary,
  createMedication,
  updateMedication,
  createThreshold,
  updateThreshold,
  type Member,
  type Medication,
  type VitalThreshold,
  type Vital,
  type DoseLog,
} from "@/lib/api";
import {
  HeartPulse,
  Pill,
  Clock,
  Plus,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronUp,
  Shield,
  Trash2,
} from "lucide-react";

interface HealthPanelProps {
  householdId: number;
  members: Member[];
}

export function HealthPanel({ householdId, members }: HealthPanelProps) {
  const queryClient = useQueryClient();

  const parents = members.filter((m) => m.role === "parent");
  const children = members.filter((m) => m.role === "child");

  // Summary query with 5s polling
  const { data: summary, isLoading } = useQuery({
    queryKey: ["healthSummary", householdId],
    queryFn: () => getHealthSummary(householdId),
    refetchInterval: 5000,
  });

  // State for toggles / forms
  const [expandedEvidence, setExpandedEvidence] = useState<Record<number, boolean>>({});
  const [isAddMedOpen, setIsAddMedOpen] = useState(false);
  const [isAddThreshOpen, setIsAddThreshOpen] = useState(false);

  // New Medication form state
  const [newMedParentId, setNewMedParentId] = useState<number>(parents[0]?.id || 0);
  const [newMedName, setNewMedName] = useState("");
  const [newMedDose, setNewMedDose] = useState("1 tablet");
  const [newMedTimes, setNewMedTimes] = useState("08:00, 20:00");
  const [newMedOwnerChildId, setNewMedOwnerChildId] = useState<number | undefined>(children[0]?.id);

  // New Threshold form state
  const [newThreshParentId, setNewThreshParentId] = useState<number>(parents[0]?.id || 0);
  const [newThreshKind, setNewThreshKind] = useState<"bp" | "sugar" | "weight" | "spo2" | "pulse" | "temperature">("bp");
  const [newThreshField, setNewThreshField] = useState<"value_1" | "value_2">("value_1");
  const [newThreshOp, setNewThreshOp] = useState<"gt" | "lt">("gt");
  const [newThreshLimit, setNewThreshLimit] = useState<number>(150);
  const [newThreshNote, setNewThreshNote] = useState("Doctor advised");

  // Mutations
  const addMedMutation = useMutation({
    mutationFn: () => {
      const timesList = newMedTimes
        .split(",")
        .map((t) => t.trim())
        .filter((t) => /^\d{2}:\d{2}$/.test(t));
      return createMedication({
        household_id: householdId,
        member_id: newMedParentId || (parents[0]?.id ?? 1),
        name: newMedName.trim(),
        dose_text: newMedDose.trim(),
        times: timesList.length > 0 ? timesList : ["08:00"],
        owner_child_id: newMedOwnerChildId || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
      setIsAddMedOpen(false);
      setNewMedName("");
    },
  });

  const toggleMedActiveMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      updateMedication(id, { active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
    },
  });

  const addThreshMutation = useMutation({
    mutationFn: () =>
      createThreshold({
        household_id: householdId,
        member_id: newThreshParentId || (parents[0]?.id ?? 1),
        kind: newThreshKind,
        field: newThreshField,
        op: newThreshOp,
        limit: Number(newThreshLimit),
        note: newThreshNote.trim(),
        set_by_member_id: children[0]?.id || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
      setIsAddThreshOpen(false);
    },
  });

  const deactivateThreshMutation = useMutation({
    mutationFn: (id: number) => updateThreshold(id, { active: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
    },
  });

  if (isLoading && !summary) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-gray-400 text-sm">
        Loading family health data…
      </div>
    );
  }

  const doses = summary?.todays_doses || [];
  const vitals = summary?.recent_vitals || [];
  const thresholds = summary?.active_thresholds || [];
  const medications = summary?.active_medications || [];

  // Group vitals by parent
  const vitalsByParent: Record<number, Vital[]> = {};
  for (const v of vitals) {
    if (!vitalsByParent[v.member_id]) {
      vitalsByParent[v.member_id] = [];
    }
    vitalsByParent[v.member_id].push(v);
  }

  // Helper for Member name
  const getMemberName = (id: number) => members.find((m) => m.id === id)?.name || `Member #${id}`;

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50/50 p-6 space-y-6">
      {/* 1. Today's Medicines */}
      <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <Pill size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Today's Medicines (आजची औषधे)</h2>
              <p className="text-xs text-gray-500">Live dose schedule & WhatsApp reminder status</p>
            </div>
          </div>
          <span className="text-xs text-gray-400">Live (5s poll)</span>
        </div>

        {doses.length === 0 ? (
          <p className="text-xs text-gray-400 py-3 italic">No doses scheduled for today.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {doses.map((d) => {
              const timeStr = d.scheduled_for ? new Date(d.scheduled_for).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
              return (
                <div key={d.id} className="py-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-gray-800">{d.member_name || "Parent"}</span>
                    <span className="text-gray-400">•</span>
                    <span className="text-gray-700 font-medium">{d.medication_name || "Medicine"}</span>
                    <span className="text-gray-400">•</span>
                    <span className="flex items-center gap-1 text-gray-500">
                      <Clock size={12} />
                      {timeStr}
                    </span>
                  </div>
                  <div>
                    {d.status === "taken" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                        <CheckCircle2 size={12} /> taken ✅
                      </span>
                    )}
                    {d.status === "pending" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                        <Clock size={12} /> pending
                      </span>
                    )}
                    {d.status === "missed" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-100 text-red-800 border border-red-200">
                        <AlertTriangle size={12} /> missed ⚠️ (escalated)
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 2. Readings & Charts (14 Days) */}
      <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-2xs space-y-6">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center">
            <HeartPulse size={18} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">Health Readings (मागील १४ दिवस)</h2>
            <p className="text-xs text-gray-500">Reported via WhatsApp voice notes & messages with verbatim evidence</p>
          </div>
        </div>

        {parents.length === 0 ? (
          <p className="text-xs text-gray-400">No parents registered in household.</p>
        ) : (
          parents.map((parent) => {
            const pVitals = vitalsByParent[parent.id] || [];
            const bpVitals = pVitals.filter((v) => v.kind === "bp");
            const bpThreshold = thresholds.find((th) => th.member_id === parent.id && th.kind === "bp");

            return (
              <div key={parent.id} className="border border-gray-100 rounded-xl p-5 bg-slate-50/40 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-gray-800 flex items-center gap-2">
                    <span>{parent.name}</span>
                    <span className="text-[11px] font-normal text-gray-500">({pVitals.length} readings)</span>
                  </h3>
                </div>

                {/* Inline SVG Chart for Blood Pressure */}
                {bpVitals.length > 0 && (
                  <div className="bg-white rounded-xl p-4 border border-gray-200 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-gray-700">Blood Pressure Trend (BP ट्रेंड)</span>
                      <div className="flex items-center gap-4 text-[11px] text-gray-500">
                        <span className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Systolic
                        </span>
                        <span className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Diastolic
                        </span>
                        {bpThreshold && (
                          <span className="flex items-center gap-1.5 text-rose-600 font-medium">
                            <span className="w-3 border-b-2 border-dashed border-rose-500"></span> Family limit ({bpThreshold.limit})
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="w-full overflow-x-auto py-2">
                      <BPLineChart vitals={bpVitals} threshold={bpThreshold} />
                    </div>
                  </div>
                )}

                {/* Vitals List */}
                {pVitals.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">No vitals logged in last 14 days.</p>
                ) : (
                  <div className="space-y-2">
                    {pVitals.map((v) => {
                      const isExpanded = expandedEvidence[v.id] || false;
                      const dateStr = new Date(v.measured_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      });
                      const readingVal = v.kind === "bp" ? `${v.value_1}/${v.value_2} ${v.unit}` : `${v.value_1} ${v.unit}`;

                      return (
                        <div key={v.id} className="bg-white rounded-lg border border-gray-200 p-3 text-xs space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded-md bg-gray-100 text-gray-700">
                                {v.kind}
                              </span>
                              <span className="font-bold text-gray-900 text-sm">{readingVal}</span>
                              <span className="text-gray-400">•</span>
                              <span className="text-gray-500 text-[11px]">{dateStr}</span>
                            </div>
                            <button
                              onClick={() => setExpandedEvidence((prev) => ({ ...prev, [v.id]: !isExpanded }))}
                              className="flex items-center gap-1 text-[11px] text-brand-600 hover:text-brand-800 font-medium cursor-pointer"
                            >
                              <FileText size={12} />
                              {isExpanded ? "Hide source" : "Evidence"}
                              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          </div>

                          {isExpanded && (
                            <div className="p-2.5 rounded-md bg-amber-50 border border-amber-200/60 text-amber-900 text-[11px]">
                              <span className="font-semibold">Quoted Source span:</span> &ldquo;{v.quote}&rdquo;
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </section>

      {/* 3. Family Limits (Thresholds) */}
      <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
              <Shield size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Family Limits (कुटुंबाने ठरवलेली मर्यादा)</h2>
              <p className="text-xs text-gray-500">Alerts siblings when readings cross limits set by family doctor</p>
            </div>
          </div>
          <button
            onClick={() => setIsAddThreshOpen(!isAddThreshOpen)}
            className="flex items-center gap-1 text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-3 py-1.5 transition-colors cursor-pointer"
          >
            <Plus size={14} />
            Add Limit
          </button>
        </div>

        {isAddThreshOpen && (
          <div className="border border-brand-200 rounded-xl p-4 bg-brand-50/40 space-y-3 text-xs">
            <h4 className="font-bold text-gray-800">Add New Family Limit</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Parent</label>
                <select
                  value={newThreshParentId}
                  onChange={(e) => setNewThreshParentId(Number(e.target.value))}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  {parents.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Kind</label>
                <select
                  value={newThreshKind}
                  onChange={(e) => setNewThreshKind(e.target.value as any)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  <option value="bp">Blood Pressure (BP)</option>
                  <option value="sugar">Blood Sugar</option>
                  <option value="weight">Weight</option>
                  <option value="spo2">SpO2</option>
                  <option value="pulse">Pulse</option>
                  <option value="temperature">Temperature</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Field</label>
                <select
                  value={newThreshField}
                  onChange={(e) => setNewThreshField(e.target.value as any)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  <option value="value_1">Systolic / Primary (value_1)</option>
                  <option value="value_2">Diastolic (value_2)</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Comparison</label>
                <select
                  value={newThreshOp}
                  onChange={(e) => setNewThreshOp(e.target.value as any)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  <option value="gt">&gt; (Greater than)</option>
                  <option value="lt">&lt; (Less than)</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Limit Value</label>
                <input
                  type="number"
                  value={newThreshLimit}
                  onChange={(e) => setNewThreshLimit(Number(e.target.value))}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Note</label>
                <input
                  type="text"
                  placeholder="e.g. Doctor advised"
                  value={newThreshNote}
                  onChange={(e) => setNewThreshNote(e.target.value)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsAddThreshOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => addThreshMutation.mutate()}
                disabled={addThreshMutation.isPending}
                className="px-3 py-1.5 rounded-lg bg-brand-600 text-white font-semibold hover:bg-brand-700 cursor-pointer"
              >
                Save Limit
              </button>
            </div>
          </div>
        )}

        {thresholds.length === 0 ? (
          <p className="text-xs text-gray-400 py-2 italic">No family limits configured.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {thresholds.map((th) => (
              <div key={th.id} className="p-3 rounded-xl border border-gray-200 bg-gray-50/50 flex items-start justify-between text-xs">
                <div>
                  <div className="font-bold text-gray-800">{getMemberName(th.member_id)}</div>
                  <div className="text-gray-600 mt-0.5">
                    <span className="font-semibold uppercase tracking-wider">{th.kind}</span> ({th.field} {th.op === "gt" ? ">" : "<"} {th.limit})
                  </div>
                  {th.note && <div className="text-gray-400 text-[11px] mt-1 italic">&ldquo;{th.note}&rdquo;</div>}
                </div>
                <button
                  onClick={() => deactivateThreshMutation.mutate(th.id)}
                  title="Remove limit"
                  className="p-1 text-gray-400 hover:text-red-600 rounded transition-colors cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 4. Medicines Setup */}
      <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
              <Pill size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Medicines Setup (औषधांची माहिती)</h2>
              <p className="text-xs text-gray-500">Entered by children with reminder times and escalation owner</p>
            </div>
          </div>
          <button
            onClick={() => setIsAddMedOpen(!isAddMedOpen)}
            className="flex items-center gap-1 text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-3 py-1.5 transition-colors cursor-pointer"
          >
            <Plus size={14} />
            Add Medicine
          </button>
        </div>

        {isAddMedOpen && (
          <div className="border border-brand-200 rounded-xl p-4 bg-brand-50/40 space-y-3 text-xs">
            <h4 className="font-bold text-gray-800">Add New Medication</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Parent</label>
                <select
                  value={newMedParentId}
                  onChange={(e) => setNewMedParentId(Number(e.target.value))}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  {parents.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Medicine Name</label>
                <input
                  type="text"
                  placeholder="e.g. सकाळची गोळी / Metformin"
                  value={newMedName}
                  onChange={(e) => setNewMedName(e.target.value)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Dose Text</label>
                <input
                  type="text"
                  placeholder="e.g. 1 tablet"
                  value={newMedDose}
                  onChange={(e) => setNewMedDose(e.target.value)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Times (HH:MM, comma-separated)</label>
                <input
                  type="text"
                  placeholder="08:00, 20:00"
                  value={newMedTimes}
                  onChange={(e) => setNewMedTimes(e.target.value)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block text-gray-600 mb-1 font-medium">Owner Child (for missed dose alerts)</label>
                <select
                  value={newMedOwnerChildId || ""}
                  onChange={(e) => setNewMedOwnerChildId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full bg-white border border-gray-200 rounded-lg p-2"
                >
                  <option value="">All Children</option>
                  {children.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsAddMedOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => addMedMutation.mutate()}
                disabled={addMedMutation.isPending || !newMedName.trim()}
                className="px-3 py-1.5 rounded-lg bg-brand-600 text-white font-semibold hover:bg-brand-700 cursor-pointer disabled:opacity-50"
              >
                Save Medicine
              </button>
            </div>
          </div>
        )}

        {medications.length === 0 ? (
          <p className="text-xs text-gray-400 py-2 italic">No active medications registered.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {medications.map((m) => (
              <div key={m.id} className="py-3 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-gray-900 flex items-center gap-2">
                    <span>{m.name}</span>
                    <span className="text-[11px] font-normal text-gray-500">({m.dose_text})</span>
                  </div>
                  <div className="text-gray-500 text-[11px] mt-0.5 flex items-center gap-2">
                    <span>Parent: {getMemberName(m.member_id)}</span>
                    <span>•</span>
                    <span>Times: {m.times.join(", ")}</span>
                    {m.owner_child_id && (
                      <>
                        <span>•</span>
                        <span>Alerts to: {getMemberName(m.owner_child_id)}</span>
                      </>
                    )}
                  </div>
                </div>
                <div>
                  <button
                    onClick={() => toggleMedActiveMutation.mutate({ id: m.id, active: !m.active })}
                    className="text-[11px] px-2.5 py-1 rounded-md border border-gray-200 hover:bg-gray-100 font-medium text-gray-600 cursor-pointer"
                  >
                    Deactivate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 5. Footer Medical Disclaimer */}
      <footer className="pt-4 border-t border-gray-200 text-center">
        <p className="text-xs text-gray-400">
          Saath records what your family reports. It does not give medical advice.
        </p>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hand-written inline SVG Line Chart for Blood Pressure (no chart dependencies)
// ---------------------------------------------------------------------------
function BPLineChart({ vitals, threshold }: { vitals: Vital[]; threshold?: VitalThreshold }) {
  const sorted = [...vitals].sort(
    (a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime()
  );

  const width = 500;
  const height = 140;
  const paddingX = 40;
  const paddingY = 20;

  const yMin = 50;
  const yMax = 190;

  const mapX = (index: number) => {
    if (sorted.length <= 1) return width / 2;
    return paddingX + (index / (sorted.length - 1)) * (width - paddingX * 2);
  };

  const mapY = (val: number) => {
    const clamped = Math.max(yMin, Math.min(yMax, val));
    return height - paddingY - ((clamped - yMin) / (yMax - yMin)) * (height - paddingY * 2);
  };

  const sysPoints = sorted.map((v, idx) => `${mapX(idx)},${mapY(Number(v.value_1))}`).join(" ");
  const diaPoints = sorted
    .filter((v) => v.value_2 !== null)
    .map((v, idx) => `${mapX(idx)},${mapY(Number(v.value_2))}`)
    .join(" ");

  const threshY = threshold ? mapY(Number(threshold.limit)) : null;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36 font-sans">
      {/* Grid Lines */}
      {[60, 90, 120, 150, 180].map((level) => (
        <g key={level}>
          <line
            x1={paddingX}
            y1={mapY(level)}
            x2={width - paddingX}
            y2={mapY(level)}
            stroke="#f1f5f9"
            strokeWidth="1"
          />
          <text x={paddingX - 6} y={mapY(level) + 3} textAnchor="end" fontSize="9" fill="#94a3b8">
            {level}
          </text>
        </g>
      ))}

      {/* Threshold line if present */}
      {threshY !== null && threshold && (
        <g>
          <line
            x1={paddingX}
            y1={threshY}
            x2={width - paddingX}
            y2={threshY}
            stroke="#f43f5e"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
          <text
            x={width - paddingX}
            y={threshY - 4}
            textAnchor="end"
            fontSize="9"
            fontWeight="bold"
            fill="#e11d48"
          >
            Family limit: {threshold.limit}
          </text>
        </g>
      )}

      {/* Systolic Polyline (Red/Rose) */}
      <polyline fill="none" stroke="#f43f5e" strokeWidth="2.5" points={sysPoints} />
      {sorted.map((v, idx) => (
        <circle
          key={`sys-${idx}`}
          cx={mapX(idx)}
          cy={mapY(Number(v.value_1))}
          r="3.5"
          fill="#f43f5e"
          stroke="#ffffff"
          strokeWidth="1.5"
        />
      ))}

      {/* Diastolic Polyline (Blue) */}
      {diaPoints && (
        <>
          <polyline fill="none" stroke="#3b82f6" strokeWidth="2.5" points={diaPoints} />
          {sorted
            .filter((v) => v.value_2 !== null)
            .map((v, idx) => (
              <circle
                key={`dia-${idx}`}
                cx={mapX(idx)}
                cy={mapY(Number(v.value_2))}
                r="3.5"
                fill="#3b82f6"
                stroke="#ffffff"
                strokeWidth="1.5"
              />
            ))}
        </>
      )}

      {/* X Axis Labels */}
      {sorted.map((v, idx) => {
        const d = new Date(v.measured_at);
        const label = `${d.getDate()}/${d.getMonth() + 1}`;
        return (
          <text
            key={`lbl-${idx}`}
            x={mapX(idx)}
            y={height - 4}
            textAnchor="middle"
            fontSize="9"
            fill="#64748b"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}
