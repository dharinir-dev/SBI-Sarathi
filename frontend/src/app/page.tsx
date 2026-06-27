"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// API Server URL
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface CustomerSummary {
  customer_id: string;
  name: string;
  city: string;
  language_pref: string;
  life_event_signals: string[];
}

interface CustomerDetails {
  customer_id: string;
  name: string;
  age: number;
  city: string;
  state: string;
  language_pref: string;
  kyc_status: string;
  risk_profile: string;
  monthly_balance_avg_6m: number[];
  existing_products: string[];
  annual_income?: number;
}

interface DetectedSignal {
  signal_type: string;
  confidence: number;
  reason: string;
}

interface QualificationResponse {
  customer_id: string;
  signal_type: string;
  propensity_score: number;
  suitability: string;
  recommended_product: string;
}

interface ConversationAgentResponse {
  message: string;
  intent: string;
  next_step: string;
  escalate: boolean;
}

interface MemoryStateResponse {
  customer_id: string;
  conversation_history: { role: string; content: string }[];
  current_stage: string;
  last_updated: string;
}

interface EscalationResponse {
  ticket_id: string;
  status: string;
  assigned_to: string;
}

interface EngageResponse {
  customer_id: string;
  signals: DetectedSignal[];
  qualification: QualificationResponse;
  conversation: ConversationAgentResponse;
  memory: MemoryStateResponse;
  escalation: EscalationResponse | null;
}

export default function Home() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [customerDetails, setCustomerDetails] = useState<CustomerDetails | null>(null);
  const [engageData, setEngageData] = useState<EngageResponse | null>(null);
  
  const [replyText, setReplyText] = useState("");
  const [loading, setLoading] = useState(false);
  const [engageLoading, setEngageLoading] = useState(false);
  const [replyLoading, setReplyLoading] = useState(false);
  const [escalateLoading, setEscalateLoading] = useState(false);
  const [manualReason, setManualReason] = useState("");
  const [showManualEscalateModal, setShowManualEscalateModal] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  const filteredCustomers = useMemo(() => {
    if (!searchQuery) {
      return customers;
    }
    const q = searchQuery.toLowerCase();
    return customers.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.customer_id.toLowerCase().includes(q) ||
        c.city.toLowerCase().includes(q) ||
        c.life_event_signals.some((s) => s.toLowerCase().includes(q))
    );
  }, [searchQuery, customers]);

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/customers`);
      if (res.ok) {
        const data = await res.json();
        setCustomers(data);
        if (data.length > 0) {
          setSelectedCustomerId((current) => current ?? data[0].customer_id);
        }
      }
    } catch (err) {
      console.error("Error fetching customers:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCustomerData = useCallback(async (id: string) => {
    setEngageLoading(true);
    try {
      // Load full customer details
      const detailRes = await fetch(`${API_BASE}/customers/${id}`);
      if (detailRes.ok) {
        const details = await detailRes.json();
        setCustomerDetails(details);
      }

      // Load engage data (this orchestrates the agents)
      const engageRes = await fetch(`${API_BASE}/engage/${id}`);
      if (engageRes.ok) {
        const engage = await engageRes.json();
        setEngageData(engage);
      }
    } catch (err) {
      console.error("Error loading customer engage details:", err);
    } finally {
      setEngageLoading(false);
    }
  }, []);

  // Fetch all customers on mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchCustomers();
  }, [fetchCustomers]);

  // Fetch details and engage data when selected customer changes
  useEffect(() => {
    if (selectedCustomerId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadCustomerData(selectedCustomerId);
    }
  }, [selectedCustomerId, loadCustomerData]);

  // Scroll to bottom of chat when history changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [engageData?.memory?.conversation_history]);

  const handleSendReply = async (message: string) => {
    if (!selectedCustomerId || !message.trim()) return;
    setReplyLoading(true);
    try {
      const res = await fetch(`${API_BASE}/conversation/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          user_message: message,
        }),
      });
      if (res.ok) {
        setReplyText("");
        // Reload engage data to get updated history, stage, and ticket
        await loadCustomerData(selectedCustomerId);
      }
    } catch (err) {
      console.error("Error sending reply:", err);
    } finally {
      setReplyLoading(false);
    }
  };

  const handleManualEscalate = async () => {
    if (!selectedCustomerId || !manualReason.trim()) return;
    setEscalateLoading(true);
    try {
      const res = await fetch(`${API_BASE}/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          reason: manualReason,
        }),
      });
      if (res.ok) {
        setManualReason("");
        setShowManualEscalateModal(false);
        await loadCustomerData(selectedCustomerId);
      }
    } catch (err) {
      console.error("Error escalating:", err);
    } finally {
      setEscalateLoading(false);
    }
  };

  const handleResetConversation = async () => {
    if (!selectedCustomerId) return;
    if (!confirm("Are you sure you want to reset the conversation and ticket?")) return;
    setEngageLoading(true);
    try {
      const res = await fetch(`${API_BASE}/memory/${selectedCustomerId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await loadCustomerData(selectedCustomerId);
      }
    } catch (err) {
      console.error("Error resetting conversation:", err);
    } finally {
      setEngageLoading(false);
    }
  };

  const getStageBadge = (stage: string) => {
    const stages: Record<string, { label: string; color: string }> = {
      initial_outreach: { label: "Initial Outreach", color: "bg-blue-100 text-blue-800 border-blue-200" },
      awaiting_permission: { label: "Awaiting Permission", color: "bg-yellow-100 text-yellow-800 border-yellow-200" },
      awaiting_amount: { label: "Awaiting Amount", color: "bg-orange-100 text-orange-800 border-orange-200" },
      awaiting_frequency: { label: "Awaiting Frequency", color: "bg-indigo-100 text-indigo-800 border-indigo-200" },
      awaiting_consent: { label: "Awaiting Consent", color: "bg-purple-100 text-purple-800 border-purple-200" },
      completed: { label: "Onboarding Completed", color: "bg-green-100 text-green-800 border-green-200" },
      escalated: { label: "Escalated to RM", color: "bg-red-100 text-red-800 border-red-200 animate-pulse" },
      declined: { label: "Declined / Opt-out", color: "bg-gray-100 text-gray-800 border-gray-200" },
    };

    const s = stages[stage] || { label: stage, color: "bg-gray-100 text-gray-800" };
    return (
      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${s.color}`}>
        {s.label}
      </span>
    );
  };

  const getSignalIcon = (type: string) => {
    switch (type) {
      case "salary_spike":
        return "💰";
      case "idle_balance_high":
        return "📈";
      case "recurring_hospital_debit":
        return "🏥";
      case "recurring_school_fee":
        return "🎓";
      case "forex_transaction_spike":
        return "✈️";
      case "large_one_time_credit":
        return "💎";
      case "dormant_high_value":
        return "💤";
      default:
        return "🔔";
    }
  };

  const getCleanSignalName = (type: string) => {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-900 text-slate-100 font-sans overflow-hidden">
      {/* HEADER */}
      <header className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-cyan-500 flex items-center justify-center font-bold text-slate-950 text-xl shadow-lg shadow-cyan-500/20">
            S
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              SBI Sarathi <span className="text-xs bg-cyan-500/25 text-cyan-400 font-medium px-2 py-0.5 rounded">MVP v1.0</span>
            </h1>
            <p className="text-xs text-slate-400">Proactive Signal-Driven Conversational Banking Assistant</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping"></span>
            <span>Server: localhost:8000</span>
          </div>
          <button 
            onClick={fetchCustomers}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 text-slate-300"
            title="Refresh List"
          >
            🔄
          </button>
        </div>
      </header>

      {/* DASHBOARD BODY */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT PANEL: Customer List */}
        <aside className="w-80 bg-slate-950 border-r border-slate-800 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-850">
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500">🔍</span>
              <input
                type="text"
                placeholder="Search name, ID, city, signal..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-900">
            {loading ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                <div className="animate-spin inline-block w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mb-2"></div>
                <div>Loading customers...</div>
              </div>
            ) : filteredCustomers.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">No customers found.</div>
            ) : (
              filteredCustomers.map((c) => {
                const isSelected = c.customer_id === selectedCustomerId;
                return (
                  <button
                    key={c.customer_id}
                    onClick={() => setSelectedCustomerId(c.customer_id)}
                    className={`w-full p-4 text-left hover:bg-slate-900 transition-colors flex flex-col gap-1.5 ${
                      isSelected ? "bg-slate-900/80 border-l-4 border-cyan-500" : ""
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <span className="font-semibold text-white text-sm">{c.name}</span>
                      <span className="text-[10px] text-slate-500 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800 font-mono">
                        {c.customer_id}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-xs text-slate-400">
                      <span>📍 {c.city}</span>
                      <span className="uppercase text-[10px] font-medium text-slate-400 bg-slate-800 px-1.5 rounded">
                        Lang: {c.language_pref}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {c.life_event_signals.slice(0, 2).map((sig) => (
                        <span
                          key={sig}
                          className="text-[9px] font-semibold bg-cyan-950/60 text-cyan-400 border border-cyan-900 px-2 py-0.5 rounded-full flex items-center gap-1"
                        >
                          <span>{getSignalIcon(sig)}</span>
                          <span>{getCleanSignalName(sig)}</span>
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* CENTER PANEL: Customer Details, Signals, & Qualification */}
        <main className="flex-1 bg-slate-900 overflow-y-auto p-6 flex flex-col gap-6">
          {engageLoading && !customerDetails ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
              <div className="animate-spin inline-block w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full mb-4"></div>
              <span>Initializing Sarathi Orchestrator...</span>
            </div>
          ) : !customerDetails ? (
            <div className="flex-1 flex items-center justify-center text-slate-500">
              Select a customer from the list to begin engagement.
            </div>
          ) : (
            <>
              {/* Profile Overview */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/5 rounded-full -mr-16 -mt-16 blur-2xl"></div>
                <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-semibold">Customer Demographics</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-slate-500">Full Name</div>
                    <div className="text-base font-bold text-white mt-0.5">{customerDetails.name}</div>
                    <div className="text-xs text-slate-400">{customerDetails.age} years old • {customerDetails.city}, {customerDetails.state}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">KYC Status</div>
                    <div className="mt-1">
                      <span
                        className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded border ${
                          customerDetails.kyc_status === "complete"
                            ? "bg-emerald-950 text-emerald-400 border-emerald-900"
                            : "bg-rose-950 text-rose-400 border-rose-900"
                        }`}
                      >
                        {customerDetails.kyc_status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Risk Profile</div>
                    <div className="mt-1">
                      <span
                        className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded border ${
                          customerDetails.risk_profile === "conservative"
                            ? "bg-slate-800 text-slate-300 border-slate-700"
                            : customerDetails.risk_profile === "moderate"
                            ? "bg-blue-950 text-blue-400 border-blue-900"
                            : "bg-amber-950 text-amber-400 border-amber-900"
                        }`}
                      >
                        {customerDetails.risk_profile.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 font-medium">Estimated Income</div>
                    <div className="text-base font-bold text-emerald-400 mt-0.5">
                      {customerDetails.annual_income ? formatCurrency(customerDetails.annual_income) : "N/A"}
                      <span className="text-slate-500 text-[10px] font-normal block">estimated / yr</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-900">
                  <div className="text-xs text-slate-500 mb-2">Existing Products</div>
                  <div className="flex flex-wrap gap-1.5">
                    {customerDetails.existing_products.map((p) => (
                      <span key={p} className="text-xs bg-slate-900 text-slate-300 border border-slate-800 px-2 py-0.5 rounded">
                        💼 {p.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                      </span>
                    ))}
                  </div>
                </div>

                {customerDetails.monthly_balance_avg_6m && (
                  <div className="mt-4 pt-4 border-t border-slate-900">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs text-slate-500">6-Month Balance History</span>
                      <span className="text-xs text-slate-400 font-semibold">
                        Avg: {formatCurrency(customerDetails.monthly_balance_avg_6m.reduce((a, b) => a + b, 0) / 6)}
                      </span>
                    </div>
                    <div className="flex items-end justify-between h-12 gap-1 px-2 pt-2">
                      {customerDetails.monthly_balance_avg_6m.map((val, idx) => {
                        const max = Math.max(...customerDetails.monthly_balance_avg_6m);
                        const height = max > 0 ? (val / max) * 100 : 10;
                        return (
                          <div key={idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
                            <div
                              style={{ height: `${height}%` }}
                              className="w-full bg-slate-800 group-hover:bg-cyan-500 transition-all rounded-t"
                            ></div>
                            <div className="absolute bottom-14 hidden group-hover:block bg-slate-950 text-[10px] text-white p-1 rounded shadow-lg border border-slate-800 z-10 whitespace-nowrap">
                              Month {idx + 1}: {formatCurrency(val)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Detected Signals */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-lg">
                <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-semibold">Detected Life-Event Signals (Signal Agent)</h2>
                {engageData?.signals && engageData.signals.length > 0 ? (
                  <div className="flex flex-col gap-3">
                    {engageData.signals.map((sig) => (
                      <div key={sig.signal_type} className="flex items-start justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-850 hover:border-slate-800 transition-colors">
                        <div className="flex items-start gap-3">
                          <span className="text-2xl mt-0.5">{getSignalIcon(sig.signal_type)}</span>
                          <div>
                            <div className="font-semibold text-white text-sm">{getCleanSignalName(sig.signal_type)}</div>
                            <div className="text-xs text-slate-400 mt-0.5">{sig.reason}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-slate-500">Confidence</div>
                          <div className="text-sm font-bold text-cyan-400">{Math.round(sig.confidence * 100)}%</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 text-center text-slate-500 border border-dashed border-slate-850 rounded-lg text-xs">
                    No active life-event signals detected.
                  </div>
                )}
              </div>

              {/* Qualification Results */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-lg">
                <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-4 font-semibold">Propensity Scoring & Qualification (Qualification Agent)</h2>
                {engageData?.qualification ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Propensity Gauge */}
                    <div className="bg-slate-900/50 border border-slate-850 rounded-lg p-4 flex flex-col items-center justify-center text-center">
                      <span className="text-xs text-slate-500 mb-1">Propensity Score</span>
                      <div className="relative flex items-center justify-center mt-2">
                        {/* Circle Score representation */}
                        <svg className="w-24 h-24 transform -rotate-90">
                          <circle cx="48" cy="48" r="40" className="stroke-slate-800" strokeWidth="8" fill="transparent" />
                          <circle
                            cx="48"
                            cy="48"
                            r="40"
                            className="stroke-cyan-500"
                            strokeWidth="8"
                            fill="transparent"
                            strokeDasharray={251.2}
                            strokeDashoffset={251.2 - (251.2 * engageData.qualification.propensity_score)}
                          />
                        </svg>
                        <span className="absolute text-xl font-extrabold text-white">
                          {Math.round(engageData.qualification.propensity_score * 100)}%
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 mt-2 block">Logistic Regression Output</span>
                    </div>

                    {/* Suitability */}
                    <div className="bg-slate-900/50 border border-slate-850 rounded-lg p-4 flex flex-col justify-between">
                      <div>
                        <span className="text-xs text-slate-500">Suitability Gate</span>
                        <div className="mt-3 flex items-center gap-2">
                          <span
                            className={`w-3 h-3 rounded-full ${
                              engageData.qualification.suitability === "PASS" ? "bg-emerald-500" : "bg-rose-500"
                            }`}
                          ></span>
                          <span className="text-lg font-extrabold text-white">
                            {engageData.qualification.suitability === "PASS" ? "PASS" : "FAIL"}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-2">
                          {engageData.qualification.suitability === "PASS"
                            ? "Customer fits product criteria and KYC is clear. Safe for outreach."
                            : "Suitability criteria failed (conservative risk vs. market product, pending KYC, or score < 0.50)."}
                        </p>
                      </div>
                      
                      {engageData.qualification.suitability === "FAIL" && (
                        <div className="bg-rose-950/30 border border-rose-900/50 text-[10px] text-rose-300 p-2 rounded mt-2">
                          ⚠️ Automated RM escalation triggered.
                        </div>
                      )}
                    </div>

                    {/* Recommended Product */}
                    <div className="bg-slate-900/50 border border-slate-850 rounded-lg p-4 flex flex-col justify-between">
                      <div>
                        <span className="text-xs text-slate-500">Recommended Action</span>
                        <div className="text-sm font-bold text-white mt-2 flex items-center gap-1.5">
                          🎁 {engageData.qualification.recommended_product.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                        </div>
                        <p className="text-xs text-slate-400 mt-2">
                          System recommended banking product mapped from the strongest signal event.
                        </p>
                      </div>
                      
                      <div className="mt-4 pt-2 border-t border-slate-850 flex justify-between items-center text-[10px] text-slate-500">
                        <span>Model: Propensity-LR-v1</span>
                        <span>Stage: 2/3</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 text-center text-slate-500 border border-dashed border-slate-850 rounded-lg text-xs">
                    No qualification score available.
                  </div>
                )}
              </div>
            </>
          )}
        </main>

        {/* RIGHT PANEL: AI Outreach & Conversational view */}
        <aside className="w-96 bg-slate-950 border-l border-slate-800 flex flex-col overflow-hidden">
          {engageLoading && !engageData ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              Loading chat...
            </div>
          ) : !engageData ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm text-center p-6">
              Outreach panel inactive. Choose a customer to review proactive message history.
            </div>
          ) : (
            <>
              {/* Status Header */}
              <div className="px-4 py-3 bg-slate-900/80 border-b border-slate-800 flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Outreach Workflow</span>
                  <div className="flex gap-2">
                    <button
                      onClick={handleResetConversation}
                      className="text-[10px] text-slate-400 hover:text-slate-100 bg-slate-800 px-2 py-0.5 rounded border border-slate-700 transition-colors"
                      title="Clear chat and DB history"
                    >
                      Reset State
                    </button>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  {getStageBadge(engageData.memory.current_stage)}
                  <span className="text-[10px] text-slate-500">
                    Turns: {engageData.memory.conversation_history.filter(m => m.role === "assistant").length}
                  </span>
                </div>
              </div>

              {/* Ticket details if escalated */}
              {engageData.escalation && (
                <div className="mx-4 mt-3 p-3 rounded-lg bg-red-950/20 border border-red-900/50 text-xs flex flex-col gap-1.5 shadow">
                  <div className="flex justify-between items-center text-rose-400 font-bold">
                    <span>🚨 RM Escalation Active</span>
                    <span className="bg-rose-950 px-2 py-0.5 rounded text-[10px] font-mono border border-rose-900">
                      {engageData.escalation.ticket_id}
                    </span>
                  </div>
                  <div className="text-slate-300">
                    <span className="text-slate-500">Assigned To:</span> {engageData.escalation.assigned_to}
                  </div>
                  <div className="text-slate-300">
                    <span className="text-slate-500">Status:</span> <span className="capitalize text-yellow-400 font-semibold">{engageData.escalation.status}</span>
                  </div>
                  <div className="text-slate-400 text-[10px]">
                    System paused conversational LLM outreach. Human intervention required.
                  </div>
                </div>
              )}

              {/* Chat history */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
                {engageData.memory.conversation_history.length === 0 ? (
                  <div className="text-center text-slate-500 text-xs my-auto">
                    Conversation memory empty. Generate an outreach message above to start.
                  </div>
                ) : (
                  engageData.memory.conversation_history.map((msg, idx) => {
                    const isRMSystem = msg.content.startsWith("[SYSTEM]");
                    const isUser = msg.role === "user";
                    
                    if (isRMSystem) {
                      return (
                        <div key={idx} className="w-full flex justify-center py-1">
                          <div className="bg-red-950/30 text-rose-300 text-[10px] px-3 py-1 rounded-full border border-red-900/40 text-center max-w-[85%]">
                            {msg.content}
                          </div>
                        </div>
                      );
                    }
                    
                    return (
                      <div
                        key={idx}
                        className={`flex flex-col max-w-[80%] ${
                          isUser ? "self-end items-end" : "self-start items-start"
                        }`}
                      >
                        <span className="text-[9px] text-slate-500 mb-0.5 px-1 uppercase tracking-wide">
                          {isUser ? "Customer" : "Sarathi Agent"}
                        </span>
                        <div
                          className={`rounded-2xl px-3.5 py-2 text-sm shadow ${
                            isUser
                              ? "bg-slate-800 text-slate-100 rounded-tr-none"
                              : "bg-cyan-900/70 text-slate-100 border border-cyan-800/50 rounded-tl-none"
                          }`}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Quick simulation responses / input */}
              <div className="p-4 border-t border-slate-850 bg-slate-900/50 flex flex-col gap-3">
                {engageData.memory.current_stage !== "escalated" && (
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase tracking-wide font-semibold block mb-2">
                      Quick Responses (Simulation)
                    </span>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => handleSendReply("Yes, sure, tell me about the option.")}
                        disabled={replyLoading}
                        className="text-xs bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 px-2.5 py-1 rounded transition-colors"
                      >
                        ✅ Yes, proceed
                      </button>
                      <button
                        onClick={() => handleSendReply("No, thank you, I am not interested right now.")}
                        disabled={replyLoading}
                        className="text-xs bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 px-2.5 py-1 rounded transition-colors"
                      >
                        ❌ No, decline
                      </button>
                      <button
                        onClick={() => handleSendReply("I need Rs. 10,000")}
                        disabled={replyLoading}
                        className="text-xs bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 px-2.5 py-1 rounded transition-colors"
                      >
                        💵 Provide amount (10k)
                      </button>
                      <button
                        onClick={() => handleSendReply("Monthly SIP")}
                        disabled={replyLoading}
                        className="text-xs bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 px-2.5 py-1 rounded transition-colors"
                      >
                        📅 Frequency: Monthly
                      </button>
                      <button
                        onClick={() => handleSendReply("Yes, I consent to the terms.")}
                        disabled={replyLoading}
                        className="text-xs bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 px-2.5 py-1 rounded transition-colors"
                      >
                        ✍️ Give Consent
                      </button>
                      <button
                        onClick={() => handleSendReply("Please connect me with a human representative.")}
                        disabled={replyLoading}
                        className="text-xs bg-red-950/40 hover:bg-red-950/60 text-rose-300 border border-red-900/40 px-2.5 py-1 rounded transition-colors"
                      >
                        🚨 Request Human
                      </button>
                    </div>
                  </div>
                )}

                {/* Input box */}
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="text"
                    placeholder={
                      engageData.memory.current_stage === "escalated"
                        ? "Chat disabled. Handoff active."
                        : "Type customer reply..."
                    }
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    disabled={replyLoading || engageData.memory.current_stage === "escalated"}
                    className="flex-1 px-3 py-2 text-sm bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-cyan-500 disabled:opacity-50 transition-colors"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && replyText.trim()) {
                        handleSendReply(replyText);
                      }
                    }}
                  />
                  <button
                    onClick={() => handleSendReply(replyText)}
                    disabled={replyLoading || !replyText.trim() || engageData.memory.current_stage === "escalated"}
                    className="px-3.5 py-2 text-sm bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg disabled:opacity-50 transition-colors font-semibold"
                  >
                    {replyLoading ? "..." : "Send"}
                  </button>
                </div>

                {/* Escalation Handlers */}
                {!engageData.escalation && (
                  <button
                    onClick={() => setShowManualEscalateModal(true)}
                    className="mt-1 w-full py-1.5 text-xs font-semibold text-rose-400 bg-rose-950/10 hover:bg-rose-950/30 border border-rose-900/30 rounded-lg transition-colors"
                  >
                    ⚠️ Manually Escalate to Relationship Manager
                  </button>
                )}
              </div>
            </>
          )}
        </aside>
      </div>

      {/* MANUAL ESCALATION MODAL */}
      {showManualEscalateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-xl max-w-md w-full p-6 flex flex-col gap-4 shadow-2xl">
            <div>
              <h3 className="text-base font-bold text-white">Manual RM Escalation</h3>
              <p className="text-xs text-slate-400 mt-1">
                Provide a reason to escalate this customer lead to a Relationship Manager.
              </p>
            </div>
            
            <textarea
              placeholder="E.g., Customer requesting custom loan details, reports dissatisfaction, or needs tax portfolio review..."
              value={manualReason}
              onChange={(e) => setManualReason(e.target.value)}
              className="w-full h-24 p-3 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
            />
            
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setManualReason("");
                  setShowManualEscalateModal(false);
                }}
                className="px-4 py-2 text-xs font-semibold bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg transition-colors text-slate-400 hover:text-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleManualEscalate}
                disabled={escalateLoading || !manualReason.trim()}
                className="px-4 py-2 text-xs font-bold bg-rose-600 hover:bg-rose-500 rounded-lg transition-colors text-white disabled:opacity-50"
              >
                {escalateLoading ? "Escalating..." : "Escalate Ticket"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
