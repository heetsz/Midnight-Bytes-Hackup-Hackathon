// @ts-nocheck

import { useState } from "react";
import SectionWithMockup from "@/components/ui/section-with-mockup";
import FloatingActionMenu from "@/components/ui/floating-action-menu";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
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
  Info,
  LayoutDashboard,
  Layers,
  ShieldCheck,
  UserRound,
  XCircle,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "transaction-analysis", label: "Transaction Analysis", icon: CreditCard },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "user-behavior", label: "User Behavior", icon: UserRound },
  { id: "alerts", label: "Alerts", icon: BellRing },
  { id: "simulation", label: "Simulation", icon: Activity },
  { id: "about", label: "About", icon: Info },
];

export function DashboardApp() {
  const navigate = useNavigate();

  const [activeSection, setActiveSection] = useState<string>("dashboard");

  return (
    <div className="min-h-screen flex bg-black text-slate-50">
      <Sidebar activeSection={activeSection} onSelectSection={setActiveSection} />
      <div className="flex-1 flex flex-col">
        <main className="flex-1 overflow-y-auto px-4 md:px-8 pb-16 space-y-16 bg-black">
          <FloatingActionMenu
            options={[
              {
                label: "Logout",
                Icon: <LogOut className="w-4 h-4" />,
                onClick: () => navigate("/login"),
              },
            ]}
          />
          {activeSection === "dashboard" && <DashboardSection />}
          {activeSection === "transaction-analysis" && (
            <TransactionAnalysisSection />
          )}
          {activeSection === "analytics" && <AnalyticsSection />}
          {activeSection === "user-behavior" && <UserBehaviorSection />}
          {activeSection === "alerts" && <AlertsSection />}
          {activeSection === "simulation" && <SimulationSection />}
          {activeSection === "about" && <AboutSection />}
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
      <div className="px-4 py-6 border-t border-white/10 text-[11px] text-slate-500 flex flex-col gap-1">
        <span>LIVE · Bank-grade security</span>
        <span className="text-slate-600">
          Powered by explainable AI
        </span>
      </div>
    </aside>
  );
}

function DashboardSection() {
  return (
    <section id="dashboard" className="space-y-8 pt-4">
      <div className="grid gap-4 md:grid-cols-4">
        <DashboardCard
          label="Total Transactions"
          value="2,184,392"
          helper="Today"
          chip={{ label: "+8.2%", tone: "success" }}
        />
        <DashboardCard
          label="Fraud Detected"
          value="1,284"
          helper="Last 24h"
          chip={{ label: "+23% vs baseline", tone: "danger" }}
        />
        <DashboardCard
          label="Fraud Rate"
          value="0.06%"
          helper="Below risk threshold"
          chip={{ label: "Safe", tone: "success" }}
        />
        <RiskLevelCard />
      </div>
    </section>
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Transaction Analysis &amp; AI Risk Scoring
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Simulate any card, UPI, or wire transaction and see how the AI
              allocates fraud scores, risk levels, and decisions in real time.
            </p>
          </div>
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
      </div>
    </section>
  );
}

function ExplainableSection() {
  return (
    <section id="explainable-ai" className="space-y-10">
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6 space-y-4">
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6">
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6 space-y-4">
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
                    <div className="absolute inset-[6px] rounded-full bg-conic-to-r from-emerald-400 via-emerald-400 via-emerald-400 to-rose-500 opacity-90" />
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6 space-y-4">
        <div className="grid gap-8 md:grid-cols-2 items-start">
          <div className="space-y-4 max-w-[520px]">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Alerts &amp; Case Management
            </h2>
            <p className="text-sm md:text-[15px] text-slate-400 leading-6">
              Monitor a live stream of suspicious transactions, route HIGH risk
              cases to manual review, and approve or block with one-click
              actions.
            </p>
          </div>
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6">
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
      <div className="container max-w-[1220px] w-full px-6 md:px-10 mx-auto -mt-6">
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
