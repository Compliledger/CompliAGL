"use client";

import React, { useState } from "react";
import type { CSSProperties } from "react";
import { HeroWaves } from "@/components/hero-waves";
import { CornerPlus } from "@/components/corner-plus";
import { CutButton } from "@/components/cut-button";
import { executeIntent, getLatestProof, verifyIntent } from "@/lib/api";
import { MotionDiv, MotionSection, softEase } from "@/lib/motion";
import "./globals.css";

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

type Decision = {
  result: string;
  reason_codes?: string[];
};

type Payment = {
  payment_verified: boolean;
  network?: string;
  payment_reference?: string;
};

type Execution = {
  status: string;
  execution_reference?: string;
  timestamp?: string;
};

type Anchor = {
  reason?: string;
  anchor_tx_id?: string;
};

type Proof = {
  proof_id: string;
  proof_hash: string;
  decision?: string;
  policy_version: string;
  created_at: string;
  intent?: {
    action: string;
  };
  settlement_chain?: string;
  anchor_chain?: string;
  anchor_tx_id?: string;
  actor_identity?: {
    name: string;
  };
};

type ExecuteResult = {
  status: string;
  decision?: Decision;
  payment?: Payment;
  execution?: Execution;
  anchor?: Anchor;
  proof?: Proof;
};

type JourneyState = "complete" | "pending" | "current" | "warning";

type JourneyItem = {
  title: string;
  description: string;
  state: JourneyState;
};

type InsightItem = {
  title: string;
  body: string;
};

const CARD_CLIP =
  "polygon(0 0, calc(100% - 34px) 0, 100% 34px, 100% 100%, 0 100%)";

function Section({ title, subtitle, kicker, className = "", children }: { title: string; subtitle?: string; kicker?: string; className?: string; children: React.ReactNode }) {
  const clip = { clipPath: CARD_CLIP } as CSSProperties;
  return (
    <MotionSection
      transition={{ duration: 0.7, ease: softEase }}
      className={`dashboard-section ${className}`.trim()}
    >
      <div className="bg-border p-px" style={clip}>
        <section className="card card-cut card-frame bg-background" style={clip}>
          <CornerPlus className="left-0 top-0 -translate-x-1/2 -translate-y-1/2" />
          <CornerPlus className="right-0 top-0 translate-x-1/2 -translate-y-1/2" />
          <CornerPlus className="bottom-0 left-0 -translate-x-1/2 translate-y-1/2" />
          <CornerPlus className="bottom-0 right-0 translate-x-1/2 translate-y-1/2" />
          <div className="card-head">
            {kicker && <span className="card-kicker">{kicker}</span>}
            <h2 className="card-title">{title}</h2>
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          <div className="card-body">{children}</div>
        </section>
      </div>
    </MotionSection>
  );
}

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <span className="field-value">{value ?? "—"}</span>
    </div>
  );
}

function CopyableField({ label, value, displayValue }: { label: string; value: string | undefined; displayValue: string | undefined }) {
  const resolvedValue = value ?? "—";

  async function onCopy() {
    if (!value || !navigator?.clipboard?.writeText) {
      return;
    }
    await navigator.clipboard.writeText(value);
  }

  return (
    <div className="field field-copyable">
      <span className="field-label">{label}</span>
      <div className="field-copy-row">
        <span className="field-value field-value-mono">{displayValue || resolvedValue}</span>
        <button className="copy-button" onClick={onCopy} type="button">
          Copy
        </button>
      </div>
    </div>
  );
}

function SectionGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="detail-group">
      <div className="detail-group-title">{title}</div>
      {children}
    </div>
  );
}

function StatusPill({ status, label }: { status?: string; label?: string }) {
  if (!status) return null;
  const cls = `pill pill-${String(status).toLowerCase().replace(/_/g, "-")}`;
  return <span className={cls}>{label || statusLabel(status)}</span>;
}

function JourneyItem({ title, description, state }: { title: string; description: string; state: JourneyState }) {
  return (
    <div className={`journey-item is-${state}`.trim()}>
      <span className="journey-marker" />
      <div className="journey-copy">
        <strong className="journey-title">{title}</strong>
        <p className="journey-description">{description}</p>
      </div>
    </div>
  );
}

function InsightCard({ title, body }: { title: string; body: string }) {
  return (
    <article className="insight-card">
      <strong className="insight-title">{title}</strong>
      <p className="insight-body">{body}</p>
    </article>
  );
}

function humanizeStatus(value: string): string {
  return String(value || "")
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusLabel(status: string): string {
  const value = String(status || "").toUpperCase();
  const statusMap: Record<string, string> = {
    APPROVED: "✓ Approved",
    EXECUTED: "⚡ Executed",
    CONFIRMED: "✓ Payment Confirmed",
    PAYMENT_REQUIRED: "◌ Payment Required",
    PAYMENT_FAILED: "! Payment Failed",
    DENIED: "✕ Denied",
    ESCALATION_REQUIRED: "→ Escalation Required",
  };

  return statusMap[value] || humanizeStatus(status);
}

function truncateMiddle(value: string, start = 10, end = 6): string {
  if (!value || value.length <= start + end + 1) return value || "—";
  return `${value.slice(0, start)}…${value.slice(-end)}`;
}

function formatNetwork(value: string): string {
  if (!value) return "—";
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatAmount(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null || Number.isNaN(Number(amount))) {
    return "—";
  }
  return `${amount} ${currency}`;
}

function decisionSummary(decision: Decision): string {
  if (!decision) {
    return "Submit the request for governance review to see whether it can proceed.";
  }
  if (decision.result === "APPROVED") {
    return "This request passed policy review and is ready for payment-gated execution.";
  }
  if (decision.result === "ESCALATION_REQUIRED") {
    return "This request needs escalation before it can move forward.";
  }
  if (decision.result === "DENIED") {
    return "This request did not pass governance review and cannot be executed.";
  }
  return "A governance decision has been recorded for this request.";
}

function paymentSummary(executeResult: ExecuteResult, payment: Payment | null, execution: Execution | null): string {
  if (!executeResult) {
    return "Execution has not started yet. Once you run the request, payment handling and settlement details will appear here.";
  }
  if (executeResult.status === "PAYMENT_REQUIRED") {
    return "The action is approved, but payment evidence is required before execution can continue.";
  }
  if (executeResult.status === "PAYMENT_FAILED") {
    return "Payment verification did not succeed, so the action was not completed.";
  }
  if (payment?.payment_verified && execution?.status === "CONFIRMED") {
    return "Payment was accepted and the action completed successfully through the execution adapter.";
  }
  return "Execution details are available for this governed request.";
}

function proofSummary(proof: Proof, anchor: Anchor | null): string {
  if (!proof) {
    return "When execution completes, the platform will present a clean proof summary here instead of raw payloads.";
  }
  if (anchor?.reason) {
    return "The AIProof was generated successfully. Anchoring is unavailable in this environment, so the proof is shown without an on-chain receipt.";
  }
  return "A proof bundle has been generated for this governed action and is ready for audit review.";
}

export default function DashboardPage() {
  const [form, setForm] = useState<Intent>(EMPTY_INTENT);
  const [verifyResult, setVerifyResult] = useState<{ decision: Decision } | null>(null);
  const [executeResult, setExecuteResult] = useState<ExecuteResult | null>(null);
  const [proof, setProof] = useState<Proof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);

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

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    clearRunState();
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function resetWorkspace() {
    setForm(EMPTY_INTENT);
    clearRunState();
  }

  async function onVerify() {
    setError(null);
    setLoading(true);
    setActiveAction("verify");
    setExecuteResult(null);
    setProof(null);

    const { ok, data } = await verifyIntent(buildIntent());

    setLoading(false);
    setActiveAction(null);

    if (!ok || !data) {
      setError("We could not review this request right now. Please try again.");
      return;
    }

    setVerifyResult(data);
  }

  async function onExecute() {
    setError(null);
    setLoading(true);
    setActiveAction("execute");
    const { data } = await executeIntent(buildIntent());

    setLoading(false);
    setActiveAction(null);

    if (!data) {
      setError("We could not complete this run right now. Please try again.");
      return;
    }

    setExecuteResult(data);
  }

  async function onLoadLatestProof() {
    setError(null);
    setLoading(true);
    setActiveAction("proof");

    const { ok, data } = await getLatestProof();

    setLoading(false);
    setActiveAction(null);

    if (!ok || !data) {
      setError("There is no saved proof available yet.");
      return;
    }

    setProof(data);
  }

  const decision = executeResult?.decision || verifyResult?.decision || null;
  const payment = executeResult?.payment || null;
  const execution = executeResult?.execution || null;
  const anchor = executeResult?.anchor || null;
  const actorIdentity = proof?.actor_identity || null;
  const actorName = actorIdentity?.name || "TravelAgent-01";
  const journey: JourneyItem[] = [
    {
      title: "Intent prepared",
      description: `${form.action || "Action"} for ${formatAmount(form.amount, form.currency)} is ready for review.`,
      state: "complete",
    },
    {
      title: "Governance reviewed",
      description: decision
        ? decisionSummary(decision)
        : "Run a review first to see whether this request can proceed.",
      state: decision ? "complete" : "pending",
    },
    {
      title: "Payment handled",
      description: executeResult
        ? executeResult.status === "PAYMENT_REQUIRED"
          ? "A payment reference is required before the approved action can continue."
          : payment?.payment_verified
            ? "Payment verification succeeded for this governed action."
            : "Payment handling has been recorded for this run."
        : "Payment will only be evaluated when you run the action.",
      state: executeResult
        ? payment?.payment_verified
          ? "complete"
          : executeResult.status === "PAYMENT_REQUIRED"
            ? "current"
            : "warning"
        : "pending",
    },
    {
      title: "Execution completed",
      description: execution?.status === "CONFIRMED"
        ? "The request finished successfully through the configured execution adapter."
        : "Execution outcome will appear here after the governed action runs.",
      state: execution?.status === "CONFIRMED" ? "complete" : "pending",
    },
    {
      title: "Proof prepared",
      description: proof
        ? "A clean audit summary is available for review."
        : "Proof details will appear after execution or when you load the latest proof.",
      state: proof ? "complete" : "pending",
    },
  ];
  const topMessage = proof
    ? "Governed action completed with an audit-ready proof summary."
    : executeResult?.status === "PAYMENT_REQUIRED"
      ? "Approval is in place, but a payment reference is still required to finish the run."
      : decision?.result === "APPROVED"
        ? "This request is approved and ready to move into execution."
        : "Prepare and review a request before moving into execution and proof generation.";
  const insightItems: InsightItem[] = [
    {
      title: "Review before action",
      body: "The request is checked against governance rules before execution is allowed to start.",
    },
    {
      title: "Payment-gated execution",
      body: "Approved actions still need valid payment evidence before the system completes them.",
    },
    {
      title: "Audit-ready proof",
      body: "Successful runs produce a concise, human-readable proof summary for operators and reviewers.",
    },
  ];
  const overviewStats = [
    {
      label: "Policy review",
      value: decision ? humanizeStatus(decision.result) : "Awaiting review",
      detail: "Deterministic governance gate",
    },
    {
      label: "Execution state",
      value: execution?.status
        ? humanizeStatus(execution.status)
        : executeResult?.status
          ? humanizeStatus(executeResult.status)
          : "Not started",
      detail: "Controlled runtime progression",
    },
    {
      label: "Proof posture",
      value: proof ? "Audit-ready" : "Pending",
      detail: "Canonical evidence package",
    },
  ];

  return (
    <main id="main-content" className="app-shell dashboard-page">
      <HeroWaves />
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <div className="ambient ambient-three" />
      <div className="mesh-overlay" />

      <div className="app">
        <MotionDiv
          transition={{ duration: 0.6, ease: softEase }}
          className="dashboard-topbar"
        >
          <a className="dashboard-brand" href="/">
            <span className="dashboard-brand-mark" aria-hidden="true" />
            <span className="dashboard-brand-copy">
              <strong>CompliAGL</strong>
              <span>Operator Workspace</span>
            </span>
          </a>

          <div className="dashboard-topbar-meta">
            <span className="dashboard-chip">Deterministic Governance</span>
            <span className="dashboard-chip dashboard-chip-muted">Machine-Verifiable Proof</span>
          </div>
        </MotionDiv>

        <MotionSection
          transition={{ duration: 0.8, ease: softEase }}
          className="hero-panel card card-cut card-frame"
        >
          <CornerPlus className="left-0 top-0 -translate-x-1/2 -translate-y-1/2" />
          <CornerPlus className="right-0 top-0 translate-x-1/2 -translate-y-1/2" />
          <CornerPlus className="bottom-0 left-0 -translate-x-1/2 translate-y-1/2" />
          <CornerPlus className="bottom-0 right-0 translate-x-1/2 translate-y-1/2" />
          <div className="hero-copy">
            <span className="eyebrow">Governed Autonomous Execution</span>
            <h1 className="hero-title">
              Govern AI execution with the same clarity as the landing experience.
            </h1>
            <p className="hero-text">
              Prepare intent, evaluate policy, control execution, and review proof inside a dashboard rewritten to feel native to the CompliAGL brand system.
            </p>

            <div className="hero-metrics">
              {overviewStats.map((item) => (
                <article key={item.label} className="hero-metric-card">
                  <span className="hero-metric-label">{item.label}</span>
                  <strong className="hero-metric-value">{item.value}</strong>
                  <span className="hero-metric-detail">{item.detail}</span>
                </article>
              ))}
            </div>

            <div className="hero-note card-subtle">
              <strong className="hero-note-title">Current workspace state</strong>
              <p className="hero-note-text">{topMessage}</p>
            </div>
          </div>

          <aside className="hero-side">
            <div className="hero-side-head">
              <span className="card-kicker">Operator Guidance</span>
              <h2 className="card-title">Landing-page polish, operational depth</h2>
              <p className="card-subtitle">
                The workspace now uses the same premium visual language: framed surfaces, restrained motion, and concise executive storytelling.
              </p>
            </div>

            <div className="insight-grid">
              {insightItems.map((item) => (
                <InsightCard key={item.title} title={item.title} body={item.body} />
              ))}
            </div>

            <div className="hero-side-footer">
              <div className="hero-side-line">
                <span>Demo actor</span>
                <strong>{truncateMiddle(form.actor_id, 10, 6)}</strong>
              </div>
              <div className="hero-side-line">
                <span>Requested amount</span>
                <strong>{formatAmount(form.amount, form.currency)}</strong>
              </div>
            </div>
          </aside>
        </MotionSection>

        {error && <div className="banner error">{error}</div>}

        <div className="workspace-grid">
          <Section
            title="Configure the governed request"
            subtitle="Define the actor, action, amount, and payment context before the platform evaluates whether execution should proceed."
            kicker="Request Setup"
            className="composer"
          >
            <div className="form-grid form-surface">
              <label>
                Actor ID
                <input name="actor_id" value={form.actor_id} onChange={onChange} />
              </label>

              <label>
                Action
                <input name="action" value={form.action} onChange={onChange} />
              </label>

              <label>
                Amount
                <input
                  name="amount"
                  type="number"
                  value={form.amount}
                  onChange={onChange}
                />
              </label>

              <label>
                Currency
                <input name="currency" value={form.currency} onChange={onChange} />
              </label>

              <label>
                Payment Reference
                <input
                  name="payment_reference"
                  value={form.payment_reference}
                  onChange={onChange}
                  placeholder="Leave blank to simulate a payment-required step"
                />
              </label>
            </div>

            <div className="actions action-bar">
              <CutButton variant="outline" onClick={onVerify} disabled={loading}>
                {activeAction === "verify" ? "Reviewing..." : "Review Request"}
              </CutButton>

              <CutButton variant="solid" onClick={onExecute} disabled={loading || !verifyResult}>
                {activeAction === "execute" ? "Running..." : "Run Governed Action"}
              </CutButton>

              <CutButton variant="outline" onClick={onLoadLatestProof} disabled={loading || !executeResult}>
                {activeAction === "proof" ? "Opening..." : "Open Latest Proof"}
              </CutButton>

              <CutButton variant="outline" onClick={resetWorkspace} disabled={loading}>
                Reset Workspace
              </CutButton>
            </div>

            <div className="form-footnote premium-footnote">
              The default request uses the seeded demo actor and a payment
              reference so you can test the full flow quickly.
            </div>
          </Section>

          <Section
            title="Execution rail"
            subtitle="Track how the request progresses from governance review through settlement handling and proof creation."
            kicker="Workflow"
            className="journey-panel"
          >
            <div className="journey-summary card-subtle">
              <strong className="journey-summary-title">Live operator readout</strong>
              <p className="journey-summary-body">{topMessage}</p>
            </div>
            <div className="journey-list">
              {journey.map((item) => (
                <JourneyItem
                  key={item.title}
                  title={item.title}
                  description={item.description}
                  state={item.state}
                />
              ))}
            </div>
          </Section>
        </div>

        <div className="results-grid">
          <Section
            title="Decision brief"
            subtitle="The governance outcome is presented in business language with supporting rationale and request context."
            kicker="Decision"
            className="result-panel"
          >
            {decision ? (
              <>
                <div className="status-row">
                  <StatusPill status={decision.result} />
                </div>
                <div className="callout callout-info">{decisionSummary(decision)}</div>
                <SectionGroup title="Request details">
                  <div className="metadata-grid">
                    <Field label="Requested action" value={form.action} />
                    <Field label="Requested amount" value={formatAmount(form.amount, form.currency)} />
                  </div>
                </SectionGroup>
                <SectionGroup title="Governance audit">
                  <div className="metadata-grid metadata-grid-single">
                    <Field
                      label="Decision reasons"
                      value={(decision.reason_codes || []).join(", ") || "No reason codes provided"}
                    />
                  </div>
                </SectionGroup>
              </>
            ) : (
              <p className="result-empty">
                Start with <strong>Review Request</strong> to see whether this
                action passes governance.
              </p>
            )}
          </Section>

          <Section
            title="Settlement brief"
            subtitle="Execution readiness, payment posture, and runtime completion are summarized for fast operator review."
            kicker="Run Outcome"
            className="result-panel"
          >
            {executeResult ? (
              <>
                <div className="status-row">
                  <StatusPill status={executeResult.status} />
                  {execution?.status ? <StatusPill status={execution.status} /> : null}
                </div>
                <div
                  className={`callout ${
                    executeResult.status === "PAYMENT_REQUIRED"
                      ? "callout-warn"
                      : executeResult.status === "EXECUTED"
                        ? "callout-success"
                        : "callout-info"
                  }`.trim()}
                >
                  {paymentSummary(executeResult, payment, execution)}
                </div>
                <SectionGroup title="Settlement summary">
                  <div className="metadata-grid">
                    <Field label="Payment verified" value={payment?.payment_verified ? "Yes" : "No"} />
                    <Field label="Settlement network" value={formatNetwork(payment?.network || "")} />
                  </div>
                </SectionGroup>
                <SectionGroup title="Execution details">
                  <div className="metadata-grid">
                    <CopyableField
                      label="Payment reference"
                      value={payment?.payment_reference || "Not supplied"}
                      displayValue={payment?.payment_reference || "Not supplied"}
                    />
                    <CopyableField
                      label="Execution reference"
                      value={execution?.execution_reference}
                      displayValue={truncateMiddle(execution?.execution_reference || "")}
                    />
                    <Field label="Completed at" value={execution?.timestamp || "—"} />
                  </div>
                </SectionGroup>
              </>
            ) : (
              <p className="result-empty">
                Run the governed action to see the payment gate and execution
                outcome in a cleaner operator summary.
              </p>
            )}
          </Section>

          <Section
            title="Proof and audit summary"
            subtitle="Canonical evidence is surfaced as a clean audit view with identifiers, chains, and verification posture."
            kicker="Proof"
            className="result-panel result-proof"
          >
            {proof ? (
              <>
                <div className="status-row">
                  <StatusPill status={proof.decision || "APPROVED"} label="🛡 Proof Verified" />
                </div>
                <div className="callout callout-info">{proofSummary(proof, anchor)}</div>
                <SectionGroup title="Execution snapshot">
                  <div className="metadata-grid">
                    <Field label="Actor" value={actorName} />
                    <Field label="Intent" value={proof?.intent?.action || form.action} />
                    <Field label="Policy version" value={proof.policy_version} />
                    <Field label="Created at" value={proof.created_at} />
                  </div>
                </SectionGroup>
                <SectionGroup title="Audit identifiers">
                  <div className="metadata-grid">
                    <CopyableField
                      label="Proof ID"
                      value={proof.proof_id}
                      displayValue={truncateMiddle(proof.proof_id)}
                    />
                    <CopyableField
                      label="Proof hash"
                      value={proof.proof_hash}
                      displayValue={truncateMiddle(proof.proof_hash, 14, 10)}
                    />
                  </div>
                </SectionGroup>
                <SectionGroup title="Settlement and anchor">
                  <div className="metadata-grid">
                    <Field label="Settlement chain" value={formatNetwork(proof.settlement_chain || "")} />
                    <Field label="Anchor chain" value={formatNetwork(proof.anchor_chain || "")} />
                    <Field
                      label="Anchoring status"
                      value={anchor?.reason ? "Unavailable in this environment" : proof.anchor_tx_id ? "Anchored" : "Pending"}
                    />
                  </div>
                </SectionGroup>
              </>
            ) : (
              <p className="result-empty">
                Complete a run or open the latest saved proof to review the
                audit summary.
              </p>
            )}
          </Section>
        </div>
      </div>
    </main>
  );
}
