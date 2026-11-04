"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getHealthSummary,
  createMedication,
  updateMedication,
  createThreshold,
  updateThreshold,
  postDeviceVital,
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
  Watch,
} from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { isWebBluetoothAvailable, connectHeartRate } from "@/lib/heartRate";

interface HealthPanelProps {
  householdId: number;
  members: Member[];
}

export function HealthPanel({ householdId, members }: HealthPanelProps) {
  const queryClient = useQueryClient();
  const { t } = useI18n();

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

  // Watch state (Web Bluetooth H-8)
  const [isBluetoothSupported, setIsBluetoothSupported] = useState(false);
  const [isConnectingWatch, setIsConnectingWatch] = useState(false);
  const [watchDeviceName, setWatchDeviceName] = useState<string | null>(null);
  const [watchDisconnectFn, setWatchDisconnectFn] = useState<(() => void) | null>(null);
  const [liveBpm, setLiveBpm] = useState<number | null>(null);
  const [announcedBpm, setAnnouncedBpm] = useState<number | null>(null);
  const [watchParentId, setWatchParentId] = useState<number>(parents[0]?.id || 0);
  const [watchStatusMessage, setWatchStatusMessage] = useState<string | null>(null);
  const lastSentRef = useRef<number>(0);
  const lastAnnouncedRef = useRef<number>(0);

  useEffect(() => {
    setIsBluetoothSupported(isWebBluetoothAvailable());
  }, []);

  useEffect(() => {
    if (!watchParentId && parents[0]?.id) {
      setWatchParentId(parents[0].id);
    }
  }, [parents, watchParentId]);

  const handleConnectWatch = async () => {
    setIsConnectingWatch(true);
    setWatchStatusMessage(null);
    try {
      const conn = await connectHeartRate(
        (bpm) => {
          setLiveBpm(bpm);
          const now = Date.now();
          if (now - lastAnnouncedRef.current >= 30000) {
            lastAnnouncedRef.current = now;
            setAnnouncedBpm(bpm);
          }
          const targetPid = watchParentId || parents[0]?.id;
          if (now - lastSentRef.current >= 5000 && targetPid) {
            lastSentRef.current = now;
            postDeviceVital(householdId, {
              member_id: targetPid,
              kind: "pulse",
              value: bpm,
              device_name: conn.deviceName,
            })
              .then((res) => {
                if (res.stored) {
                  queryClient.invalidateQueries({ queryKey: ["healthSummary", householdId] });
                }
              })
              .catch(() => {});
          }
        },
        () => {
          setWatchDeviceName(null);
          setWatchDisconnectFn(null);
          setLiveBpm(null);
          setWatchStatusMessage(t("watch_disconnected"));
        }
      );
      setWatchDeviceName(conn.deviceName);
      setWatchDisconnectFn(() => conn.disconnect);
      setWatchStatusMessage(t("watch_connected"));
    } catch (err: any) {
      if (err?.name !== "NotFoundError") {
        setWatchStatusMessage(err?.message || "Failed to connect watch");
      }
    } finally {
      setIsConnectingWatch(false);
    }
  };

  const handleDisconnectWatch = () => {
    if (watchDisconnectFn) {
      try {
        watchDisconnectFn();
      } catch (err) {
        console.error("Disconnect error:", err);
      }
    }
    setWatchDeviceName(null);
    setWatchDisconnectFn(null);
    setLiveBpm(null);
    setWatchStatusMessage(t("watch_disconnected"));
  };

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
    <div className="flex-1 overflow-y-auto bg-khata-canvas p-6 space-y-6">
      {/* 1. Today's Medicines */}
      <section className="bg-white rounded-2xl border border-khata-subtle p-6 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sage-100 text-sage-800 border border-sage-200 flex items-center justify-center shadow-2xs">
              <Pill size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-khata-ink">{t("todays_medicines")}</h2>
              <p className="text-xs text-khata-muted font-medium">Live dose schedule & WhatsApp reminder status</p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-khata-muted bg-khata-raised border border-khata-subtle px-2 py-0.5 rounded-md">Live (5s poll)</span>
        </div>

        {doses.length === 0 ? (
          <p className="text-xs text-khata-muted py-3 italic">No doses scheduled for today.</p>
        ) : (
          <div className="divide-y divide-khata-subtle">
            {doses.map((d) => {
              const timeStr = d.scheduled_for ? new Date(d.scheduled_for).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
              return (
                <div key={d.id} className="py-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-khata-ink">{d.member_name || "Parent"}</span>
                    <span className="text-khata-muted">•</span>
                    <span className="text-khata-ink font-medium">{d.medication_name || "Medicine"}</span>
                    <span className="text-khata-muted">•</span>
                    <span className="flex items-center gap-1 text-khata-muted font-mono">
                      <Clock size={12} />
                      {timeStr}
                    </span>
                  </div>
                  <div>
                    {d.status === "taken" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold font-mono bg-sage-100 text-sage-800 border border-sage-200 shadow-2xs">
                        <CheckCircle2 size={12} /> taken
                      </span>
                    )}
                    {d.status === "pending" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold font-mono bg-ochre-100 text-ochre-800 border border-ochre-200 shadow-2xs">
                        <Clock size={12} /> pending
                      </span>
                    )}
                    {d.status === "missed" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold font-mono bg-sindoor-100 text-sindoor-800 border border-sindoor-200 shadow-2xs">
                        <AlertTriangle size={12} /> missed (escalated)
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
      <section className="bg-white rounded-2xl border border-khata-subtle p-6 shadow-2xs space-y-6">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sindoor-100 text-sindoor-700 border border-sindoor-200 flex items-center justify-center shadow-2xs">
            <HeartPulse size={18} />
          </div>
          <div>
            <h2 className="text-base font-bold text-khata-ink">{t("vitals_14_days")}</h2>
            <p className="text-xs text-khata-muted font-medium">Reported via WhatsApp voice notes & messages with verbatim evidence</p>
          </div>
        </div>

        {/* Live Watch Connection (Web Bluetooth H-8) */}
        <div className="border border-khata-subtle rounded-xl p-4 bg-white shadow-2xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-sindoor-50 text-sindoor-700 border border-sindoor-100 flex items-center justify-center shrink-0">
                <Watch size={20} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-khata-ink">{t("live_heart_rate")}</h3>
                  {watchDeviceName && (
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                      {watchDeviceName}
                    </span>
                  )}
                </div>
                <p className="text-xs text-khata-muted">
                  {watchDeviceName
                    ? `${t("watch_connected")} (${parents.find((p) => p.id === watchParentId)?.name || ""})`
                    : t("wearing_watch")}
                </p>
              </div>
            </div>

            {!isBluetoothSupported ? (
              <p className="text-xs text-khata-muted italic max-w-xs">{t("watch_not_supported")}</p>
            ) : watchDeviceName ? (
              <div className="flex items-center gap-4">
                <div className="flex items-baseline gap-1.5 bg-sindoor-50/60 border border-sindoor-200/80 px-4 py-1.5 rounded-xl">
                  <span className="text-4xl font-extrabold text-sindoor-700 font-mono tabular-nums leading-none">
                    {liveBpm ?? "--"}
                  </span>
                  <span className="text-xs font-bold text-khata-muted">BPM</span>
                </div>
                <div aria-live="polite" className="sr-only">
                  {announcedBpm ? `Current heart rate: ${announcedBpm} beats per minute` : ""}
                </div>
                <button
                  type="button"
                  onClick={handleDisconnectWatch}
                  className="px-3.5 py-2 text-xs font-bold text-khata-ink bg-khata-raised hover:bg-khata-subtle border border-khata-subtle rounded-lg transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sindoor-500 focus-visible:ring-offset-2"
                >
                  {t("disconnect_watch")}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                {parents.length > 1 && (
                  <select
                    value={watchParentId}
                    onChange={(e) => setWatchParentId(Number(e.target.value))}
                    aria-label={t("wearing_watch")}
                    className="text-xs border border-khata-subtle rounded-lg px-2.5 py-2 bg-white text-khata-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sindoor-500"
                  >
                    {parents.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  onClick={handleConnectWatch}
                  disabled={isConnectingWatch || parents.length === 0}
                  className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-sindoor-600 hover:bg-sindoor-700 disabled:opacity-50 rounded-lg shadow-2xs transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sindoor-500 focus-visible:ring-offset-2"
                >
                  <Watch size={14} />
                  <span>{isConnectingWatch ? "Connecting…" : t("connect_watch")}</span>
                </button>
              </div>
            )}
          </div>
          {watchStatusMessage && (
            <p className="text-[11px] text-khata-muted font-medium pt-1 border-t border-khata-subtle/50">
              {watchStatusMessage}
            </p>
          )}
        </div>

        {parents.length === 0 ? (
          <p className="text-xs text-khata-muted">No parents registered in household.</p>
        ) : (
          parents.map((parent) => {
            const pVitals = vitalsByParent[parent.id] || [];
            const bpVitals = pVitals.filter((v) => v.kind === "bp");
            const bpThreshold = thresholds.find((th) => th.member_id === parent.id && th.kind === "bp");

            return (
              <div key={parent.id} className="border border-khata-subtle rounded-xl p-5 bg-khata-raised/40 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-khata-ink flex items-center gap-2">
                    <span>{parent.name}</span>
                    <span className="text-[11px] font-normal text-khata-muted font-mono">({pVitals.length} readings)</span>
                  </h3>
                </div>

                {/* Inline SVG Chart for Blood Pressure */}
                {bpVitals.length > 0 && (
                  <div className="bg-white rounded-xl p-4 border border-khata-subtle space-y-2 shadow-2xs">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-khata-ink">Blood Pressure Trend (BP ट्रेंड)</span>
                      <div className="flex items-center gap-4 text-[11px] text-khata-muted font-medium">
                        <span className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-sindoor-600"></span> Systolic
                        </span>
                        <span className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span> Diastolic
                        </span>
                        {bpThreshold && (
                          <span className="flex items-center gap-1.5 text-sindoor-700 font-semibold font-mono">
                            <span className="w-3 border-b-2 border-dashed border-sindoor-500"></span> Family limit ({bpThreshold.limit})
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
                  <p className="text-xs text-khata-muted italic">No vitals logged in last 14 days.</p>
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
                        <div key={v.id} className="bg-white rounded-lg border border-khata-subtle p-3 text-xs space-y-2 shadow-2xs">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                              <span className="font-mono font-bold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded-md bg-khata-raised text-khata-ink border border-khata-subtle">
                                {v.kind}
                              </span>
                              {v.source === "watch" && (
                                <span className="font-medium text-[10px] px-2 py-0.5 rounded-md bg-amber-100 text-amber-900 border border-amber-200">
                                  {t("from_watch")}
                                </span>
                              )}
                              <span className="font-mono font-bold text-khata-ink text-sm tabular-nums">{readingVal}</span>
                              <span className="text-khata-muted">•</span>
                              <span className="text-khata-muted font-mono text-[11px]">{dateStr}</span>
                            </div>
                            <button
                              onClick={() => setExpandedEvidence((prev) => ({ ...prev, [v.id]: !isExpanded }))}
                              className="flex items-center gap-1 text-[11px] text-brand-600 hover:text-brand-700 font-bold cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sindoor-500 rounded"
                            >
                              <FileText size={12} />
                              {isExpanded ? "Hide source" : "Evidence"}
                              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          </div>

                          {isExpanded && (
                            <div className="verbatim-box p-2.5 rounded-md bg-ochre-50/70 border border-ochre-200/80 text-ochre-900 text-xs font-mono">
                              <span className="font-sans font-bold">
                                {v.source === "watch" ? "Device:" : "Quoted Source span:"}
                              </span>{" "}
                              &ldquo;{v.quote}&rdquo;
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
      <section className="bg-white rounded-2xl border border-khata-subtle p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-ochre-100 text-ochre-800 border border-ochre-200 flex items-center justify-center shadow-2xs">
              <Shield size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-khata-ink">{t("family_limits")}</h2>
              <p className="text-xs text-khata-muted font-medium">Alerts siblings when readings cross limits set by family doctor</p>
            </div>
          </div>
          <button
            onClick={() => setIsAddThreshOpen(!isAddThreshOpen)}
            className="flex items-center gap-1.5 text-xs font-semibold bg-white hover:bg-khata-raised text-khata-ink border border-khata-subtle rounded-lg px-3 py-1.5 transition-colors cursor-pointer shadow-2xs"
          >
            <Plus size={14} className="text-brand-600" />
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
          <p className="text-xs text-khata-muted py-2 italic">No family limits configured.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {thresholds.map((th) => (
              <div key={th.id} className="p-3 rounded-xl border border-khata-subtle bg-khata-raised/40 flex items-start justify-between text-xs shadow-2xs">
                <div>
                  <div className="font-bold text-khata-ink">{getMemberName(th.member_id)}</div>
                  <div className="text-khata-ink mt-0.5 font-mono text-[11px]">
                    <span className="font-bold uppercase tracking-wider text-ochre-800 bg-ochre-100 px-1.5 py-0.5 rounded mr-1">{th.kind}</span> ({th.field} {th.op === "gt" ? ">" : "<"} {th.limit})
                  </div>
                  {th.note && <div className="text-khata-muted text-[11px] mt-1 italic">&ldquo;{th.note}&rdquo;</div>}
                </div>
                <button
                  onClick={() => deactivateThreshMutation.mutate(th.id)}
                  title="Remove limit"
                  className="p-1 text-khata-muted hover:text-sindoor-600 rounded transition-colors cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 4. Medicines Setup */}
      <section className="bg-white rounded-2xl border border-khata-subtle p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-100 text-brand-700 border border-brand-200 flex items-center justify-center shadow-2xs">
              <Pill size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-khata-ink">{t("medicines_setup")}</h2>
              <p className="text-xs text-khata-muted font-medium">Entered by children with reminder times and escalation owner</p>
            </div>
          </div>
          <button
            onClick={() => setIsAddMedOpen(!isAddMedOpen)}
            className="flex items-center gap-1.5 text-xs font-semibold bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-lg px-3 py-1.5 transition-all cursor-pointer shadow-2xs"
          >
            <Plus size={14} />
            Add Medicine
          </button>
        </div>

        {isAddMedOpen && (
          <div className="border border-brand-200 rounded-xl p-4 bg-brand-50/40 space-y-3 text-xs shadow-2xs">
            <h4 className="font-bold text-khata-ink">Add New Medication</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-khata-ink mb-1 font-semibold text-[11px]">Parent</label>
                <select
                  value={newMedParentId}
                  onChange={(e) => setNewMedParentId(Number(e.target.value))}
                  className="w-full bg-white border border-khata-subtle rounded-lg p-2 text-khata-ink"
                >
                  {parents.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-khata-ink mb-1 font-semibold text-[11px]">Medicine Name</label>
                <input
                  type="text"
                  placeholder="e.g. सकाळची गोळी / Metformin"
                  value={newMedName}
                  onChange={(e) => setNewMedName(e.target.value)}
                  className="w-full bg-white border border-khata-subtle rounded-lg p-2 text-khata-ink"
                />
              </div>
              <div>
                <label className="block text-khata-ink mb-1 font-semibold text-[11px]">Dose Text</label>
                <input
                  type="text"
                  placeholder="e.g. 1 tablet"
                  value={newMedDose}
                  onChange={(e) => setNewMedDose(e.target.value)}
                  className="w-full bg-white border border-khata-subtle rounded-lg p-2 text-khata-ink"
                />
              </div>
              <div>
                <label className="block text-khata-ink mb-1 font-semibold text-[11px]">Times (HH:MM, comma-separated)</label>
                <input
                  type="text"
                  placeholder="08:00, 20:00"
                  value={newMedTimes}
                  onChange={(e) => setNewMedTimes(e.target.value)}
                  className="w-full bg-white border border-khata-subtle rounded-lg p-2 text-khata-ink font-mono"
                />
              </div>
              <div>
                <label className="block text-khata-ink mb-1 font-semibold text-[11px]">Owner Child (for missed dose alerts)</label>
                <select
                  value={newMedOwnerChildId || ""}
                  onChange={(e) => setNewMedOwnerChildId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full bg-white border border-khata-subtle rounded-lg p-2 text-khata-ink"
                >
                  <option value="">All Children</option>
                  {children.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <p className="mt-1 text-[10px] text-khata-muted">{t("guardians_also_alerted")}</p>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsAddMedOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-khata-subtle text-khata-ink hover:bg-khata-raised cursor-pointer text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={() => addMedMutation.mutate()}
                disabled={addMedMutation.isPending || !newMedName.trim()}
                className="px-3.5 py-1.5 rounded-lg bg-brand-500 text-white font-bold hover:bg-brand-600 cursor-pointer disabled:opacity-50 text-xs shadow-2xs"
              >
                Save Medicine
              </button>
            </div>
          </div>
        )}

        {medications.length === 0 ? (
          <p className="text-xs text-khata-muted py-2 italic">No active medications registered.</p>
        ) : (
          <div className="divide-y divide-khata-subtle">
            {medications.map((m) => (
              <div key={m.id} className="py-3 flex items-center justify-between text-xs">
                <div>
                  <div className="font-bold text-khata-ink flex items-center gap-2">
                    <span>{m.name}</span>
                    <span className="text-[11px] font-normal text-khata-muted">({m.dose_text})</span>
                  </div>
                  <div className="text-khata-muted text-[11px] mt-0.5 flex items-center gap-2 font-mono">
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
                    className="text-[11px] px-2.5 py-1 rounded-md border border-khata-subtle hover:bg-khata-raised font-semibold text-khata-ink cursor-pointer shadow-2xs"
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
      <footer className="pt-4 border-t border-khata-subtle text-center">
        <p className="text-xs text-khata-muted font-medium">
          {t("health_disclaimer")}
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
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36 font-mono">
      {/* Grid Lines */}
      {[60, 90, 120, 150, 180].map((level) => (
        <g key={level}>
          <line
            x1={paddingX}
            y1={mapY(level)}
            x2={width - paddingX}
            y2={mapY(level)}
            stroke="#E8E3D8"
            strokeWidth="1"
          />
          <text x={paddingX - 6} y={mapY(level) + 3} textAnchor="end" fontSize="9" fill="#7D7566">
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
            stroke="#C92A2A"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
          <text
            x={width - paddingX}
            y={threshY - 4}
            textAnchor="end"
            fontSize="9"
            fontWeight="bold"
            fill="#C92A2A"
          >
            Family limit: {threshold.limit}
          </text>
        </g>
      )}

      {/* Systolic Polyline (Sindoor Crimson) */}
      <polyline fill="none" stroke="#C92A2A" strokeWidth="2.5" points={sysPoints} />
      {sorted.map((v, idx) => (
        <circle
          key={`sys-${idx}`}
          cx={mapX(idx)}
          cy={mapY(Number(v.value_1))}
          r="3.5"
          fill="#C92A2A"
          stroke="#ffffff"
          strokeWidth="1.5"
        />
      ))}

      {/* Diastolic Polyline (Deep Indigo) */}
      {diaPoints && (
        <>
          <polyline fill="none" stroke="#4338CA" strokeWidth="2.5" points={diaPoints} />
          {sorted
            .filter((v) => v.value_2 !== null)
            .map((v, idx) => (
              <circle
                key={`dia-${idx}`}
                cx={mapX(idx)}
                cy={mapY(Number(v.value_2))}
                r="3.5"
                fill="#4338CA"
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
            fill="#7D7566"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}

