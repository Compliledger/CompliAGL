"use client";

import React, { useState } from "react";
import { HeroWaves } from "@/components/hero-waves";
import { CutButton } from "@/components/cut-button";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { executeIntent, getLatestProof, verifyIntent } from "@/lib/api";
import { MotionDiv, softEase, fadeInUp } from "@/lib/motion";
import {
  ArrowUpRight,
  BadgeCheck,
  FileText,
  Gauge,
  Play,
  Search,
  ShieldCheck,
  Timer,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

const DEMO_ACTOR_ID = "00000000-0000-0000-0000-000000000001";

const EMPTY_INTENT = {
  actor_id: DEMO_ACTOR_ID,
  action: "book_flight",
  amount: 100,
  currency: "USDC",
  payment_reference: "pay-demo-001",
};

type Intent = {
  actor_id: string;
  action: string;
  amount: number;
  currency: string;
  payment_reference?: string;
  payment?: {
    reference: string;
  };
};

const CUT =
  "[clip-path:polygon(5px_0,100%_0,100%_calc(100%-5px),calc(100%-5px)_100%,0_100%,0_5px)]";

type NavItem = { label: string; icon: LucideIcon; active?: boolean };

const PORTAL_NAV_ITEMS: NavItem[] = [
  { label: "Overview", icon: Gauge, active: true },
  { label: "Intents", icon: Play },
  { label: "Executions", icon: Workflow },
  { label: "Proofs", icon: ShieldCheck },
  { label: "Actors", icon: BadgeCheck },
  { label: "Reports", icon: FileText },
];

type ActiveView = "Overview" | "Intents" | "Executions" | "Proofs" | "Actors" | "Reports";

type Kpi = {
  label: string;
  value: string;
  delta: string;
  dir: "up" | "down";
  icon: LucideIcon;
};

function getDynamicKpis(form: Intent, verifyResult: { decision: { result: string; reason_codes?: string[] } } | null, executeResult: any, proof: any): Kpi[] {
  return [
    {
      label: "Current Intent",
      value: form.action || "—",
      delta: verifyResult ? verifyResult.decision.result : "Pending",
      dir: "up",
      icon: Play,
    },
    {
      label: "Execution Status",
      value: executeResult?.status || "Pending",
      delta: executeResult?.payment?.payment_verified ? "Verified" : "Unverified",
      dir: "up",
      icon: Workflow,
    },
    {
      label: "Proof Status",
      value: proof ? "Generated" : "Not available",
      delta: proof?.policy_version || "v1.0",
      dir: "up",
      icon: ShieldCheck,
    },
    {
      label: "Governance State",
      value: verifyResult ? "Active" : "Ready",
      delta: form.amount ? `${form.amount} ${form.currency}` : "No amount",
      dir: "down",
      icon: Timer,
    },
  ];
}

function PortalSidebar({ activeView, setActiveView, form, verifyResult, executeResult, proof }: {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  form: Intent;
  verifyResult: { decision: { result: string; reason_codes?: string[] } } | null;
  executeResult: any;
  proof: any;
}): ReactNode {
  const getSidebarContent = () => {
    switch (activeView) {
      case "Overview":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">System Status</span>
                <span className="text-[10px] text-green-500">● All systems operational</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Last Activity</span>
                <span className="text-[10px] text-muted-foreground">
                  {verifyResult ? "Intent verified" : "Ready for input"}
                </span>
              </span>
            </div>
          </div>
        );
      case "Intents":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Current Intent</span>
                <span className="text-[10px] text-muted-foreground truncate">{form.action}</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Amount</span>
                <span className="text-[10px] text-muted-foreground">{form.amount} {form.currency}</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Actor</span>
                <span className="text-[10px] text-muted-foreground font-mono">{form.actor_id.slice(0, 8)}...</span>
              </span>
            </div>
          </div>
        );
      case "Executions":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Execution Status</span>
                <span className={`text-[10px] ${executeResult?.status === "EXECUTED" ? "text-green-500" : "text-yellow-500"}`}>
                  {executeResult?.status || "Pending"}
                </span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Payment Verified</span>
                <span className={`text-[10px] ${executeResult?.payment?.payment_verified ? "text-green-500" : "text-muted-foreground"}`}>
                  {executeResult?.payment?.payment_verified ? "Yes" : "No"}
                </span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Network</span>
                <span className="text-[10px] text-muted-foreground">{executeResult?.payment?.network || "—"}</span>
              </span>
            </div>
          </div>
        );
      case "Proofs":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Proof Status</span>
                <span className={`text-[10px] ${proof ? "text-blue-500" : "text-muted-foreground"}`}>
                  {proof ? "Generated" : "Not available"}
                </span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Policy Version</span>
                <span className="text-[10px] text-muted-foreground">{proof?.policy_version || "—"}</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Settlement Chain</span>
                <span className="text-[10px] text-muted-foreground">{proof?.settlement_chain || "—"}</span>
              </span>
            </div>
          </div>
        );
      case "Actors":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Active Actor</span>
                <span className="text-[10px] text-muted-foreground font-mono">{form.actor_id.slice(0, 8)}...</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Actor Type</span>
                <span className="text-[10px] text-muted-foreground">Travel Agent</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Permissions</span>
                <span className="text-[10px] text-green-500">Full Access</span>
              </span>
            </div>
          </div>
        );
      case "Reports":
        return (
          <div className="space-y-2">
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Report Status</span>
                <span className="text-[10px] text-muted-foreground">Generating...</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Data Range</span>
                <span className="text-[10px] text-muted-foreground">Last 24 hours</span>
              </span>
            </div>
            <div className="rounded-md border border-border/60 bg-background px-2.5 py-2">
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium">Export Format</span>
                <span className="text-[10px] text-muted-foreground">PDF, CSV</span>
              </span>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <aside className="hidden w-[240px] shrink-0 flex-col border-r border-border/60 bg-muted/20 lg:flex">
      <div className="flex h-14 items-center gap-2.5 border-b border-border/60 px-4">
        <span className={`h-6 w-6 bg-foreground ${CUT}`} aria-hidden="true" />
        <span className="text-[15px] font-semibold tracking-tight">
          CompliAGL
        </span>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 p-3">
        <p className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
          Workspace
        </p>
        {PORTAL_NAV_ITEMS.map((item) => (
          <button
            key={item.label}
            onClick={() => setActiveView(item.label as ActiveView)}
            disabled={item.label !== "Overview"}
            className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors text-left ${
              item.label === "Overview"
                ? "bg-foreground/[0.06] font-medium text-foreground"
                : "text-muted-foreground/50 cursor-not-allowed"
            }`}
          >
            <item.icon
              className="h-[15px] w-[15px]"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="border-t border-border/60 p-3">
        <p className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
          Live Readout
        </p>
        {getSidebarContent()}
      </div>
    </aside>
  );
}

function PortalTopbar(): ReactNode {
  return (
    <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4 sm:px-5">
      <div className="flex min-w-0 flex-col">
        <h2 className="truncate text-sm font-semibold tracking-tight">
          Governance Portal
        </h2>
        <p className="hidden text-[11px] text-muted-foreground sm:block">
          Intent → Verify → Execute → Proof
        </p>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden h-8 w-44 items-center gap-2 rounded-md border border-border/60 bg-muted/40 px-2.5 text-muted-foreground md:flex">
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="text-xs">Search</span>
          <kbd className="ml-auto rounded border border-border/60 bg-background px-1 text-[10px] font-medium">
            ⌘K
          </kbd>
        </div>
        <span className="grid h-8 w-8 place-items-center rounded-full bg-foreground text-[11px] font-semibold text-background">
          OP
        </span>
      </div>
    </div>
  );
}

function KpiCard({ kpi }: { kpi: Kpi }): ReactNode {
  const Arrow = ArrowUpRight;
  return (
    <div className="flex flex-col justify-between rounded-lg border border-border/60 bg-background p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-muted-foreground">{kpi.label}</span>
        <kpi.icon
          className="h-3.5 w-3.5 text-muted-foreground/60"
          strokeWidth={1.75}
          aria-hidden="true"
        />
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="text-xl font-semibold tracking-tight">
          {kpi.value}
        </span>
        <span className="flex items-center gap-0.5 text-[11px] font-medium text-muted-foreground">
          <Arrow className="h-3 w-3" aria-hidden="true" />
          {kpi.delta}
        </span>
      </div>
    </div>
  );
}

function WorkflowCard({ title, subtitle, kicker, className = "", children }: { title: string; subtitle?: string; kicker?: string; className?: string; children: ReactNode }) {
  return (
    <div className={`flex min-h-0 flex-col rounded-lg border border-border/60 bg-background p-4 ${className}`.trim()}>
      <div className="flex items-start justify-between">
        <div>
          {kicker && <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">{kicker}</p>}
          <h3 className="text-[13px] font-semibold tracking-tight">
            {title}
          </h3>
          {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="mt-3 flex-1">
        {children}
      </div>
    </div>
  );
}

export default function PortalPage(): ReactNode {
  const [form, setForm] = useState<Intent>(EMPTY_INTENT);
  const [verifyResult, setVerifyResult] = useState<{ decision: { result: string; reason_codes?: string[] } } | null>(null);
  const [executeResult, setExecuteResult] = useState<any>(null);
  const [proof, setProof] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("Overview");

  function clearRunState() {
    setVerifyResult(null);
    setExecuteResult(null);
    setProof(null);
    setError(null);
  }

  function buildIntent(): Intent {
    const intent: Intent = {
      actor_id: form.actor_id,
      action: form.action,
      amount: Number(form.amount),
      currency: form.currency,
    };
    if (form.payment_reference) {
      intent.payment = { reference: form.payment_reference };
    }
    return intent;
  }

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    clearRunState();
    setForm((prev) => ({
      ...prev,
      [name]: name === "amount" ? Number(value) : value,
    }));
  };

  const onVerify = async () => {
    setError(null);
    setLoading(true);
    setExecuteResult(null);
    setProof(null);

    const { ok, data } = await verifyIntent(buildIntent());

    setLoading(false);

    if (!ok || !data) {
      setError("We could not review this request right now. Please try again.");
      return;
    }

    setVerifyResult(data);
  };

  const onExecute = async () => {
    setError(null);
    setLoading(true);
    const { data } = await executeIntent(buildIntent());

    setLoading(false);

    if (!data) {
      setError("We could not complete this run right now. Please try again.");
      return;
    }

    setExecuteResult(data);
  };

  const onLoadLatestProof = async () => {
    setError(null);
    setLoading(true);

    const { ok, data } = await getLatestProof();

    setLoading(false);

    if (!ok || !data) {
      setError("There is no saved proof available yet.");
      return;
    }

    setProof(data);
  };

  const resetWorkspace = () => {
    setForm(EMPTY_INTENT);
    clearRunState();
  };

  return (
    <>
      <Nav />
      <main id="main-content" className="flex-1 relative overflow-hidden">
        <HeroWaves />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(60% 50% at 50% -5%, color-mix(in srgb, var(--foreground) 5%, transparent), transparent 70%)",
          }}
        />

        <div className="mx-auto max-w-[1440px] px-5 py-12 sm:px-8 sm:py-16 lg:px-10 lg:py-20">
          <MotionDiv
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
            transition={{ duration: 0.8, ease: softEase }}
            className="max-w-2xl mx-auto text-center mb-12"
          >
            <h1 className="text-balance font-serif text-4xl font-normal leading-[1.1] tracking-[-0.01em] sm:text-5xl lg:text-[3.5rem]">
              Governance{" "}
              <span className="font-sans font-medium tracking-tight">
                Portal
              </span>
            </h1>
            <p className="mt-4 max-w-xl text-balance text-[15px] leading-relaxed text-muted-foreground sm:text-base">
              Professional workspace for intent preparation, policy verification, governed execution, and machine-verifiable proof.
            </p>
          </MotionDiv>

          <div className="mx-auto max-w-[1400px] overflow-hidden rounded-2xl border border-border/60 bg-background shadow-2xl shadow-black/[0.08]">
            <div className="relative flex h-7 items-center border-b border-border/60 px-2.5">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
              </div>
              <span className="pointer-events-none absolute inset-x-0 text-center text-xs font-normal text-muted-foreground">
                CompliAGL Portal
              </span>
            </div>

            <div className="flex min-h-[700px]">
              <PortalSidebar
                activeView={activeView}
                setActiveView={setActiveView}
                form={form}
                verifyResult={verifyResult}
                executeResult={executeResult}
                proof={proof}
              />

              <section className="flex min-w-0 flex-1 flex-col">
                <PortalTopbar />

                <main className="flex min-h-0 flex-1 flex-col gap-3 p-3 sm:p-4">
                  {error && (
                    <MotionDiv
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="shrink-0 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-xs"
                    >
                      {error}
                    </MotionDiv>
                  )}

                  {activeView === "Overview" && (
                    <>
                      <div className="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
                        {getDynamicKpis(form, verifyResult, executeResult, proof).map((kpi) => (
                          <KpiCard key={kpi.label} kpi={kpi} />
                        ))}
                      </div>

                      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-2">
                        <WorkflowCard
                          title="Intent Configuration"
                          subtitle="Define actor, action, amount, and payment context"
                          kicker="Step 1"
                        >
                          <div className="space-y-3">
                            <label className="block">
                              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 block">Actor ID</span>
                              <input
                                name="actor_id"
                                value={form.actor_id}
                                onChange={onChange}
                                className="w-full bg-muted/50 border border-border rounded-md px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 block">Action</span>
                              <input
                                name="action"
                                value={form.action}
                                onChange={onChange}
                                className="w-full bg-muted/50 border border-border rounded-md px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                            </label>
                            <div className="grid grid-cols-2 gap-2">
                              <label className="block">
                                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 block">Amount</span>
                                <input
                                  name="amount"
                                  type="number"
                                  value={form.amount}
                                  onChange={onChange}
                                  className="w-full bg-muted/50 border border-border rounded-md px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                              </label>
                              <label className="block">
                                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 block">Currency</span>
                                <input
                                  name="currency"
                                  value={form.currency}
                                  onChange={onChange}
                                  className="w-full bg-muted/50 border border-border rounded-md px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                              </label>
                            </div>
                            <label className="block">
                              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 block">Payment Reference</span>
                              <input
                                name="payment_reference"
                                value={form.payment_reference}
                                onChange={onChange}
                                placeholder="Optional"
                                className="w-full bg-muted/50 border border-border rounded-md px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                            </label>
                            <div className="flex gap-2 pt-1">
                              <CutButton variant="solid" onClick={onVerify} disabled={loading} className="text-xs h-8">
                                {loading ? "Verifying..." : "Verify Intent"}
                              </CutButton>
                              <CutButton variant="outline" onClick={resetWorkspace} disabled={loading} className="text-xs h-8">
                                Reset
                              </CutButton>
                            </div>
                          </div>
                        </WorkflowCard>

                        <WorkflowCard
                          title="Decision Result"
                          subtitle="Policy evaluation with reason codes"
                          kicker="Step 2"
                        >
                          {verifyResult ? (
                            <div className="space-y-2">
                              <div className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium ${
                                verifyResult.decision.result === "APPROVED"
                                  ? "bg-green-500/10 text-green-500"
                                  : "bg-red-500/10 text-red-500"
                              }`}>
                                {verifyResult.decision.result}
                              </div>
                              <div className="space-y-1 pt-1">
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Action</span>
                                  <span className="text-xs font-medium">{form.action}</span>
                                </div>
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Amount</span>
                                  <span className="text-xs font-medium">{`${form.amount} ${form.currency}`}</span>
                                </div>
                                {verifyResult.decision.reason_codes && (
                                  <div className="flex justify-between items-center py-1">
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Reason Codes</span>
                                    <span className="text-xs font-medium">{verifyResult.decision.reason_codes.join(", ")}</span>
                                  </div>
                                )}
                              </div>
                              {verifyResult.decision.result === "APPROVED" && (
                                <div className="pt-2">
                                  <CutButton variant="solid" onClick={onExecute} disabled={loading} className="text-xs h-8 w-full">
                                    {loading ? "Executing..." : "Execute Intent"}
                                  </CutButton>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-center py-6 text-muted-foreground text-xs">
                              Verify the intent to see the governance decision.
                            </div>
                          )}
                        </WorkflowCard>

                        <WorkflowCard
                          title="Execution Outcome"
                          subtitle="Payment verification and execution status"
                          kicker="Step 3"
                        >
                          {executeResult ? (
                            <div className="space-y-2">
                              <div className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium ${
                                executeResult.status === "EXECUTED"
                                  ? "bg-green-500/10 text-green-500"
                                  : "bg-yellow-500/10 text-yellow-500"
                              }`}>
                                {executeResult.status}
                              </div>
                              <div className="space-y-1 pt-1">
                                {executeResult.payment && (
                                  <>
                                    <div className="flex justify-between items-center py-1 border-b border-border/50">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Payment Verified</span>
                                      <span className="text-xs font-medium">{executeResult.payment.payment_verified ? "Yes" : "No"}</span>
                                    </div>
                                    <div className="flex justify-between items-center py-1 border-b border-border/50">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Network</span>
                                      <span className="text-xs font-medium">{executeResult.payment.network || "—"}</span>
                                    </div>
                                    <div className="flex justify-between items-center py-1 border-b border-border/50">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Reference</span>
                                      <span className="text-xs font-medium">{executeResult.payment.payment_reference || "—"}</span>
                                    </div>
                                  </>
                                )}
                                {executeResult.execution && (
                                  <>
                                    <div className="flex justify-between items-center py-1 border-b border-border/50">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Execution Status</span>
                                      <span className="text-xs font-medium">{executeResult.execution.status}</span>
                                    </div>
                                    <div className="flex justify-between items-center py-1 border-b border-border/50">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Reference</span>
                                      <span className="text-xs font-medium">{executeResult.execution.execution_reference || "—"}</span>
                                    </div>
                                    <div className="flex justify-between items-center py-1">
                                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Timestamp</span>
                                      <span className="text-xs font-medium">{executeResult.execution.timestamp || "—"}</span>
                                    </div>
                                  </>
                                )}
                              </div>
                              <div className="pt-2">
                                <CutButton variant="outline" onClick={onLoadLatestProof} disabled={loading} className="text-xs h-8 w-full">
                                  {loading ? "Loading..." : "Load Latest Proof"}
                                </CutButton>
                              </div>
                            </div>
                          ) : (
                            <div className="text-center py-6 text-muted-foreground text-xs">
                              Execute the intent to see the outcome.
                            </div>
                          )}
                        </WorkflowCard>

                        <WorkflowCard
                          title="Proof Summary"
                          subtitle="Canonical evidence package with identifiers"
                          kicker="Step 4"
                        >
                          {proof ? (
                            <div className="space-y-2">
                              <div className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-blue-500/10 text-blue-500">
                                Proof Verified
                              </div>
                              <div className="space-y-1 pt-1">
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Proof ID</span>
                                  <span className="text-xs font-medium">{proof.proof_id}</span>
                                </div>
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Proof Hash</span>
                                  <span className="text-xs font-medium">{proof.proof_hash}</span>
                                </div>
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Policy Version</span>
                                  <span className="text-xs font-medium">{proof.policy_version}</span>
                                </div>
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Created At</span>
                                  <span className="text-xs font-medium">{proof.created_at}</span>
                                </div>
                                <div className="flex justify-between items-center py-1 border-b border-border/50">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Settlement Chain</span>
                                  <span className="text-xs font-medium">{proof.settlement_chain || "—"}</span>
                                </div>
                                <div className="flex justify-between items-center py-1">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Anchor Chain</span>
                                  <span className="text-xs font-medium">{proof.anchor_chain || "—"}</span>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="text-center py-6 text-muted-foreground text-xs">
                              Load the latest proof to see the audit summary.
                            </div>
                          )}
                        </WorkflowCard>
                      </div>
                    </>
                  )}

                  {activeView !== "Overview" && (
                    <div className="flex-1 flex items-center justify-center">
                      <div className="text-center">
                        <h3 className="text-lg font-semibold tracking-tight mb-2">{activeView}</h3>
                        <p className="text-sm text-muted-foreground">
                          This view is under development. Navigate to Overview to access the governance workflow.
                        </p>
                      </div>
                    </div>
                  )}
                </main>
              </section>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
