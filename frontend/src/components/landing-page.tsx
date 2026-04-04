import { useEffect, useMemo, useRef, useState } from "react";
import SectionWithMockup from "@/components/ui/section-with-mockup";
import { GlobeAnalytics } from "@/components/ui/cobe-globe-analytics";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import * as Recharts from "recharts";
import {
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BellRing,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  CreditCard,
  Globe2,
  LayoutDashboard,
  Layers,
  ShieldCheck,
  UserRound,
  XCircle,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { FloatingPaths } from "@/components/ui/background-paths";

const RLMapContainer = MapContainer as any;
const RLTileLayer = TileLayer as any;
const RLCircle = Circle as any;
const RLCircleMarker = CircleMarker as any;

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "live-transactions", label: "Live Transactions Feed", icon: Clock3 },
  { id: "fraud-ring", label: "Fraud Ring Graph", icon: Layers },
  { id: "users", label: "Users", icon: UserRound },
  { id: "location", label: "Location", icon: Globe2 },
  { id: "alerts", label: "Alerts", icon: BellRing },
  { id: "transaction-analysis", label: "Transaction Analysis", icon: CreditCard },
];

export function DashboardApp() {
  const [activeSection, setActiveSection] = useState<string>("dashboard");

  return (
    <div className="relative min-h-screen flex bg-black text-slate-50 overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-60">
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
      </div>
      <Sidebar activeSection={activeSection} onSelectSection={setActiveSection} />
      <div className="flex-1 flex flex-col">
        <main className="flex-1 overflow-y-auto px-4 md:px-8 pt-5 md:pt-7 pb-16 space-y-16 bg-black/80">
          {activeSection === "dashboard" && <DashboardSection />}
          {activeSection === "live-transactions" && (
            <LiveTransactionsFeedSection />
          )}
          {activeSection === "fraud-ring" && <FraudRingSection />}
          {activeSection === "users" && <UsersSection />}
          {activeSection === "location" && <LocationSection />}
          {activeSection === "alerts" && <AlertsSection />}
          {activeSection === "transaction-analysis" && (
            <TransactionAnalysisSection />
          )}
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  activeSection,
  onSelectSection,
}: {
  activeSection: string;
  onSelectSection: (id: string) => void;
}) {
  const navigate = useNavigate();

  return (
    <aside className="hidden md:flex flex-col w-20 lg:w-64 border-r border-white/10 bg-gradient-to-b from-black to-black/80 backdrop-blur-xl">
      <div className="flex items-center justify-center lg:justify-start gap-2 px-4 py-6 border-b border-white/10">
        <div className="h-9 w-9 rounded-2xl bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center shadow-soft-glow">
          <ShieldCheck className="h-5 w-5 text-slate-950" />
        </div>
        <div className="hidden lg:flex flex-col">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Quantum Shield
          </span>
          <span className="text-sm font-medium text-slate-50">
            AI Fraud Ops
          </span>
        </div>
      </div>
      <nav className="flex-1 py-6 flex flex-col gap-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelectSection(item.id)}
            className={cn(
              "group flex items-center justify-center lg:justify-start gap-3 px-3 py-2 rounded-full mx-3 text-sm transition-all duration-300",
              activeSection === item.id
                ? "text-slate-50 bg-white/10"
                : "text-slate-400 hover:text-slate-50 hover:bg-white/5"
            )}
          >
            <div
              className={cn(
                "relative flex h-9 w-9 items-center justify-center rounded-full border bg-slate-900/60",
                activeSection === item.id
                  ? "border-indigo-400/80 shadow-soft-glow"
                  : "border-white/10 group-hover:border-indigo-400/70 group-hover:shadow-soft-glow"
              )}
            >
              <item.icon className="h-4 w-4" />
            </div>
            <span className="hidden lg:inline-flex text-xs font-medium tracking-wide">
              {item.label}
            </span>
          </button>
        ))}
      </nav>
      <div className="px-4 py-6 border-t border-white/10 text-[11px] text-slate-500 flex flex-col gap-3">
        <span>LIVE · Bank-grade security</span>
        <span className="text-slate-600">
          Powered by explainable AI
        </span>
        <button
          type="button"
          onClick={() => navigate("/login")}
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-full border border-rose-400/60 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-200 hover:bg-rose-500/20 transition"
        >
          <LogOut className="h-3.5 w-3.5" />
          Logout
        </button>
      </div>
    </aside>
  );
}

function DashboardSection() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDashboardStats() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/dashboard/stats`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed dashboard stats: ${response.status}`);
        }

        const data = (await response.json()) as DashboardStats;
        setStats(data);
      } catch (error) {
        // Keep UI usable with placeholder values while backend integration is evolving.
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setStats(null);
      }
    }

    loadDashboardStats();

    return () => controller.abort();
  }, []);

  const totalToday = stats?.total_transactions_today ?? 2184392;
  const fraudCaught = stats?.fraud_blocked_today?.count ?? 1284;
  const amountSaved = stats?.fraud_blocked_today?.amount_sum ?? 986430.52;
  const falsePositive =
    stats?.fraud_by_type?.find((item) =>
      item.fraud_type.toLowerCase().includes("false")
    )?.count ?? 23;

  const formatNumber = (value: number) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);

  return (
    <section id="dashboard" className="space-y-8 pt-4">
      <div className="grid gap-4 md:grid-cols-4">
        <DashboardCard
          label="Total Today"
          value={formatNumber(totalToday)}
          helper="Transactions today"
          chip={{ label: "Live", tone: "success" }}
        />
        <DashboardCard
          label="Fraud Caught"
          value={formatNumber(fraudCaught)}
          helper="Blocked today"
          chip={{ label: "Risk blocked", tone: "danger" }}
        />
        <DashboardCard
          label="Amount Saved"
          value={formatCurrency(amountSaved)}
          helper="Blocked transaction value"
          chip={{ label: "Protected", tone: "success" }}
        />
        <DashboardCard
          label="False Positive"
          value={formatNumber(falsePositive)}
          helper="Placeholder from backend mapping"
          chip={{ label: "Tune model", tone: "warning" }}
        />
      </div>
      <FraudTypeBreakdownCard stats={stats} />
    </section>
  );
}

type DashboardStats = {
  total_transactions_today: number;
  fraud_blocked_today: {
    count: number;
    amount_sum: number;
  };
  fraud_by_type: Array<{
    fraud_type: string;
    count: number;
  }>;
};

function FraudTypeBreakdownCard({ stats }: { stats: DashboardStats | null }) {
  const fallback = [
    { fraud_type: "ATO", count: 42 },
    { fraud_type: "Low & Slow", count: 28 },
    { fraud_type: "Velocity", count: 16 },
    { fraud_type: "Fraud Ring", count: 9 },
    { fraud_type: "Synthetic ID", count: 5 },
  ];

  const source =
    stats?.fraud_by_type && stats.fraud_by_type.length > 0
      ? stats.fraud_by_type
      : fallback;

  const total = Math.max(1, source.reduce((sum, item) => sum + item.count, 0));
  const toPercent = (value: number) => Math.min(100, Math.max(0, (value / total) * 100));

  const chartData = source.slice(0, 6).map((item) => ({
    name: item.fraud_type,
    value: item.count,
    percent: Math.round(toPercent(item.count)),
  }));

  const donutColors = [
    "#ef4444",
    "#f59e0b",
    "#22c55e",
    "#06b6d4",
    "#3b82f6",
    "#8b5cf6",
  ];

  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
      <div className="text-sm font-semibold tracking-wide text-slate-100">
        Fraud Type Breakdown Chart
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius={74}
                outerRadius={116}
                paddingAngle={2}
                stroke="rgba(2,6,23,0.8)"
                labelLine={false}
                label={({ payload, x, y }) => (
                  <text
                    x={x}
                    y={y}
                    fill="#e2e8f0"
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={12}
                    fontWeight={600}
                  >
                    {`${Math.min(100, Math.max(0, Math.round(payload?.percent ?? 0)))}%`}
                  </text>
                )}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${entry.name}`} fill={donutColors[index % donutColors.length]} />
                ))}
              </Pie>
              <RechartsTooltip
                contentStyle={{
                  background: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(148,163,184,0.25)",
                  borderRadius: "10px",
                  color: "#e2e8f0",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

type LiveTransaction = {
  txn_id: string;
  user_id: string;
  username: string;
  amount: number;
  fraud_score: number;
  decision: string;
  merchant_name: string;
  timestamp: string;
  location: string;
  why_flagged?: string;
};

type LiveTransactionsResponse = {
  transactions: LiveTransaction[];
  generated_at: string;
};

type TrendPoint = {
  time: string;
  safe: number;
  risky: number;
  fishy: number;
};

function LiveTransactionsFeedSection() {
  const [rows, setRows] = useState<LiveTransaction[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [searchType, setSearchType] = useState<
    "all" | "txn_id" | "username" | "user_id" | "merchant" | "location"
  >("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [decisionFilter, setDecisionFilter] = useState<"all" | "APPROVE" | "REVIEW" | "BLOCK">("all");
  const [riskFilter, setRiskFilter] = useState<"all" | "safe" | "risky" | "fishy">("all");
  const [sortBy, setSortBy] = useState<
    "time" | "amount" | "fraud_score" | "txn_id"
  >("time");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [activeTransaction, setActiveTransaction] = useState<LiveTransaction | null>(null);
  const [activeUserMeta, setActiveUserMeta] = useState<{
    usualCity: string;
    trustedDeviceCount: number;
  } | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadLiveTransactions = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/transactions/live?limit=20`);

        if (!response.ok) {
          throw new Error(`Failed live transactions: ${response.status}`);
        }

        const data = (await response.json()) as LiveTransactionsResponse;

        if (!isMounted) {
          return;
        }

        setRows(data.transactions);
      } catch {
        // Keep the latest rendered rows when initial fetch fails.
      }
    };

    void loadLiveTransactions();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (rows.length === 0) {
      return;
    }

    const updateTrend = () => {
      const safe = rows.filter((row) => row.fraud_score < 40).length;
      const risky = rows.filter((row) => row.fraud_score >= 40 && row.fraud_score < 70).length;
      const fishy = rows.filter((row) => row.fraud_score >= 70).length;
      const time = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      setTrend((prev) => [...prev.slice(-11), { time, safe, risky, fishy }]);
    };

    updateTrend();
    const trendId = window.setInterval(updateTrend, 3000);

    return () => window.clearInterval(trendId);
  }, [rows]);

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const wsUrl = new URL(baseUrl);
    wsUrl.protocol = wsUrl.protocol === "https:" ? "wss:" : "ws:";
    wsUrl.pathname = "/api/transactions/ws/live";

    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let active = true;

    const connect = () => {
      socket = new WebSocket(wsUrl.toString());

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as {
            type?: string;
            transaction?: LiveTransaction;
          };

          if (payload.type !== "transaction.created" || !payload.transaction) {
            return;
          }

          setRows((prev) => {
            const deduped = [
              payload.transaction!,
              ...prev.filter((row) => row.txn_id !== payload.transaction!.txn_id),
            ];
            return deduped.slice(0, 200);
          });
        } catch {
          // Ignore malformed websocket payloads.
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (!active) {
          return;
        }
        reconnectTimer = window.setTimeout(connect, 2000);
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, []);

  useEffect(() => {
    if (!activeTransaction) {
      setActiveUserMeta(null);
      return;
    }

    const currentTransaction = activeTransaction!;

    const controller = new AbortController();

    async function loadUserMeta() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(
          `${baseUrl}/api/user/${currentTransaction.user_id}/profile`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error("profile fetch failed");
        }

        const data = (await response.json()) as {
          user?: { city?: string; trusted_devices?: string[] };
        };

        setActiveUserMeta({
          usualCity: data.user?.city || "Unknown",
          trustedDeviceCount: data.user?.trusted_devices?.length ?? 0,
        });
      } catch {
        setActiveUserMeta({ usualCity: "Unknown", trustedDeviceCount: 0 });
      }
    }

    void loadUserMeta();
    return () => controller.abort();
  }, [activeTransaction]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    const filtered = rows.filter((row) => {
      const riskBucket = row.fraud_score >= 70 ? "fishy" : row.fraud_score >= 40 ? "risky" : "safe";

      if (decisionFilter !== "all" && row.decision !== decisionFilter) {
        return false;
      }

      if (riskFilter !== "all" && riskBucket !== riskFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const allText = [
        row.txn_id,
        row.username,
        row.user_id,
        row.merchant_name,
        row.location,
        row.decision,
      ]
        .join(" ")
        .toLowerCase();

      if (searchType === "all") {
        return allText.includes(normalizedQuery);
      }

      if (searchType === "txn_id") {
        return row.txn_id.toLowerCase().includes(normalizedQuery);
      }

      if (searchType === "username") {
        return row.username.toLowerCase().includes(normalizedQuery);
      }

      if (searchType === "user_id") {
        return row.user_id.toLowerCase().includes(normalizedQuery);
      }

      if (searchType === "merchant") {
        return row.merchant_name.toLowerCase().includes(normalizedQuery);
      }

      return row.location.toLowerCase().includes(normalizedQuery);
    });

    return filtered.sort((a, b) => {
      const direction = sortOrder === "asc" ? 1 : -1;

      if (sortBy === "txn_id") {
        return a.txn_id.localeCompare(b.txn_id) * direction;
      }

      if (sortBy === "amount") {
        return (a.amount - b.amount) * direction;
      }

      if (sortBy === "fraud_score") {
        return (a.fraud_score - b.fraud_score) * direction;
      }

      return (Date.parse(a.timestamp) - Date.parse(b.timestamp)) * direction;
    });
  }, [rows, searchQuery, searchType, decisionFilter, riskFilter, sortBy, sortOrder]);

  return (
    <section id="live-transactions" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="space-y-6">
          <div className="rounded-3xl bg-slate-950/80 border border-white/10 backdrop-blur-2xl p-5 space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400 border border-white/20 px-4 py-3 rounded-xl">
              <div className="flex items-center gap-2 tracking-[0.12em] uppercase">
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-rose-400 animate-pulse" />
                Live Risk Trend
              </div>
              <span>WebSocket stream</span>
            </div>
            <LiveTrendChart points={trend} />
          </div>

          <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
            <div className="text-sm font-semibold tracking-wide text-slate-100">
              Entire Live Transactions
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3">
              <label className="xl:col-span-1 space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Search In</span>
                <select
                  value={searchType}
                  onChange={(event) => setSearchType(event.target.value as typeof searchType)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="all">All Fields</option>
                  <option value="txn_id">Transaction ID</option>
                  <option value="username">Username</option>
                  <option value="user_id">User ID</option>
                  <option value="merchant">Merchant</option>
                  <option value="location">Location</option>
                </select>
              </label>

              <label className="xl:col-span-2 space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Search Query</span>
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search transaction id, user, merchant, location..."
                  className="w-full rounded-xl border border-white/15 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                />
              </label>

              <label className="xl:col-span-1 space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Decision</span>
                <select
                  value={decisionFilter}
                  onChange={(event) => setDecisionFilter(event.target.value as typeof decisionFilter)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="all">All</option>
                  <option value="APPROVE">Approve</option>
                  <option value="REVIEW">Review</option>
                  <option value="BLOCK">Block</option>
                </select>
              </label>

              <label className="xl:col-span-1 space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Risk</span>
                <select
                  value={riskFilter}
                  onChange={(event) => setRiskFilter(event.target.value as typeof riskFilter)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="all">All</option>
                  <option value="safe">Safe</option>
                  <option value="risky">Bit Risky</option>
                  <option value="fishy">Fishy</option>
                </select>
              </label>

              <label className="xl:col-span-1 space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Sort</span>
                <div className="flex gap-2">
                  <select
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
                    className="w-full rounded-xl border border-white/15 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                  >
                    <option value="time">Time</option>
                    <option value="txn_id">Transaction ID</option>
                    <option value="amount">Amount</option>
                    <option value="fraud_score">Fraud Score</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => setSortOrder((current) => (current === "asc" ? "desc" : "asc"))}
                    className="shrink-0 rounded-xl border border-white/20 bg-slate-900/75 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800/90"
                    title="Toggle sort order"
                  >
                    {sortOrder === "asc" ? "Asc" : "Desc"}
                  </button>
                </div>
              </label>
            </div>

            <div className="text-xs text-slate-400">
              Showing {filteredRows.length} of {rows.length} transactions
            </div>

            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="w-full min-w-[980px] text-sm">
                <thead className="bg-slate-900/85 text-slate-300">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Transaction ID</th>
                    <th className="text-left px-4 py-3 font-medium">Username</th>
                    <th className="text-left px-4 py-3 font-medium">Amount</th>
                    <th className="text-left px-4 py-3 font-medium">Fraud Score</th>
                    <th className="text-left px-4 py-3 font-medium">Location</th>
                    <th className="text-left px-4 py-3 font-medium">Time</th>
                    <th className="text-left px-4 py-3 font-medium">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr
                      key={row.txn_id}
                      className="border-t border-white/5 hover:bg-white/5 cursor-pointer"
                      onClick={() => setActiveTransaction(row)}
                    >
                      <td className="px-4 py-3 text-slate-100 font-semibold tracking-[0.06em] uppercase">{row.txn_id}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col leading-tight">
                          <span className="text-slate-100 font-medium">{row.username || row.user_id}</span>
                          <span className="text-xs text-slate-400">{row.user_id}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-emerald-300 font-medium">
                        {new Intl.NumberFormat("en-IN", {
                          style: "currency",
                          currency: "INR",
                          maximumFractionDigits: 0,
                        }).format(row.amount)}
                      </td>
                      <td className="px-4 py-3 text-slate-200">{row.fraud_score}</td>
                      <td className="px-4 py-3 text-slate-300">{row.location}</td>
                      <td className="px-4 py-3 text-slate-400">
                        {new Date(row.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex rounded-full border px-2 py-1 text-xs",
                            row.decision === "BLOCK"
                              ? "text-rose-100 bg-rose-500/15 border-rose-400/60"
                              : row.decision === "REVIEW"
                              ? "text-amber-100 bg-amber-500/15 border-amber-400/60"
                              : "text-emerald-100 bg-emerald-500/15 border-emerald-400/60"
                          )}
                        >
                          {row.decision}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {filteredRows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                        No transactions matched your current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {activeTransaction && (
        <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm p-4 md:p-8 overflow-y-auto">
          <div className="mx-auto max-w-3xl rounded-2xl border border-white/15 bg-slate-950/95 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <h3 className="text-lg md:text-xl font-semibold tracking-[0.05em]">
                {activeTransaction.txn_id} - DETAILED ANALYSIS
              </h3>
              <button
                type="button"
                onClick={() => setActiveTransaction(null)}
                className="rounded-full border border-white/20 px-3 py-1 text-sm text-slate-300 hover:bg-white/10"
              >
                Close
              </button>
            </div>

            <div className="space-y-5 p-5 text-sm">
              <div className="grid gap-2 text-slate-200">
                <div>User: {activeTransaction.username} ({activeTransaction.user_id})</div>
                <div>
                  Amount: {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(activeTransaction.amount)}
                </div>
                <div>Merchant: {activeTransaction.merchant_name}</div>
                <div>Time: {new Date(activeTransaction.timestamp).toLocaleString()}</div>
                <div>
                  Device: {activeUserMeta?.trustedDeviceCount ? `Trusted (${activeUserMeta.trustedDeviceCount})` : "UNKNOWN"} ⚠️
                </div>
                <div>
                  Location: {activeTransaction.location} (usual: {activeUserMeta?.usualCity || "Unknown"})
                </div>
              </div>

              <div className="border-t border-white/10 pt-4 space-y-3">
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Fraud Score Breakdown</div>
                <AnalysisScoreRow label="ATO Score" score={Math.min(100, Math.max(0, activeTransaction.fraud_score - 16))} />
                <AnalysisScoreRow label="Amount Anomaly" score={Math.min(100, Math.max(0, activeTransaction.fraud_score - 3))} />
                <AnalysisScoreRow label="Low & Slow" score={Math.min(100, Math.max(0, activeTransaction.fraud_score - 32))} />
                <AnalysisScoreRow label="Velocity" score={Math.min(100, Math.max(0, activeTransaction.fraud_score - 50))} />
                <AnalysisScoreRow label="Fraud Ring" score={Math.max(0, Math.round(activeTransaction.fraud_score * 0.05))} />
                <div className="h-px bg-white/10" />
                <AnalysisScoreRow label="FINAL SCORE" score={activeTransaction.fraud_score} emphasize />
              </div>

              <div className="border-t border-white/10 pt-4 space-y-2">
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Why Flagged (LLM Generated)</div>
                <p className="text-slate-200 leading-6">
                  {activeTransaction.why_flagged ||
                    `Critical: Transaction of ${new Intl.NumberFormat("en-IN", {
                      style: "currency",
                      currency: "INR",
                      maximumFractionDigits: 0,
                    }).format(activeTransaction.amount)} from ${
                      activeUserMeta?.trustedDeviceCount ? "a known" : "an unrecognized"
                    } device in ${activeTransaction.location} at unusual time. Pattern is consistent with account takeover risk. Recommend immediate review and temporary freeze.`}
                </p>
              </div>

              <div className="border-t border-white/10 pt-4 space-y-3">
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Analyst Actions</div>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-full border border-emerald-400/60 px-3 py-1.5 text-emerald-200 hover:bg-emerald-500/10">✅ Confirm Fraud</button>
                  <button className="rounded-full border border-rose-400/60 px-3 py-1.5 text-rose-200 hover:bg-rose-500/10">❌ False Positive</button>
                  <button className="rounded-full border border-amber-400/60 px-3 py-1.5 text-amber-200 hover:bg-amber-500/10">🔒 Freeze Account</button>
                  <button className="rounded-full border border-cyan-400/60 px-3 py-1.5 text-cyan-200 hover:bg-cyan-500/10">📱 Call User</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function AnalysisScoreRow({
  label,
  score,
  emphasize = false,
}: {
  label: string;
  score: number;
  emphasize?: boolean;
}) {
  return (
    <div className="grid grid-cols-[140px_minmax(0,1fr)_70px] items-center gap-3 text-sm">
      <span className={cn("text-slate-300", emphasize && "text-slate-100 font-semibold")}>{label}</span>
      <div className="h-2 rounded-full border border-slate-700/80 bg-slate-900 overflow-hidden">
        <div
          className={cn(
            "h-full",
            emphasize
              ? "bg-gradient-to-r from-rose-500 to-amber-400"
              : "bg-gradient-to-r from-indigo-400 to-cyan-300"
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={cn("text-right text-slate-300", emphasize && "text-slate-100 font-semibold")}>
        {String(score).padStart(2, "0")}/100
      </span>
    </div>
  );
}

function LiveTrendChart({ points }: { points: TrendPoint[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const chartPoints = points.length > 1 ? points : generateInitialTrend();
  const maxY = Math.max(
    5,
    ...chartPoints.map((item) => Math.max(item.safe, item.risky, item.fishy))
  );

  const width = 960;
  const height = 260;
  const padX = 40;
  const padY = 24;
  const innerWidth = width - padX * 2;
  const innerHeight = height - padY * 2;

  const getX = (index: number) =>
    padX + (index / Math.max(chartPoints.length - 1, 1)) * innerWidth;
  const getY = (value: number) =>
    padY + ((maxY - value) / Math.max(maxY, 1)) * innerHeight;

  const toPath = (values: number[]) =>
    values
      .map((value, index) => `${index === 0 ? "M" : "L"} ${getX(index)} ${getY(value)}`)
      .join(" ");

  const safePath = toPath(chartPoints.map((item) => item.safe));
  const riskyPath = toPath(chartPoints.map((item) => item.risky));
  const fishyPath = toPath(chartPoints.map((item) => item.fishy));

  const active =
    hoveredIndex !== null && chartPoints[hoveredIndex] ? chartPoints[hoveredIndex] : null;

  return (
    <div className="space-y-3">
      <div className="relative w-full overflow-hidden rounded-2xl border border-white/10 bg-slate-950/70 p-2">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[290px]">
          <g>
            {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
              <line
                key={tick}
                x1={padX}
                x2={width - padX}
                y1={padY + tick * innerHeight}
                y2={padY + tick * innerHeight}
                stroke="rgba(148,163,184,0.15)"
                strokeWidth="1"
              />
            ))}
          </g>

          <path d={safePath} fill="none" stroke="#34d399" strokeWidth="3" />
          <path d={riskyPath} fill="none" stroke="#fbbf24" strokeWidth="3" />
          <path d={fishyPath} fill="none" stroke="#fb7185" strokeWidth="3" />

          {chartPoints.map((point, index) => {
            const x = getX(index);
            return (
              <g key={`${point.time}-${index}`}>
                <circle
                  cx={x}
                  cy={getY(point.safe)}
                  r="5"
                  fill="#34d399"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
                <circle
                  cx={x}
                  cy={getY(point.risky)}
                  r="5"
                  fill="#fbbf24"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
                <circle
                  cx={x}
                  cy={getY(point.fishy)}
                  r="5"
                  fill="#fb7185"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
                <text
                  x={x}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize="10"
                  fill="rgba(148,163,184,0.85)"
                >
                  {point.time}
                </text>
              </g>
            );
          })}
        </svg>

        {active && (
          <div className="absolute right-4 top-4 rounded-xl border border-white/20 bg-slate-900/95 px-3 py-2 text-xs">
            <div className="text-slate-300">{active.time}</div>
            <div className="text-emerald-300">Safe: {active.safe}</div>
            <div className="text-amber-300">Bit Risky: {active.risky}</div>
            <div className="text-rose-300">Fishy: {active.fishy}</div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Safe
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Bit Risky
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400" /> Fishy
        </span>
      </div>
    </div>
  );
}

function generateInitialTrend(): TrendPoint[] {
  const now = Date.now();
  return Array.from({ length: 8 }, (_, index) => {
    const pointTime = new Date(now - (7 - index) * 3 * 60 * 1000);
    return {
      time: pointTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      safe: Math.max(1, 3 + Math.floor(Math.random() * 6)),
      risky: Math.max(0, 1 + Math.floor(Math.random() * 3)),
      fishy: Math.max(0, Math.floor(Math.random() * 3)),
    };
  });
}

function getRiskMeta(score: number): {
  label: "Fishy" | "Bit Risky" | "Safe";
  badgeClass: string;
  dotClass: string;
} {
  if (score >= 70) {
    return {
      label: "Fishy",
      badgeClass: "text-rose-100 bg-rose-500/15 border-rose-400/60",
      dotClass: "bg-rose-400",
    };
  }

  if (score >= 40) {
    return {
      label: "Bit Risky",
      badgeClass: "text-amber-100 bg-amber-500/15 border-amber-400/60",
      dotClass: "bg-amber-400",
    };
  }

  return {
    label: "Safe",
    badgeClass: "text-emerald-100 bg-emerald-500/15 border-emerald-400/60",
    dotClass: "bg-emerald-400",
  };
}

type UserSummary = {
  user_id: string;
  name: string;
  city: string;
  member_since: string;
  risk_label: string;
  avg_txn_per_day: number;
  trusted_devices: number;
  usual_login_hour: number;
};

type UserSearchResponse = {
  users: UserSummary[];
  generated_at: string;
};

type UserProfileResponseApi = {
  user: {
    user_id: string;
    name?: string;
    city?: string;
    usual_login_hour?: number;
    avg_txn_per_day?: number;
    trusted_devices?: string[];
  };
  recent_transactions: Array<{
    txn_id: string;
    amount: number;
    merchant_name: string;
    fraud_score: number;
    timestamp: string;
    city?: string;
  }>;
  login_history: Array<{
    ip_address: string;
    success: boolean;
    failure_reason?: string;
    timestamp: string;
  }>;
};

type FraudRingNode = {
  id: string;
  label: string;
  node_type: string;
  risk_score: number;
};

type FraudRingLink = {
  source: string;
  target: string;
  relation: string;
  confidence: number;
};

type FraudRingGraphResponse = {
  nodes: FraudRingNode[];
  links: FraudRingLink[];
  generated_at: string;
};

function FraudRingSection() {
  const [nodes, setNodes] = useState<FraudRingNode[]>([]);
  const [links, setLinks] = useState<FraudRingLink[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [lastPointer, setLastPointer] = useState<{ x: number; y: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const svgRef = useRef<SVGSVGElement | null>(null);

  const width = 980;
  const height = 460;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;

  useEffect(() => {
    const controller = new AbortController();

    async function loadFraudRing() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/dashboard/fraud-ring`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed fraud ring data: ${response.status}`);
        }

        const data = (await response.json()) as FraudRingGraphResponse;
        setNodes(data.nodes);
        setLinks(data.links);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        const fallbackNodes: FraudRingNode[] = [
          { id: "USR003", label: "Rohan Iyer", node_type: "user", risk_score: 82 },
          { id: "USR004", label: "Neha Kulkarni", node_type: "user", risk_score: 74 },
          { id: "USR005", label: "Karthik Rajan", node_type: "user", risk_score: 79 },
          { id: "device:ring_shared_device_01", label: "ring_shared_device_01", node_type: "device", risk_score: 91 },
        ];
        const fallbackLinks: FraudRingLink[] = [
          { source: "USR003", target: "USR004", relation: "ring_link", confidence: 0.91 },
          { source: "USR004", target: "USR005", relation: "ring_link", confidence: 0.88 },
          { source: "USR003", target: "device:ring_shared_device_01", relation: "shared_device", confidence: 0.95 },
          { source: "USR004", target: "device:ring_shared_device_01", relation: "shared_device", confidence: 0.95 },
          { source: "USR005", target: "device:ring_shared_device_01", relation: "shared_device", confidence: 0.95 },
        ];

        setNodes(fallbackNodes);
        setLinks(fallbackLinks);
      }
    }

    void loadFraudRing();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (nodes.length === 0) {
      setSelectedNodeId(null);
      return;
    }

    if (!selectedNodeId || !nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(nodes[0].id);
    }
  }, [nodes, selectedNodeId]);

  useEffect(() => {
    if (nodes.length === 0) {
      setNodePositions({});
      return;
    }

    setNodePositions((prev) => {
      const next: Record<string, { x: number; y: number }> = {};

      nodes.forEach((node, index) => {
        if (prev[node.id]) {
          next[node.id] = prev[node.id];
          return;
        }

        const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
        const isDevice = node.node_type === "device";
        const ringRadius = isDevice ? radius * 0.5 : radius;

        next[node.id] = {
          x: centerX + Math.cos(angle) * ringRadius,
          y: centerY + Math.sin(angle) * ringRadius,
        };
      });

      return next;
    });
  }, [nodes, centerX, centerY, radius]);

  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null;
  const nodeLinks = links.filter(
    (link) => link.source === selectedNodeId || link.target === selectedNodeId
  );

  return (
    <section id="fraud-ring" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-6">
        <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">Fraud Ring Graph</h2>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] items-start">
          <div className="rounded-3xl bg-slate-950/85 border border-white/10 backdrop-blur-2xl p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-300">
              <span>Wheel: zoom · Drag canvas: pan · Drag node: move</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setZoom((current) => Math.max(0.6, Number((current - 0.1).toFixed(2))))}
                  className="rounded-lg border border-white/20 px-2 py-1 hover:bg-white/10"
                >
                  -
                </button>
                <span className="min-w-[56px] text-center">{Math.round(zoom * 100)}%</span>
                <button
                  type="button"
                  onClick={() => setZoom((current) => Math.min(2.5, Number((current + 0.1).toFixed(2))))}
                  className="rounded-lg border border-white/20 px-2 py-1 hover:bg-white/10"
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setZoom(1);
                    setPan({ x: 0, y: 0 });
                  }}
                  className="rounded-lg border border-indigo-400/50 px-2 py-1 text-indigo-200 hover:bg-indigo-500/10"
                >
                  Reset
                </button>
              </div>
            </div>
            <svg
              ref={svgRef}
              viewBox={`0 0 ${width} ${height}`}
              className="w-full h-[460px] rounded-2xl bg-slate-950/70 border border-white/10"
              onWheel={(event) => {
                event.preventDefault();
                const direction = event.deltaY > 0 ? -0.1 : 0.1;
                setZoom((current) => {
                  const next = Number((current + direction).toFixed(2));
                  return Math.min(2.5, Math.max(0.6, next));
                });
              }}
              onMouseMove={(event) => {
                if (!svgRef.current) {
                  return;
                }

                const rect = svgRef.current.getBoundingClientRect();
                const x = ((event.clientX - rect.left) / rect.width) * width;
                const y = ((event.clientY - rect.top) / rect.height) * height;

                if (draggingNodeId) {
                  const worldX = (x - pan.x) / zoom;
                  const worldY = (y - pan.y) / zoom;

                  setNodePositions((prev) => ({
                    ...prev,
                    [draggingNodeId]: {
                      x: Math.min(width - 20, Math.max(20, worldX)),
                      y: Math.min(height - 20, Math.max(20, worldY)),
                    },
                  }));
                  return;
                }

                if (isPanning && lastPointer) {
                  const dx = x - lastPointer.x;
                  const dy = y - lastPointer.y;
                  setPan((current) => ({ x: current.x + dx, y: current.y + dy }));
                  setLastPointer({ x, y });
                }
              }}
              onMouseUp={() => {
                setDraggingNodeId(null);
                setIsPanning(false);
                setLastPointer(null);
              }}
              onMouseLeave={() => {
                setDraggingNodeId(null);
                setIsPanning(false);
                setLastPointer(null);
              }}
            >
              <defs>
                <linearGradient id="ringLink" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#fb7185" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.9" />
                </linearGradient>
              </defs>

              <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                <rect
                  x={0}
                  y={0}
                  width={width}
                  height={height}
                  fill="transparent"
                  onMouseDown={(event) => {
                    if (!svgRef.current) {
                      return;
                    }
                    const rect = svgRef.current.getBoundingClientRect();
                    const x = ((event.clientX - rect.left) / rect.width) * width;
                    const y = ((event.clientY - rect.top) / rect.height) * height;
                    setIsPanning(true);
                    setLastPointer({ x, y });
                  }}
                />

                {links.map((link, index) => {
                  const source = nodePositions[link.source];
                  const target = nodePositions[link.target];
                  if (!source || !target) {
                    return null;
                  }

                  return (
                    <line
                      key={`${link.source}-${link.target}-${index}`}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke="url(#ringLink)"
                      strokeWidth={Math.max(1.5, link.confidence * 2.4)}
                      strokeOpacity={0.75}
                    />
                  );
                })}

                {nodes.map((node) => {
                  const pos = nodePositions[node.id];
                  if (!pos) {
                    return null;
                  }

                  const isSelected = node.id === selectedNodeId;
                  const nodeColor =
                    node.node_type === "device"
                      ? "#38bdf8"
                      : node.risk_score >= 70
                      ? "#fb7185"
                      : node.risk_score >= 40
                      ? "#fbbf24"
                      : "#34d399";

                  return (
                    <g
                      key={node.id}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        setSelectedNodeId(node.id);
                        setDraggingNodeId(node.id);
                        setIsPanning(false);
                      }}
                      style={{ cursor: "grab" }}
                    >
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r={isSelected ? 20 : 14}
                        fill={nodeColor}
                        fillOpacity={0.9}
                        stroke={isSelected ? "#ffffff" : "#0f172a"}
                        strokeWidth={isSelected ? 2 : 1.5}
                      />
                      <text
                        x={pos.x}
                        y={pos.y + 30}
                        textAnchor="middle"
                        fontSize="11"
                        fill="rgba(226,232,240,0.95)"
                      >
                        {node.label}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>

          <aside className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4 lg:sticky lg:top-4">
            <div className="text-xs uppercase tracking-[0.14em] text-slate-400">
              Ring Node Details
            </div>

            {selectedNode ? (
              <>
                <div className="rounded-2xl border border-white/15 bg-slate-900/70 p-4 space-y-2">
                  <div className="text-slate-100 text-lg font-semibold">{selectedNode.label}</div>
                  <div className="text-xs text-slate-400">{selectedNode.id}</div>
                  <div className="flex gap-2 text-xs">
                    <span className="rounded-full border border-indigo-400/50 text-indigo-200 px-2 py-1">
                      {selectedNode.node_type.toUpperCase()}
                    </span>
                    <span className="rounded-full border border-amber-400/50 text-amber-200 px-2 py-1">
                      Risk {selectedNode.risk_score}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-200">Connections</div>
                  <div className="space-y-2 max-h-[290px] overflow-y-auto pr-1">
                    {nodeLinks.map((link, index) => {
                      const peerId = link.source === selectedNode.id ? link.target : link.source;
                      const peer = nodes.find((node) => node.id === peerId);
                      return (
                        <div key={`${peerId}-${index}`} className="rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2">
                          <div className="text-sm text-slate-100">{peer?.label || peerId}</div>
                          <div className="text-xs text-slate-400">{link.relation} · {(link.confidence * 100).toFixed(0)}% confidence</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-400">No ring nodes available.</p>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}

function UsersSection() {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [searchText, setSearchText] = useState("");
  const [riskFilter, setRiskFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [cityFilter, setCityFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"name" | "member_since" | "avg_txn" | "trusted_devices">("name");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profile, setProfile] = useState<UserProfileResponseApi | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsers() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(
          `${baseUrl}/api/users/search?query=&limit=200`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error(`Failed users search: ${response.status}`);
        }

        const data = (await response.json()) as UserSearchResponse;
        setUsers(data.users);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setUsers([]);
      }
    }

    void loadUsers();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (users.length === 0) {
      setSelectedUserId(null);
      setIsProfileOpen(false);
      return;
    }
  }, [users, selectedUserId]);

  useEffect(() => {
    if (!selectedUserId) {
      setProfile(null);
      return;
    }

    const controller = new AbortController();

    async function loadProfile() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/user/${selectedUserId}/profile`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed user profile: ${response.status}`);
        }

        const data = (await response.json()) as UserProfileResponseApi;
        setProfile(data);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setProfile(null);
      }
    }

    void loadProfile();
    return () => controller.abort();
  }, [selectedUserId]);
    const allCities = useMemo(() => {
      const citySet = new Set(users.map((user) => user.city).filter(Boolean));
      return Array.from(citySet).sort((a, b) => a.localeCompare(b));
    }, [users]);

    const filteredUsers = useMemo(() => {
      const query = searchText.trim().toLowerCase();

      return users
        .filter((user) => {
          const normalizedRisk = user.risk_label.toLowerCase();
          if (riskFilter === "high" && !normalizedRisk.includes("high")) {
            return false;
          }
          if (riskFilter === "medium" && !normalizedRisk.includes("medium")) {
            return false;
          }
          if (riskFilter === "low" && !normalizedRisk.includes("low")) {
            return false;
          }

          if (cityFilter !== "all" && user.city !== cityFilter) {
            return false;
          }

          if (!query) {
            return true;
          }

          return [user.user_id, user.name, user.city, user.risk_label]
            .join(" ")
            .toLowerCase()
            .includes(query);
        })
        .sort((a, b) => {
          if (sortBy === "name") {
            return a.name.localeCompare(b.name);
          }
          if (sortBy === "avg_txn") {
            return b.avg_txn_per_day - a.avg_txn_per_day;
          }
          if (sortBy === "trusted_devices") {
            return b.trusted_devices - a.trusted_devices;
          }
          return Date.parse(b.member_since) - Date.parse(a.member_since);
        });
    }, [users, searchText, riskFilter, cityFilter, sortBy]);

    const selectedUser = users.find((user) => user.user_id === selectedUserId) ?? null;

    const topMetrics = useMemo(() => {
      const scoped = filteredUsers;
      const total = scoped.length;
      const high = scoped.filter((user) => user.risk_label.toLowerCase().includes("high")).length;
      const medium = scoped.filter((user) => user.risk_label.toLowerCase().includes("medium")).length;
      const avgDaily =
        total > 0
          ? scoped.reduce((sum, user) => sum + user.avg_txn_per_day, 0) / total
          : 0;
      const avgTrusted =
        total > 0
          ? scoped.reduce((sum, user) => sum + user.trusted_devices, 0) / total
          : 0;
      const cities = new Set(scoped.map((user) => user.city).filter(Boolean)).size;

      return { total, high, medium, avgDaily, avgTrusted, cities };
    }, [filteredUsers]);

    const transactionTrendData = useMemo(() => {
      if (!profile) {
        return [] as Array<{ point: string; amount: number; score: number }>;
      }

      return [...profile.recent_transactions]
        .reverse()
        .map((txn, index) => ({
          point: `T${index + 1}`,
          amount: txn.amount,
          score: txn.fraud_score,
        }));
    }, [profile]);

    const loginBarData = useMemo(() => {
      if (!profile) {
        return [
          { label: "Success", count: 0 },
          { label: "Failed", count: 0 },
        ];
      }

      const success = profile.login_history.filter((item) => item.success).length;
      const failed = profile.login_history.length - success;

      return [
        { label: "Success", count: success },
        { label: "Failed", count: failed },
      ];
    }, [profile]);

  return (
    <section id="users" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-5 space-y-4">
            <div className="text-sm font-semibold tracking-wide text-slate-100">Users Overview</div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-xl border border-white/10 bg-slate-950/65 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Users</div>
                <div className="text-2xl font-semibold text-slate-100">{topMetrics.total}</div>
            </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/65 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">High Risk</div>
                <div className="text-2xl font-semibold text-rose-200">{topMetrics.high}</div>
            </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/65 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Medium Risk</div>
                <div className="text-2xl font-semibold text-amber-200">{topMetrics.medium}</div>
            </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/65 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Avg Daily Txn</div>
                <div className="text-2xl font-semibold text-cyan-200">{topMetrics.avgDaily.toFixed(1)}</div>
            </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/65 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">City Spread</div>
                <div className="text-2xl font-semibold text-indigo-200">{topMetrics.cities}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
              <label className="space-y-1 xl:col-span-2">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Search Users</span>
                <input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder="Search by name, id, city, risk"
                  className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Risk Filter</span>
                <select
                  value={riskFilter}
                  onChange={(event) => setRiskFilter(event.target.value as typeof riskFilter)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="all">All</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">City</span>
                <select
                  value={cityFilter}
                  onChange={(event) => setCityFilter(event.target.value)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="all">All Cities</option>
                  {allCities.map((city) => (
                    <option key={city} value={city}>{city}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Sort</span>
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
                  className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
                >
                  <option value="name">Name</option>
                  <option value="member_since">Newest Member</option>
                  <option value="avg_txn">Avg Daily Txn</option>
                  <option value="trusted_devices">Trusted Devices</option>
                </select>
              </label>
            </div>

            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full min-w-[920px] text-sm">
                <thead className="bg-slate-900/80 text-slate-300">
                  <tr>
                    <th className="text-left px-3 py-2">User</th>
                    <th className="text-left px-3 py-2">User ID</th>
                    <th className="text-left px-3 py-2">City</th>
                    <th className="text-left px-3 py-2">Risk</th>
                    <th className="text-left px-3 py-2">Avg Daily Txn</th>
                    <th className="text-left px-3 py-2">Trusted Devices</th>
                    <th className="text-left px-3 py-2">Member Since</th>
                    <th className="text-left px-3 py-2">History</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr key={user.user_id} className="border-t border-white/5 hover:bg-white/5">
                      <td className="px-3 py-2 text-slate-100 font-medium">{user.name}</td>
                      <td className="px-3 py-2 text-slate-300">{user.user_id}</td>
                      <td className="px-3 py-2 text-slate-300">{user.city}</td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex rounded-full border px-2 py-1 text-xs",
                            user.risk_label.toLowerCase().includes("high")
                              ? "text-rose-100 bg-rose-500/15 border-rose-400/60"
                              : user.risk_label.toLowerCase().includes("medium")
                              ? "text-amber-100 bg-amber-500/15 border-amber-400/60"
                              : "text-emerald-100 bg-emerald-500/15 border-emerald-400/60"
                          )}
                        >
                          {user.risk_label}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-300">{user.avg_txn_per_day.toFixed(1)}</td>
                      <td className="px-3 py-2 text-slate-300">{user.trusted_devices}</td>
                      <td className="px-3 py-2 text-slate-400">{new Date(user.member_since).toLocaleDateString()}</td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedUserId(user.user_id);
                            setIsProfileOpen(true);
                          }}
                          className="rounded-lg border border-indigo-400/60 px-3 py-1.5 text-xs text-indigo-100 hover:bg-indigo-500/10"
                        >
                          View Card
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredUsers.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-3 py-8 text-center text-slate-400">
                        No users matched your filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
          </div>
        </div>

          {isProfileOpen && selectedUser && (
            <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm p-4 md:p-8 overflow-y-auto">
              <div className="mx-auto max-w-6xl rounded-3xl border border-white/15 bg-slate-950/95 shadow-2xl p-5 space-y-5">
                <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
                  <div>
                    <div className="text-lg md:text-xl font-semibold text-slate-100 flex items-center gap-2">
                      <UserRound className="h-5 w-5 text-indigo-300" />
                      {selectedUser.name} - User History Card
                    </div>
                    <div className="text-sm text-slate-400 mt-1">
                      {selectedUser.user_id} · {selectedUser.city} · Member since {new Date(selectedUser.member_since).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsProfileOpen(false)}
                    className="rounded-full border border-white/20 px-3 py-1 text-sm text-slate-300 hover:bg-white/10"
                  >
                    Close
                  </button>
                </div>

                <div className="overflow-x-auto rounded-xl border border-white/10">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="bg-slate-900/80 text-slate-300">
                      <tr>
                        <th className="text-left px-3 py-2">Field</th>
                        <th className="text-left px-3 py-2">Value</th>
                        <th className="text-left px-3 py-2">Field</th>
                        <th className="text-left px-3 py-2">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-white/5">
                        <td className="px-3 py-2 text-slate-400">Risk Label</td>
                        <td className="px-3 py-2 text-slate-100">{selectedUser.risk_label}</td>
                        <td className="px-3 py-2 text-slate-400">Avg Txn / Day</td>
                        <td className="px-3 py-2 text-slate-100">{selectedUser.avg_txn_per_day.toFixed(1)}</td>
                      </tr>
                      <tr className="border-t border-white/5">
                        <td className="px-3 py-2 text-slate-400">Trusted Devices</td>
                        <td className="px-3 py-2 text-slate-100">{selectedUser.trusted_devices}</td>
                        <td className="px-3 py-2 text-slate-400">Usual Login Hour</td>
                        <td className="px-3 py-2 text-slate-100">{selectedUser.usual_login_hour}:00</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 space-y-3">
                    <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Transaction Amount Trend</div>
                    <div className="h-[220px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={transactionTrendData}>
                          <CartesianGrid stroke="rgba(148,163,184,0.2)" strokeDasharray="3 3" />
                          <XAxis dataKey="point" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                          <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                          <RechartsTooltip
                            contentStyle={{
                              background: "rgba(15, 23, 42, 0.96)",
                              border: "1px solid rgba(148,163,184,0.25)",
                              borderRadius: "10px",
                              color: "#e2e8f0",
                            }}
                          />
                          <Line type="monotone" dataKey="amount" stroke="#22d3ee" strokeWidth={2.6} dot={{ r: 3 }} />
                          <Line type="monotone" dataKey="score" stroke="#f87171" strokeWidth={2.2} dot={{ r: 2 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 space-y-3">
                    <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Login Outcome Distribution</div>
                    <div className="h-[220px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={loginBarData}>
                          <CartesianGrid stroke="rgba(148,163,184,0.2)" strokeDasharray="3 3" />
                          <XAxis dataKey="label" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                          <YAxis allowDecimals={false} stroke="#94a3b8" tick={{ fontSize: 11 }} />
                          <RechartsTooltip
                            contentStyle={{
                              background: "rgba(15, 23, 42, 0.96)",
                              border: "1px solid rgba(148,163,184,0.25)",
                              borderRadius: "10px",
                              color: "#e2e8f0",
                            }}
                          />
                          <Recharts.Bar dataKey="count" radius={[8, 8, 0, 0]}>
                            {loginBarData.map((entry, index) => (
                              <Cell key={`${entry.label}-${index}`} fill={entry.label === "Success" ? "#34d399" : "#fb7185"} />
                            ))}
                          </Recharts.Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 space-y-3">
                    <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Recent Transactions</div>
                    <div className="overflow-x-auto rounded-xl border border-white/10">
                      <table className="w-full min-w-[560px] text-sm">
                        <thead className="bg-slate-900/80 text-slate-300">
                          <tr>
                            <th className="text-left px-3 py-2">Txn ID</th>
                            <th className="text-left px-3 py-2">Amount</th>
                            <th className="text-left px-3 py-2">Merchant</th>
                            <th className="text-left px-3 py-2">Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(profile?.recent_transactions ?? []).map((txn) => (
                            <tr key={txn.txn_id} className="border-t border-white/5">
                              <td className="px-3 py-2 text-slate-100">{txn.txn_id}</td>
                              <td className="px-3 py-2 text-emerald-300">
                                {new Intl.NumberFormat("en-IN", {
                                  style: "currency",
                                  currency: "INR",
                                  maximumFractionDigits: 0,
                                }).format(txn.amount)}
                              </td>
                              <td className="px-3 py-2 text-slate-300">{txn.merchant_name}</td>
                              <td className="px-3 py-2 text-slate-300">{txn.fraud_score}</td>
                            </tr>
                          ))}
                          {(profile?.recent_transactions?.length ?? 0) === 0 && (
                            <tr>
                              <td colSpan={4} className="px-3 py-6 text-center text-slate-400">No transactions found for this user.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 space-y-3">
                    <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Login History</div>
                    <div className="overflow-x-auto rounded-xl border border-white/10">
                      <table className="w-full min-w-[560px] text-sm">
                        <thead className="bg-slate-900/80 text-slate-300">
                          <tr>
                            <th className="text-left px-3 py-2">Time</th>
                            <th className="text-left px-3 py-2">IP</th>
                            <th className="text-left px-3 py-2">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(profile?.login_history ?? []).map((item, index) => (
                            <tr key={`${item.ip_address}-${item.timestamp}-${index}`} className="border-t border-white/5">
                              <td className="px-3 py-2 text-slate-400">{new Date(item.timestamp).toLocaleString()}</td>
                              <td className="px-3 py-2 text-slate-300">{item.ip_address}</td>
                              <td className="px-3 py-2">
                                <span
                                  className={cn(
                                    "inline-flex rounded-full border px-2 py-1 text-xs",
                                    item.success
                                      ? "text-emerald-100 bg-emerald-500/15 border-emerald-400/60"
                                      : "text-rose-100 bg-rose-500/15 border-rose-400/60"
                                  )}
                                >
                                  {item.success ? "Success" : "Failed"}
                                </span>
                              </td>
                            </tr>
                          ))}
                          {(profile?.login_history?.length ?? 0) === 0 && (
                            <tr>
                              <td colSpan={3} className="px-3 py-6 text-center text-slate-400">No login history found for this user.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
      </div>
    </section>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 min-h-[56px]">
      <div className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm text-slate-100 break-words">{value}</div>
    </div>
  );
}

function DashboardCard({
  label,
  value,
  helper,
  chip,
}: {
  label: string;
  value: string;
  helper: string;
  chip?: { label: string; tone: "success" | "warning" | "danger" };
}) {
  const toneClasses: Record<"success" | "warning" | "danger", string> = {
    success:
      "text-emerald-300 bg-emerald-500/10 border-emerald-400/40 shadow-[0_0_20px_rgba(16,185,129,0.35)]",
    warning:
      "text-amber-200 bg-amber-500/10 border-amber-400/40 shadow-[0_0_20px_rgba(245,158,11,0.35)]",
    danger:
      "text-rose-200 bg-rose-500/10 border-rose-400/40 shadow-[0_0_20px_rgba(244,63,94,0.35)]",
  };

  return (
    <div className="relative rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl px-4 py-5 flex flex-col gap-2 overflow-hidden">
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
        {label}
      </span>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xl md:text-3xl font-semibold tracking-tight">
          {value}
        </span>
        {chip && (
          <span
            className={cn(
              "inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-medium",
              toneClasses[chip.tone]
            )}
          >
            {chip.label}
          </span>
        )}
      </div>
      <span className="text-xs text-slate-400">{helper}</span>
    </div>
  );
}

function RiskLevelCard() {
  return (
    <div className="relative rounded-3xl bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-slate-900/40 border border-white/10 backdrop-blur-2xl px-4 py-5 flex items-center gap-4 overflow-hidden">
      <div className="relative h-16 w-16 rounded-full bg-slate-900 flex items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-emerald-400 via-amber-400 to-rose-500 opacity-70" />
        <div className="absolute inset-[6px] rounded-full bg-slate-950" />
        <span className="relative text-xs font-semibold tracking-tight">
          42 / 100
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
          Current Risk Level
        </span>
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold text-amber-200">
            Moderate
          </span>
          <span className="text-xs text-slate-400">Stable · Below alert cap</span>
        </div>
      </div>
    </div>
  );
}

function TransactionAnalysisSection() {
  return (
    <section id="transaction-analysis" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-3">
              <DashboardCard
                label="Fraud Score"
                value="87"
                helper="Current simulated transaction"
                chip={{ label: "HIGH risk", tone: "danger" }}
              />
              <DashboardCard
                label="Risk Level"
                value="HIGH"
                helper="Decision: Block · Manual review"
                chip={{ label: "Block recommended", tone: "danger" }}
              />
              <DashboardCard
                label="Similar Attempts (24h)"
                value="12"
                helper="9 blocked as fraud"
                chip={{ label: "Streaming", tone: "warning" }}
              />
            </div>
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] items-start">
              <div className="space-y-4">
                <SectionTitle
                  icon={CreditCard}
                  label="Transaction Analysis"
                  description="Simulate a single transaction and see how the AI scores it."
                />
                <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Transaction Amount">
                      <div className="flex items-center rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3 py-2.5 text-sm focus-within:border-indigo-400/80 focus-within:ring-1 focus-within:ring-indigo-400/60 transition-all">
                        <span className="text-slate-500 mr-2">$</span>
                        <input
                          className="bg-transparent border-none outline-none flex-1 text-slate-50 placeholder:text-slate-600"
                          placeholder="4,750.00"
                        />
                      </div>
                    </Field>
                    <Field label="Time">
                      <input
                        className="w-full rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3 py-2.5 text-sm text-slate-50 placeholder:text-slate-600 focus:border-indigo-400/80 focus:ring-1 focus:ring-indigo-400/60 outline-none transition-all"
                        placeholder="02:37 AM UTC"
                      />
                    </Field>
                    <Field label="Location (optional)">
                      <input
                        className="w-full rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3 py-2.5 text-sm text-slate-50 placeholder:text-slate-600 focus:border-indigo-400/80 focus:ring-1 focus:ring-indigo-400/60 outline-none transition-all"
                        placeholder="Singapore, SG"
                      />
                    </Field>
                    <Field label="Channel">
                      <select className="w-full rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3 py-2.5 text-sm text-slate-50 focus:border-indigo-400/80 focus:ring-1 focus:ring-indigo-400/60 outline-none transition-all">
                        <option className="bg-slate-900">Card</option>
                        <option className="bg-slate-900">UPI</option>
                        <option className="bg-slate-900">Wire Transfer</option>
                      </select>
                    </Field>
                  </div>
                  <button className="inline-flex items-center justify-center w-full md:w-auto rounded-full px-6 py-2.5 text-sm font-medium bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400 text-slate-950 shadow-soft-glow hover:brightness-110 transition-all">
                    Analyze Transaction
                  </button>
                  <p className="text-[11px] text-slate-500">
                    Inference latency &lt; 20ms · evaluated across ML model and rule
                    engine.
                  </p>
                </div>
              </div>
              <div className="space-y-4">
                <SectionTitle
                  icon={ShieldCheck}
                  label="AI Risk Assessment"
                  description="Fraud score, color-coded risk level, and decision hints."
                />
                <div className="rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-900/70 border border-white/10 backdrop-blur-2xl p-5 space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="relative h-24 w-24">
                      <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-amber-400 via-rose-500 to-red-500 opacity-80" />
                      <div className="absolute inset-[10px] rounded-full bg-slate-950 flex flex-col items-center justify-center">
                        <span className="text-[10px] text-slate-500 uppercase tracking-[0.18em]">
                          Fraud Score
                        </span>
                        <span className="text-2xl font-semibold text-rose-300">
                          87
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                        Risk Level
                      </span>
                      <span className="text-lg font-semibold text-rose-200">
                        HIGH
                      </span>
                      <span className="text-xs text-slate-400">
                        Decision: Block recommended · Route to manual review.
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <Tag tone="danger">High amount</Tag>
                    <Tag tone="warning">Unusual time</Tag>
                    <Tag tone="danger">Velocity anomaly</Tag>
                    <Tag tone="warning">New device fingerprint</Tag>
                  </div>
                  <div className="rounded-2xl bg-slate-900/80 border border-slate-700/70 p-3 text-xs flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Prev. 24h</span>
                      <span className="text-slate-200 font-medium">
                        12 similar attempts · 9 blocked
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div className="h-full w-1/2 bg-gradient-to-r from-emerald-400 to-emerald-500" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
        </div>
      </div>
    </section>
  );
}

function ExplainableSection() {
  return (
    <section id="explainable-ai" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-4">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Why is this flagged?
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Explainable AI highlights exactly which signals contributed to the
              decision – high amount, unusual time, behavior deviation, and
              rule + ML overlap – so risk and compliance teams can trust every
              alert.
            </p>
          </div>
          <div className="space-y-4">
            <SectionTitle
              icon={BrainCircuit}
              label="Why is this flagged?"
              description="Explainable AI signals that compliance and risk teams can trust."
            />
            <div className="grid gap-4 md:grid-cols-4">
              <ExplainTile
                icon={ArrowRightIcon}
                title="High amount"
                body="Amount exceeds typical range for this user by 4.3× and crosses configured limits."
              />
              <ExplainTile
                icon={Clock3}
                title="Unusual time"
                body="Attempt executed at 02:37 AM · outside learned usage window and regional norms."
              />
              <ExplainTile
                icon={Activity}
                title="Behavior deviation"
                body="Location, device fingerprint, and channel deviate from last 50 sessions."
              />
              <ExplainTile
                icon={Layers}
                title="Rule + ML overlap"
                body="Triggered 3 rule hits plus high anomaly score from the ML model."
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function UserBehaviorSection() {
  return (
    <section id="user-behavior" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              User Behavior Deviation Insights
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Compare each transaction against 12+ months of learned behavior –
              typical amounts, time of day, geo stability, and device
              consistency – with a single deviation score.
            </p>
          </div>
          <div className="space-y-4">
            <SectionTitle
              icon={UserRound}
              label="User Behavior"
              description="Compare normal profile vs current transaction to understand deviation."
            />
            <div className="grid gap-6 lg:grid-cols-2">
              <BehaviorCard
                title="Normal Behavior Profile"
                subtitle="Learned from last 12 months of activity."
                variant="baseline"
              />
              <BehaviorCard
                title="Current Transaction"
                subtitle="Multiple features deviate from the learned profile."
                variant="current"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AnalyticsSection() {
  return (
    <section id="analytics" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-4">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Analytics &amp; Trends
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Understand macro fraud vs normal distributions, transaction amount
              patterns, and time-based spikes with production-grade dashboards
              and drill-downs.
            </p>
          </div>
          <div className="space-y-4">
            <SectionTitle
              icon={BarChart3}
              label="Analytics"
              description="Macro-level view of fraud vs normal transactions and temporal trends."
            />
            <div className="flex flex-wrap gap-2 text-[11px] text-slate-300">
              <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10">
                Last 24h
              </span>
              <span className="px-3 py-1 rounded-full bg-transparent border border-white/10/50 text-slate-500">
                7d
              </span>
              <span className="px-3 py-1 rounded-full bg-transparent border border-white/10/50 text-slate-500">
                30d
              </span>
            </div>
            <div className="grid gap-6 lg:grid-cols-3">
              <AnalyticsCard title="Fraud vs Normal distribution">
                <div className="flex items-center gap-4">
                  <div className="relative h-24 w-24">
                    <div className="absolute inset-0 rounded-full bg-slate-900" />
                    <div className="absolute inset-[6px] rounded-full bg-conic-to-r from-emerald-400 via-emerald-400 to-rose-500 opacity-90" />
                    <div className="absolute inset-[14px] rounded-full bg-slate-950 flex items-center justify-center">
                      <span className="text-xs text-slate-400">Fraud</span>
                      <span className="ml-1 text-sm font-semibold text-rose-300">
                        2.6%
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      <span className="text-slate-300">Normal · 97.4%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-rose-400" />
                      <span className="text-slate-300">Fraud · 2.6%</span>
                    </div>
                  </div>
                </div>
              </AnalyticsCard>
              <AnalyticsCard title="Transaction amount patterns">
                <div className="mt-2 flex items-end gap-2 h-24">
                  <Bar height="30%" tone="muted" label="0-100" />
                  <Bar height="55%" tone="muted" label="100-500" />
                  <Bar height="80%" tone="warning" label="500-2K" />
                  <Bar height="65%" tone="danger" label=">2K" />
                </div>
              </AnalyticsCard>
              <AnalyticsCard title="Time-based fraud trends">
                <div className="mt-2 h-24 rounded-2xl bg-slate-900/70 border border-slate-700/80 overflow-hidden relative">
                  <div className="absolute inset-x-4 inset-y-3 flex flex-col justify-between text-[9px] text-slate-600">
                    <span>High</span>
                    <span>Medium</span>
                    <span>Low</span>
                  </div>
                  <div className="absolute inset-x-4 inset-y-1">
                    <div className="h-full w-full">
                      <div className="h-full w-full bg-[radial-gradient(circle_at_0_100%,rgba(56,189,248,0.4),transparent_60%),radial-gradient(circle_at_60%_0,rgba(248,113,113,0.5),transparent_60%)] opacity-80" />
                    </div>
                  </div>
                </div>
              </AnalyticsCard>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function LocationSection() {
  const fallbackCityStats = useMemo(
    () => [
      {
        city: "Mumbai",
        fraud: 12,
        transactions: 42,
        tone: "danger" as const,
        location: [19.076, 72.8777] as [number, number],
      },
      {
        city: "Delhi",
        fraud: 8,
        transactions: 31,
        tone: "warning" as const,
        location: [28.6139, 77.209] as [number, number],
      },
      {
        city: "Hyderabad",
        fraud: 19,
        transactions: 37,
        tone: "danger" as const,
        location: [17.385, 78.4867] as [number, number],
      },
      {
        city: "Bangalore",
        fraud: 3,
        transactions: 18,
        tone: "success" as const,
        location: [12.9716, 77.5946] as [number, number],
      },
    ],
    []
  );

  const [cityStats, setCityStats] = useState(fallbackCityStats);

  useEffect(() => {
    const controller = new AbortController();

    async function loadLocationHeatmap() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/dashboard/location-heatmap`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed location heatmap: ${response.status}`);
        }

        const data = (await response.json()) as {
          cities?: Array<{
            city: string;
            location: [number, number];
            fraud: number;
            transactions: number;
          }>;
        };

        if (!data.cities || data.cities.length === 0) {
          setCityStats(fallbackCityStats);
          return;
        }

        const mapped = data.cities.map((city) => ({
          city: city.city,
          fraud: city.fraud,
          transactions: city.transactions,
          tone: (city.fraud >= 20 ? "danger" : city.fraud >= 8 ? "warning" : "success") as
            | "danger"
            | "warning"
            | "success",
          location: city.location,
        }));

        setCityStats(mapped);
      } catch {
        setCityStats(fallbackCityStats);
      }
    }

    void loadLocationHeatmap();
    return () => controller.abort();
  }, [fallbackCityStats]);

  const globeMarkers = cityStats.map((city) => ({
    id: city.city,
    location: city.location,
    visitors: city.transactions,
    trend: city.fraud,
    fraud: city.fraud,
    riskTone: city.tone,
  }));

  return (
    <section id="location" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="space-y-5">
          <SectionTitle
            icon={Globe2}
            label="Fraud Heat Map (2D)"
            description="Real map heat layer for fraudulent transactions, with globe retained below."
          />

          <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
            <FraudHeatMapMap data={cityStats} />
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
              <span>Globe View</span>
              <span>Retained as requested</span>
            </div>
            <div className="w-full max-w-md mx-auto">
              <GlobeAnalytics markers={globeMarkers} speed={0} className="w-full" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function FraudHeatMapMap({
  data,
}: {
  data: Array<{
    city: string;
    fraud: number;
    transactions: number;
    tone: "danger" | "warning" | "success";
    location: [number, number];
  }>;
}) {
  const indiaCenter: [number, number] = [22.9734, 78.6569];
  const maxFraud = Math.max(1, ...data.map((city) => city.fraud));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>Fraud-only heat intensity</span>
        <span>Real map tiles</span>
      </div>

      <div className="rounded-2xl border border-white/10 overflow-hidden">
        <RLMapContainer center={indiaCenter} zoom={5} className="h-[520px] w-full" scrollWheelZoom>
          <RLTileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {data.map((city) => {
            const intensity = city.fraud / maxFraud;
            const color =
              intensity >= 0.7 ? "#f43f5e" : intensity >= 0.4 ? "#f59e0b" : "#22c55e";
            const ringScale = 0.65 + intensity;

            return [
              <RLCircle
                key={`${city.city}-outer`}
                center={city.location}
                radius={98000 * ringScale}
                pathOptions={{ color: color, weight: 0, fillColor: color, fillOpacity: 0.14 + intensity * 0.08 }}
              />,
              <RLCircle
                key={`${city.city}-mid`}
                center={city.location}
                radius={64000 * ringScale}
                pathOptions={{ color: color, weight: 0, fillColor: color, fillOpacity: 0.22 + intensity * 0.1 }}
              />,
              <RLCircle
                key={`${city.city}-inner`}
                center={city.location}
                radius={32000 * ringScale}
                pathOptions={{ color: color, weight: 0, fillColor: color, fillOpacity: 0.34 + intensity * 0.14 }}
              />,
              <RLCircleMarker
                key={`${city.city}-pin`}
                center={city.location}
                radius={5}
                pathOptions={{ color: "#ec4899", fillColor: "#ec4899", fillOpacity: 0.95, weight: 1 }}
              >
                <Popup>
                  <div className="text-sm">
                    <div className="font-semibold">{city.city}</div>
                    <div>Fraud cases: {city.fraud}</div>
                  </div>
                </Popup>
              </RLCircleMarker>,
            ];
          })}
        </RLMapContainer>
      </div>

    </div>
  );
}

function AlertsSection() {
  const alerts = [
    {
      id: "TXN-984213",
      amount: "₹89,200.00",
      channel: "International Wire",
      risk: "HIGH",
      score: "92/100",
      time: "2 min ago · Singapore → London",
      tone: "danger" as const,
    },
    {
      id: "TXN-984087",
      amount: "$1,420.00",
      channel: "Card Not Present",
      risk: "MEDIUM",
      score: "71/100",
      time: "9 min ago · Mumbai → Dubai",
      tone: "warning" as const,
    },
    {
      id: "TXN-983904",
      amount: "$64.00",
      channel: "UPI",
      risk: "LOW",
      score: "34/100",
      time: "14 min ago · Delhi",
      tone: "success" as const,
    },
  ];

  return (
    <section id="alerts" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-4">
        <div className="space-y-4">
            <SectionTitle
              icon={BellRing}
              label="Alerts"
              description="Live stream of suspicious activity across your portfolio."
            />
            <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE · Streaming alerts
                </div>
                <span>Last 15 min</span>
              </div>
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {alerts.map((alert) => (
                  <AlertCard key={alert.id} {...alert} />
                ))}
              </div>
            </div>
        </div>
      </div>
    </section>
  );
}

function SimulationSection() {
  const sampleRows = [
    {
      id: "TXN-984213",
      amount: "$4,980.00",
      location: "Singapore → London",
      status: "Blocked",
      tone: "danger" as const,
    },
    {
      id: "TXN-984211",
      amount: "$1,120.00",
      location: "Delhi → Dubai",
      status: "Flagged",
      tone: "warning" as const,
    },
    {
      id: "TXN-984205",
      amount: "$72.00",
      location: "Mumbai",
      status: "Safe",
      tone: "success" as const,
    },
  ];

  return (
    <section id="simulation" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Simulation Studio
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Launch synthetic card testing, account takeover, and bot attack
              scenarios in a safe environment to validate your controls before
              they hit production.
            </p>
          </div>
          <div className="space-y-4">
            <SectionTitle
              icon={Activity}
              label="Simulation"
              description="Simulate synthetic fraud attacks to stress-test detection."
            />
            <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-start">
              <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
                <p className="text-sm text-slate-300">
                  Replay synthetic scenarios – card testing, account takeover, and
                  bot attacks – without touching production traffic.
                </p>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  <Tag tone="danger">Card testing</Tag>
                  <Tag tone="warning">Account takeover</Tag>
                  <Tag tone="success">Safe traffic baseline</Tag>
                </div>
                <button className="mt-3 inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400 text-slate-950 shadow-soft-glow hover:brightness-110 transition-all">
                  <Zap className="h-4 w-4" />
                  Simulate Fraud Attack
                </button>
                <p className="text-[11px] text-slate-500">
                  Synthetic stream only · no real customer data.
                </p>
              </div>
              <div className="rounded-3xl bg-slate-950/80 border border-white/10 backdrop-blur-2xl p-5 space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Live transaction feed</span>
                  <span>Most recent first</span>
                </div>
                <div className="space-y-2 text-xs">
                  {sampleRows.map((row) => (
                    <SimulationRow key={row.id} {...row} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AboutSection() {
  return (
    <section id="about" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              System Architecture
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Input → ML Model → Rule Engine → Output. A hybrid AI engine combines
              deep learning with deterministic rules to deliver explainable,
              regulator-ready fraud decisions.
            </p>
          </div>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] items-start">
            <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
              <div className="flex flex-col md:flex-row items-center md:items-stretch gap-4">
                <FlowStep
                  icon={Globe2}
                  title="Input"
                  body="Transaction, device fingerprint, geo signals, and user graph."
                />
                <ArrowConnector />
                <FlowStep
                  icon={BrainCircuit}
                  title="ML Model"
                  body="AI-based anomaly detection and feature scoring in real time."
                />
                <ArrowConnector />
                <FlowStep
                  icon={Layers}
                  title="Rule Engine"
                  body="Compliance rules, velocity checks, sanctions, and lists."
                />
                <ArrowConnector />
                <FlowStep
                  icon={ShieldCheck}
                  title="Output"
                  body="Approve, challenge (step-up), block, or route to human review."
                />
              </div>
            </div>
            <div className="rounded-3xl bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.5),_transparent_60%),radial-gradient(circle_at_bottom,_rgba(244,63,94,0.4),_transparent_60%)] border border-white/10 p-5 flex flex-col justify-between min-h-[260px]">
              <div className="space-y-3">
                <div className="relative h-28 w-full overflow-hidden rounded-2xl border border-white/15">
                  <img
                    src="https://images.unsplash.com/photo-1553729459-efe14ef6055d?auto=format&fit=crop&w=1200&q=80"
                    alt="Abstract financial data visualization"
                    className="h-full w-full object-cover opacity-90"
                  />
                </div>
                <p className="text-sm text-slate-100">
                  Built for banks, fintechs, and payment processors that need
                  explainable, regulator-ready fraud defenses.
                </p>
                <ul className="text-xs text-slate-200 space-y-1.5">
                  <li>• Explainable AI signals for every decision.</li>
                  <li>• Bank-grade encryption and data isolation.</li>
                  <li>• Sub-50ms scoring at scale across channels.</li>
                </ul>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-slate-900">
                <span className="px-3 py-1 rounded-full bg-emerald-300/90 font-medium">
                  Explainable AI
                </span>
                <span className="px-3 py-1 rounded-full bg-sky-300/90 font-medium">
                  Real-time scoring
                </span>
                <span className="px-3 py-1 rounded-full bg-violet-300/90 font-medium">
                  Bank-grade security
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SectionTitle({
  icon: Icon,
  label,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
          <Icon className="h-4 w-4 text-indigo-300" />
        </div>
        <div>
          <h2 className="text-sm md:text-base font-semibold tracking-tight">
            {label}
          </h2>
          <p className="text-[11px] md:text-xs text-slate-400 max-w-xl">
            {description}
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-300">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

function Tag({
  tone,
  children,
}: {
  tone: "success" | "warning" | "danger";
  children: React.ReactNode;
}) {
  const map: Record<"success" | "warning" | "danger", string> = {
    success:
      "bg-emerald-500/10 border-emerald-400/40 text-emerald-200 shadow-[0_0_16px_rgba(16,185,129,0.3)]",
    warning:
      "bg-amber-500/10 border-amber-400/40 text-amber-100 shadow-[0_0_16px_rgba(245,158,11,0.3)]",
    danger:
      "bg-rose-500/10 border-rose-400/40 text-rose-100 shadow-[0_0_16px_rgba(244,63,94,0.35)]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-medium",
        map[tone]
      )}
    >
      {children}
    </span>
  );
}

function ExplainTile({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-4 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-indigo-500 to-rose-500 flex items-center justify-center">
          <Icon className="h-4 w-4 text-slate-50" />
        </div>
        <span className="text-xs font-semibold tracking-tight">
          {title}
        </span>
      </div>
      <p className="text-[11px] text-slate-400">{body}</p>
    </div>
  );
}

function BehaviorCard({
  title,
  subtitle,
  variant,
}: {
  title: string;
  subtitle: string;
  variant: "baseline" | "current";
}) {
  const metrics = [
    "Typical Amount",
    "Time of Day",
    "Geo Stability",
    "Device Consistency",
  ];

  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        <p className="text-[11px] text-slate-400">{subtitle}</p>
      </div>
      <div className="space-y-3">
        {metrics.map((metric, idx) => {
          const baseWidth = 65 + idx * 5;
          const currentWidth =
            variant === "baseline" ? baseWidth : baseWidth + (idx % 2 === 0 ? 20 : -15);
          const tone: "success" | "warning" | "danger" =
            variant === "baseline"
              ? "success"
              : idx === 0 || idx === 2
              ? "danger"
              : "warning";
          return (
            <div key={metric} className="space-y-1">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>{metric}</span>
                <span>{variant === "baseline" ? "Stable" : tone === "danger" ? "High deviation" : "Medium deviation"}</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-900 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full bg-gradient-to-r",
                    tone === "success" && "from-emerald-400 to-emerald-500",
                    tone === "warning" && "from-amber-400 to-amber-500",
                    tone === "danger" && "from-rose-400 to-red-500"
                  )}
                  style={{ width: `${Math.max(10, Math.min(currentWidth, 100))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {variant === "current" && (
        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span className="text-slate-400">Deviation Score</span>
          <span className="px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-400/40 text-rose-100 font-medium">
            76%
          </span>
        </div>
      )}
    </div>
  );
}

function AnalyticsCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-200">{title}</span>
      </div>
      {children}
    </div>
  );
}

function Bar({
  height,
  tone,
  label,
}: {
  height: string;
  tone: "muted" | "warning" | "danger";
  label: string;
}) {
  const color =
    tone === "muted"
      ? "from-slate-500 to-slate-400"
      : tone === "warning"
      ? "from-amber-400 to-amber-500"
      : "from-rose-400 to-red-500";

  return (
    <div className="flex flex-col items-center gap-1 flex-1">
      <div className="w-full rounded-t-xl bg-slate-900/70 border border-slate-700/80 flex items-end justify-center">
        <div
          className={cn(
            "w-3/4 rounded-t-lg bg-gradient-to-t shadow-soft-glow",
            color
          )}
          style={{ height }}
        />
      </div>
      <span className="text-[9px] text-slate-500">{label}</span>
    </div>
  );
}

function AlertCard({
  id,
  amount,
  channel,
  risk,
  score,
  time,
  tone,
}: {
  id: string;
  amount: string;
  channel: string;
  risk: string;
  score: string;
  time: string;
  tone: "success" | "warning" | "danger";
}) {
  const borderColor =
    tone === "danger"
      ? "border-rose-500/60"
      : tone === "warning"
      ? "border-amber-400/60"
      : "border-emerald-400/60";

  const RiskIcon = tone === "danger" ? XCircle : tone === "warning" ? AlertTriangle : CheckCircle2;

  return (
    <div
      className={cn(
        "rounded-2xl border bg-slate-950/80 px-3 py-3 flex items-center gap-3 text-xs transition-all hover:translate-y-[-1px] hover:shadow-soft-glow",
        borderColor
      )}
    >
      <div className="flex flex-col items-center gap-1">
        <RiskIcon
          className={cn(
            "h-4 w-4",
            tone === "danger" && "text-rose-400",
            tone === "warning" && "text-amber-300",
            tone === "success" && "text-emerald-300"
          )}
        />
        <span className="text-[9px] text-slate-500">{risk}</span>
      </div>
      <div className="flex-1 flex flex-col gap-0.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="font-medium text-slate-100">
            ⚠ Suspicious Transaction Detected
          </span>
          <span className="text-slate-400">{id}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[11px]">
          <span className="text-emerald-300 font-medium">{amount}</span>
          <span className="text-slate-400">{channel}</span>
          <span className="text-rose-300 font-medium">{score}</span>
        </div>
        <span className="text-[10px] text-slate-500">{time}</span>
      </div>
      <div className="flex flex-col gap-1 min-w-[88px]">
        <button className="rounded-full border border-emerald-400/60 text-emerald-200 px-2 py-1 text-[10px] font-medium hover:bg-emerald-500/10 transition">
          Approve
        </button>
        <button className="rounded-full bg-gradient-to-r from-rose-500 to-red-500 text-slate-950 px-2 py-1 text-[10px] font-semibold hover:brightness-110 transition">
          Block
        </button>
      </div>
    </div>
  );
}

function SimulationRow({
  id,
  amount,
  location,
  status,
  tone,
}: {
  id: string;
  amount: string;
  location: string;
  status: string;
  tone: "success" | "warning" | "danger";
}) {
  const map: Record<"success" | "warning" | "danger", string> = {
    success:
      "bg-emerald-500/10 border-emerald-400/50 text-emerald-200",
    warning:
      "bg-amber-500/10 border-amber-400/50 text-amber-100",
    danger:
      "bg-rose-500/10 border-rose-400/50 text-rose-100",
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3 py-2">
      <div className="flex flex-col gap-0.5 text-[11px]">
        <span className="text-slate-300 font-medium">{id}</span>
        <span className="text-slate-400">{location}</span>
      </div>
      <div className="flex items-center gap-3 text-[11px]">
        <span className="text-emerald-300 font-medium">{amount}</span>
        <span className={cn("px-2 py-0.5 rounded-full border text-[10px]", map[tone])}>
          {status}
        </span>
      </div>
    </div>
  );
}

function FlowStep({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="flex flex-col items-center text-center gap-2 max-w-[160px]">
      <div className="h-9 w-9 rounded-full bg-white/10 border border-white/30 flex items-center justify-center">
        <Icon className="h-4 w-4 text-indigo-200" />
      </div>
      <span className="text-xs font-semibold text-slate-100">{title}</span>
      <p className="text-[10px] text-slate-300">{body}</p>
    </div>
  );
}

function ArrowConnector() {
  return (
    <div className="hidden md:flex items-center justify-center w-6">
      <div className="h-px w-6 bg-gradient-to-r from-slate-500 via-slate-200 to-slate-500" />
    </div>
  );
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-4 w-4 text-slate-50", className)}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
