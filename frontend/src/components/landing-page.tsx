import { useEffect, useMemo, useRef, useState } from "react";
import SectionWithMockup from "@/components/ui/section-with-mockup";
import { GlobeAnalytics } from "@/components/ui/cobe-globe-analytics";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
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
  const chartData = source.slice(0, 6).map((item) => ({
    name: item.fraud_type,
    value: item.count,
    percent: Math.round((item.count / total) * 100),
  }));

  const donutColors = ["#f87171", "#fb7185", "#fbbf24", "#38bdf8", "#34d399", "#a78bfa"];

  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
      <div className="text-sm font-semibold tracking-wide text-slate-100">
        Fraud Type Breakdown Chart
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)] items-center">
        <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 space-y-2">
          <div className="text-xs text-slate-400">Fraud by Type (Today)</div>
          <div className="space-y-2">
            {chartData.map((item) => (
              <div key={item.name} className="grid grid-cols-[140px_minmax(0,1fr)_48px] items-center gap-2 text-sm">
                <span className="text-slate-200 truncate">{item.name}</span>
                <div className="h-3 rounded-full border border-slate-700/80 bg-slate-900 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-400 to-cyan-300"
                    style={{ width: `${item.percent}%` }}
                  />
                </div>
                <span className="text-slate-300 text-right">{String(item.percent).padStart(2, "0")}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-2 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={92}
                paddingAngle={2}
                stroke="rgba(2,6,23,0.8)"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${entry.name}`} fill={donutColors[index % donutColors.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number, name: string) => [`${value} cases`, name]}
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
  merchant_name: string;
  timestamp: string;
  location: string;
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

type UserTableRow = {
  userId: string;
  username: string;
  transactions: number;
  totalAmount: number;
  avgScore: number;
  latestLocation: string;
  latestTime: string;
  risk: "Safe" | "Bit Risky" | "Fishy";
};

function LiveTransactionsFeedSection() {
  const [rows, setRows] = useState<LiveTransaction[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [searchType, setSearchType] = useState<
    "all" | "userId" | "username" | "location" | "risk"
  >("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<
    "username" | "transactions" | "totalAmount" | "avgScore" | "latestTime"
  >("latestTime");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);

  const fallbackRows = useMemo<LiveTransaction[]>(
    () => [
      {
        txn_id: "TXN991",
        user_id: "rajesh",
        username: "Rajesh",
        amount: 48000,
        fraud_score: 94,
        merchant_name: "CryptoXchange",
        timestamp: new Date().toISOString(),
        location: "Mumbai -> Hyderabad",
      },
      {
        txn_id: "TXN990",
        user_id: "priya",
        username: "Priya",
        amount: 5200,
        fraud_score: 58,
        merchant_name: "New Merchant",
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        location: "Pune",
      },
      {
        txn_id: "TXN989",
        user_id: "suresh",
        username: "Suresh",
        amount: 450,
        fraud_score: 8,
        merchant_name: "Amazon",
        timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
        location: "Bengaluru",
      },
      {
        txn_id: "TXN988",
        user_id: "ananya",
        username: "Ananya",
        amount: 12800,
        fraud_score: 41,
        merchant_name: "TravelHub",
        timestamp: new Date(Date.now() - 70 * 60 * 1000).toISOString(),
        location: "Delhi",
      },
      {
        txn_id: "TXN987",
        user_id: "vikram",
        username: "Vikram",
        amount: 920,
        fraud_score: 15,
        merchant_name: "MetroMart",
        timestamp: new Date(Date.now() - 100 * 60 * 1000).toISOString(),
        location: "Chennai",
      },
      {
        txn_id: "TXN986",
        user_id: "neha",
        username: "Neha",
        amount: 31000,
        fraud_score: 78,
        merchant_name: "GiftCard Vault",
        timestamp: new Date(Date.now() - 140 * 60 * 1000).toISOString(),
        location: "Kolkata",
      },
    ],
    []
  );

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

        setRows(data.transactions.length > 0 ? data.transactions : fallbackRows);
      } catch {
        if (isMounted) {
          setRows(fallbackRows);
        }
      }
    };

    void loadLiveTransactions();
    const intervalId = window.setInterval(loadLiveTransactions, 6000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [fallbackRows]);

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
    const simulationId = window.setInterval(() => {
      setRows((prev) => [createSyntheticTransaction(prev), ...prev.slice(0, 39)]);
    }, 5000);

    return () => window.clearInterval(simulationId);
  }, []);

  useEffect(() => {
    if (rows.length === 0) {
      setSelectedTxnId(null);
      return;
    }

    if (!selectedTxnId || !rows.some((row) => row.txn_id === selectedTxnId)) {
      setSelectedTxnId(rows[0].txn_id);
    }
  }, [rows, selectedTxnId]);

  const selectedTransaction = useMemo(
    () => rows.find((row) => row.txn_id === selectedTxnId) ?? null,
    [rows, selectedTxnId]
  );

  const userRows = useMemo<UserTableRow[]>(() => {
    const grouped = rows.reduce<Record<string, UserTableRow>>((acc, row) => {
      const key = row.user_id;
      const prev = acc[key];
      const timestamp = Date.parse(row.timestamp);
      const existingTime = prev ? Date.parse(prev.latestTime) : 0;

      const currentRisk: "Safe" | "Bit Risky" | "Fishy" =
        row.fraud_score >= 70 ? "Fishy" : row.fraud_score >= 40 ? "Bit Risky" : "Safe";

      if (!prev) {
        acc[key] = {
          userId: row.user_id,
          username: row.username || row.user_id,
          transactions: 1,
          totalAmount: row.amount,
          avgScore: row.fraud_score,
          latestLocation: row.location,
          latestTime: row.timestamp,
          risk: currentRisk,
        };
        return acc;
      }

      const totalTransactions = prev.transactions + 1;
      const totalScore = prev.avgScore * prev.transactions + row.fraud_score;

      acc[key] = {
        ...prev,
        transactions: totalTransactions,
        totalAmount: prev.totalAmount + row.amount,
        avgScore: totalScore / totalTransactions,
        latestLocation: timestamp > existingTime ? row.location : prev.latestLocation,
        latestTime: timestamp > existingTime ? row.timestamp : prev.latestTime,
        risk:
          currentRisk === "Fishy" || prev.risk === "Fishy"
            ? "Fishy"
            : currentRisk === "Bit Risky" || prev.risk === "Bit Risky"
            ? "Bit Risky"
            : "Safe",
      };

      return acc;
    }, {});

    const normalizedQuery = searchQuery.trim().toLowerCase();

    const filtered = Object.values(grouped).filter((item) => {
      if (!normalizedQuery) {
        return true;
      }

      const composite = [
        item.userId,
        item.username,
        item.latestLocation,
        item.risk,
      ]
        .join(" ")
        .toLowerCase();

      if (searchType === "all") {
        return composite.includes(normalizedQuery);
      }

      if (searchType === "userId") {
        return item.userId.toLowerCase().includes(normalizedQuery);
      }

      if (searchType === "username") {
        return item.username.toLowerCase().includes(normalizedQuery);
      }

      if (searchType === "location") {
        return item.latestLocation.toLowerCase().includes(normalizedQuery);
      }

      return item.risk.toLowerCase().includes(normalizedQuery);
    });

    return filtered.sort((a, b) => {
      const direction = sortOrder === "asc" ? 1 : -1;

      if (sortBy === "username") {
        return a.username.localeCompare(b.username) * direction;
      }

      if (sortBy === "transactions") {
        return (a.transactions - b.transactions) * direction;
      }

      if (sortBy === "totalAmount") {
        return (a.totalAmount - b.totalAmount) * direction;
      }

      if (sortBy === "avgScore") {
        return (a.avgScore - b.avgScore) * direction;
      }

      return (Date.parse(a.latestTime) - Date.parse(b.latestTime)) * direction;
    });
  }, [rows, searchQuery, searchType, sortBy, sortOrder]);

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
              <span>Auto-refreshing</span>
            </div>
            <LiveTrendChart points={trend} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)] items-start">
            <div className="rounded-3xl bg-slate-950/80 border border-white/10 backdrop-blur-xl p-5 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border border-white/20 px-4 py-3 rounded-xl">
                <span className="tracking-[0.12em] uppercase">Live Transactions</span>
                <span>Click any transaction</span>
              </div>
              <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                {rows.slice(0, 20).map((row) => {
                  const risk = getRiskMeta(row.fraud_score);
                  const isSelected = selectedTxnId === row.txn_id;

                  return (
                    <button
                      key={row.txn_id}
                      type="button"
                      onClick={() => setSelectedTxnId(row.txn_id)}
                      className={cn(
                        "w-full text-left rounded-2xl border px-4 py-3 transition-all",
                        isSelected
                          ? "border-indigo-400/70 bg-indigo-500/10"
                          : "border-slate-700/80 bg-slate-900/70 hover:border-indigo-400/40 hover:bg-slate-900"
                      )}
                    >
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={cn("inline-flex h-2.5 w-2.5 rounded-full", risk.dotClass)} />
                          <span className="text-slate-50 font-semibold tracking-[0.08em] uppercase text-base truncate">{row.txn_id}</span>
                          <span className="text-slate-300 truncate">{row.username || row.user_id}</span>
                        </div>
                        <span className="text-slate-200">Score: {row.fraud_score}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                        <span className="text-emerald-300 font-medium">
                          {new Intl.NumberFormat("en-IN", {
                            style: "currency",
                            currency: "INR",
                            maximumFractionDigits: 0,
                          }).format(row.amount)}
                        </span>
                        <span className="text-slate-300">{row.merchant_name}</span>
                        <span className="text-slate-400">
                          {new Date(row.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                        <span className="text-slate-400">{row.location}</span>
                      </div>
                      <div className="mt-2">
                        <span className={cn("inline-flex rounded-full border px-2 py-1 text-[10px]", risk.badgeClass)}>
                          {risk.label}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <aside className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4 lg:sticky lg:top-4">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">
                Transaction Details Sidebar
              </div>

              {selectedTransaction ? (
                <>
                  <div className="space-y-2">
                    <h3 className="text-lg font-semibold text-slate-100">{selectedTransaction.txn_id}</h3>
                    <span
                      className={cn(
                        "inline-flex rounded-full border px-2 py-1 text-xs",
                        getRiskMeta(selectedTransaction.fraud_score).badgeClass
                      )}
                    >
                      {getRiskMeta(selectedTransaction.fraud_score).label}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <DetailItem label="Username" value={selectedTransaction.username || selectedTransaction.user_id} />
                    <DetailItem label="User ID" value={selectedTransaction.user_id} />
                    <DetailItem
                      label="Amount"
                      value={new Intl.NumberFormat("en-IN", {
                        style: "currency",
                        currency: "INR",
                        maximumFractionDigits: 0,
                      }).format(selectedTransaction.amount)}
                    />
                    <DetailItem label="Score" value={String(selectedTransaction.fraud_score)} />
                    <DetailItem label="Merchant" value={selectedTransaction.merchant_name} />
                    <DetailItem
                      label="Time"
                      value={new Date(selectedTransaction.timestamp).toLocaleString()}
                    />
                    <DetailItem label="Location" value={selectedTransaction.location} />
                  </div>

                  <button
                    type="button"
                    className="w-full rounded-full border border-indigo-400/70 px-3 py-2 text-sm font-medium text-indigo-200 hover:bg-indigo-500/10 transition"
                  >
                    View Details
                  </button>
                </>
              ) : (
                <p className="text-sm text-slate-400">Select a transaction to view details.</p>
              )}
            </aside>
          </div>

          <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold tracking-tight">Users Data</h3>
                <p className="text-xs text-slate-400">
                  Search by type and sort by any major metric.
                </p>
              </div>
              <div className="flex flex-col md:flex-row gap-2 md:items-center">
                <select
                  value={searchType}
                  onChange={(event) => setSearchType(event.target.value as typeof searchType)}
                  className="rounded-xl bg-slate-900/80 border border-slate-700/80 px-3 py-2 text-xs text-slate-100"
                >
                  <option value="all">Search: All</option>
                  <option value="userId">Search: User ID</option>
                  <option value="username">Search: Username</option>
                  <option value="location">Search: Location</option>
                  <option value="risk">Search: Risk Type</option>
                </select>
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Type to search"
                  className="rounded-xl bg-slate-900/80 border border-slate-700/80 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500"
                />
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
                  className="rounded-xl bg-slate-900/80 border border-slate-700/80 px-3 py-2 text-xs text-slate-100"
                >
                  <option value="latestTime">Sort: Latest Time</option>
                  <option value="username">Sort: Username</option>
                  <option value="transactions">Sort: Transactions</option>
                  <option value="totalAmount">Sort: Total Amount</option>
                  <option value="avgScore">Sort: Average Score</option>
                </select>
                <button
                  type="button"
                  onClick={() =>
                    setSortOrder((current) => (current === "asc" ? "desc" : "asc"))
                  }
                  className="rounded-xl border border-indigo-400/60 px-3 py-2 text-xs text-indigo-200 hover:bg-indigo-500/10"
                >
                  {sortOrder === "asc" ? "Ascending" : "Descending"}
                </button>
              </div>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="w-full min-w-[840px] text-sm">
                <thead className="bg-slate-900/85 text-slate-300">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">User ID</th>
                    <th className="text-left px-4 py-3 font-medium">Username</th>
                    <th className="text-left px-4 py-3 font-medium">Transactions</th>
                    <th className="text-left px-4 py-3 font-medium">Total Amount</th>
                    <th className="text-left px-4 py-3 font-medium">Avg Score</th>
                    <th className="text-left px-4 py-3 font-medium">Latest Location</th>
                    <th className="text-left px-4 py-3 font-medium">Latest Time</th>
                    <th className="text-left px-4 py-3 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {userRows.map((item) => {
                    const riskClasses =
                      item.risk === "Fishy"
                        ? "text-rose-100 bg-rose-500/15 border-rose-400/60"
                        : item.risk === "Bit Risky"
                        ? "text-amber-100 bg-amber-500/15 border-amber-400/60"
                        : "text-emerald-100 bg-emerald-500/15 border-emerald-400/60";

                    return (
                      <tr key={item.userId} className="border-t border-white/5 hover:bg-white/5">
                        <td className="px-4 py-3 text-slate-300">{item.userId}</td>
                        <td className="px-4 py-3 text-slate-100 font-medium">{item.username}</td>
                        <td className="px-4 py-3 text-slate-300">{item.transactions}</td>
                        <td className="px-4 py-3 text-emerald-300">
                          {new Intl.NumberFormat("en-IN", {
                            style: "currency",
                            currency: "INR",
                            maximumFractionDigits: 0,
                          }).format(item.totalAmount)}
                        </td>
                        <td className="px-4 py-3 text-slate-200">{item.avgScore.toFixed(1)}</td>
                        <td className="px-4 py-3 text-slate-300">{item.latestLocation}</td>
                        <td className="px-4 py-3 text-slate-400">
                          {new Date(item.latestTime).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("inline-flex rounded-full border px-2 py-1 text-xs", riskClasses)}>
                            {item.risk}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
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

function createSyntheticTransaction(currentRows: LiveTransaction[]): LiveTransaction {
  const names = [
    "Rajesh",
    "Priya",
    "Suresh",
    "Ananya",
    "Vikram",
    "Neha",
    "Rohan",
    "Meera",
  ];
  const merchants = [
    "QuickShop",
    "CryptoXchange",
    "MetroMart",
    "TravelHub",
    "CloudKitchen",
    "GiftCard Vault",
    "RideNow",
    "New Merchant",
  ];
  const locations = [
    "Mumbai",
    "Delhi",
    "Hyderabad",
    "Pune",
    "Bengaluru",
    "Chennai",
    "Kolkata",
    "Ahmedabad",
  ];

  const pick = <T,>(items: T[]) => items[Math.floor(Math.random() * items.length)];
  const name = pick(names);
  const score = Math.floor(Math.random() * 100);
  const txnNum = currentRows.length + Math.floor(Math.random() * 1000);

  return {
    txn_id: `TXN${txnNum}`,
    user_id: name.toLowerCase(),
    username: name,
    amount: Math.floor(200 + Math.random() * 90000),
    fraud_score: score,
    merchant_name: pick(merchants),
    timestamp: new Date().toISOString(),
    location: pick(locations),
  };
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
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [profile, setProfile] = useState<UserProfileResponseApi | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsers() {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const search = encodeURIComponent(query.trim());
        const response = await fetch(
          `${baseUrl}/api/users/search?query=${search}&limit=30`,
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
  }, [query]);

  useEffect(() => {
    if (users.length === 0) {
      setSelectedUserId(null);
      return;
    }

    if (!selectedUserId || !users.some((user) => user.user_id === selectedUserId)) {
      setSelectedUserId(users[0].user_id);
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

  const selectedUser = users.find((user) => user.user_id === selectedUserId) ?? null;

  return (
    <section id="users" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto space-y-6">
        <div className="grid gap-4 lg:grid-cols-[minmax(360px,0.95fr)_minmax(0,1.05fr)] items-start">
          <div className="rounded-3xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 space-y-4">
            <div className="flex items-center gap-2">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search user by ID, name, city"
                className="w-full rounded-xl bg-slate-900/80 border border-slate-700/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
              />
            </div>

            {selectedUser && (
              <div className="rounded-2xl border border-white/20 bg-slate-950/75 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-lg font-medium text-slate-100">
                    <UserRound className="h-4 w-4 text-indigo-300" />
                    {selectedUser.name}
                  </div>
                  <span
                    className={cn(
                      "inline-flex rounded-full border px-2 py-1 text-xs",
                      selectedUser.risk_label.includes("HIGH")
                        ? "text-rose-100 bg-rose-500/15 border-rose-400/60"
                        : selectedUser.risk_label.includes("MEDIUM")
                        ? "text-amber-100 bg-amber-500/15 border-amber-400/60"
                        : "text-emerald-100 bg-emerald-500/15 border-emerald-400/60"
                    )}
                  >
                    {selectedUser.risk_label}
                  </span>
                </div>
                <div className="text-slate-300 text-sm">
                  {selectedUser.user_id} • {selectedUser.city} • Member since {new Date(selectedUser.member_since).toLocaleDateString()}
                </div>
                <div className="pt-1 text-sm text-slate-200 space-y-1">
                  <div>Behavioral Baseline</div>
                  <div>Avg Transaction: {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format((profile?.recent_transactions?.[0]?.amount ?? 650))}</div>
                  <div>
                    Usual Time: {selectedUser.usual_login_hour}:00 - {(selectedUser.usual_login_hour + 2) % 24}:00
                  </div>
                  <div>Trusted Devices: {selectedUser.trusted_devices}</div>
                  <div>Daily Avg Txns: {selectedUser.avg_txn_per_day.toFixed(1)}</div>
                </div>
              </div>
            )}

            <div className="space-y-2 max-h-[440px] overflow-y-auto pr-1">
              {users.map((user) => (
                <button
                  key={user.user_id}
                  type="button"
                  onClick={() => setSelectedUserId(user.user_id)}
                  className={cn(
                    "w-full text-left rounded-xl border px-3 py-2 transition-all",
                    selectedUserId === user.user_id
                      ? "border-indigo-400/70 bg-indigo-500/10"
                      : "border-slate-700/80 bg-slate-900/70 hover:border-indigo-400/40"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-slate-100 font-medium">{user.name}</span>
                    <span className="text-xs text-slate-400">{user.user_id}</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{user.city}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl bg-slate-950/80 border border-white/10 p-5 space-y-3">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Transaction History</div>
              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="bg-slate-900/80 text-slate-300">
                    <tr>
                      <th className="text-left px-3 py-2">Txn ID</th>
                      <th className="text-left px-3 py-2">Amount</th>
                      <th className="text-left px-3 py-2">Merchant</th>
                      <th className="text-left px-3 py-2">Score</th>
                      <th className="text-left px-3 py-2">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(profile?.recent_transactions ?? []).map((txn) => (
                      <tr key={txn.txn_id} className="border-t border-white/5">
                        <td className="px-3 py-2 text-slate-100 font-medium">{txn.txn_id}</td>
                        <td className="px-3 py-2 text-emerald-300">
                          {new Intl.NumberFormat("en-IN", {
                            style: "currency",
                            currency: "INR",
                            maximumFractionDigits: 0,
                          }).format(txn.amount)}
                        </td>
                        <td className="px-3 py-2 text-slate-300">{txn.merchant_name}</td>
                        <td className="px-3 py-2 text-slate-300">{txn.fraud_score}</td>
                        <td className="px-3 py-2 text-slate-400">{new Date(txn.timestamp).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-3xl bg-slate-950/80 border border-white/10 p-5 space-y-3">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Login History</div>
              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full min-w-[520px] text-sm">
                  <thead className="bg-slate-900/80 text-slate-300">
                    <tr>
                      <th className="text-left px-3 py-2">Time</th>
                      <th className="text-left px-3 py-2">Host (IP)</th>
                      <th className="text-left px-3 py-2">Status</th>
                      <th className="text-left px-3 py-2">Reason</th>
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
                        <td className="px-3 py-2 text-slate-400">{item.failure_reason || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
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
  const cityStats = [
    {
      city: "Mumbai",
      transactions: 2104,
      fraud: 12,
      tone: "danger" as const,
      location: [19.076, 72.8777] as [number, number],
    },
    {
      city: "Delhi",
      transactions: 1847,
      fraud: 8,
      tone: "warning" as const,
      location: [28.6139, 77.209] as [number, number],
    },
    {
      city: "Hyderabad",
      transactions: 923,
      fraud: 19,
      tone: "danger" as const,
      location: [17.385, 78.4867] as [number, number],
    },
    {
      city: "Bangalore",
      transactions: 1203,
      fraud: 3,
      tone: "success" as const,
      location: [12.9716, 77.5946] as [number, number],
    },
  ];

  const mapMarkers = cityStats.map((item) => ({
    id: item.city,
    location: item.location,
    visitors: item.transactions,
    trend: item.fraud,
    fraud: item.fraud,
    riskTone: item.tone,
  }));

  return (
    <section id="location" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto flex justify-center">
        <div className="w-full max-w-3xl space-y-4">
          <SectionTitle
            icon={Globe2}
            label="India Transaction Map"
            description="City-wise transaction and fraud snapshot from live feed."
          />
          <div className="space-y-5">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Bottom — Geographic Map</span>
              <span>Drag to explore city markers</span>
            </div>
            <div className="w-full max-w-md mx-auto">
              <GlobeAnalytics markers={mapMarkers} className="w-full" />
            </div>
          </div>
        </div>
      </div>
    </section>
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
