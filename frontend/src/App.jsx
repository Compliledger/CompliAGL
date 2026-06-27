import React, { useState } from "react";
import { executeIntent, getLatestProof, verifyIntent } from "./api.js";

const DEMO_ACTOR_ID = "00000000-0000-0000-0000-000000000001";

const EMPTY_INTENT = {
  actor_id: DEMO_ACTOR_ID,
  action: "book_flight",
  amount: 100,
  currency: "USDC",
  payment_reference: "pay-demo-001",
};

function Section({ title, subtitle, kicker, className = "", children }) {
  return (
    <section className={`card card-cut ${className}`.trim()}>
      <div className="card-head">
        {kicker && <span className="card-kicker">{kicker}</span>}
        <h2 className="card-title">{title}</h2>
        {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
      </div>
      <div className="card-body">{children}</div>
    </section>
  );
}

function Field({ label, value }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <span className="field-value">{value ?? "—"}</span>
    </div>
  );
}

function CopyableField({ label, value, displayValue }) {
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

function SectionGroup({ title, children }) {
  return (
    <div className="detail-group">
      <div className="detail-group-title">{title}</div>
      {children}
    </div>
  );
}

function StatusPill({ status, label }) {
  if (!status) return null;
  const cls = `pill pill-${String(status).toLowerCase().replace(/_/g, "-")}`;
  return <span className={cls}>{label || statusLabel(status)}</span>;
}

function JourneyItem({ title, description, state }) {
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

function InsightCard({ title, body }) {
  return (
    <article className="insight-card">
      <strong className="insight-title">{title}</strong>
      <p className="insight-body">{body}</p>
    </article>
  );
}

function humanizeStatus(value) {
  return String(value || "")
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusLabel(status) {
  const value = String(status || "").toUpperCase();
  const statusMap = {
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

function truncateMiddle(value, start = 10, end = 6) {
  if (!value || value.length <= start + end + 1) return value || "—";
  return `${value.slice(0, start)}…${value.slice(-end)}`;
}

function formatNetwork(value) {
  if (!value) return "—";
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatAmount(amount, currency) {
  if (amount === undefined || amount === null || Number.isNaN(Number(amount))) {
    return "—";
  }
  return `${amount} ${currency}`;
}

function decisionSummary(decision) {
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

function paymentSummary(executeResult, payment, execution) {
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

function proofSummary(proof, anchor) {
  if (!proof) {
    return "When execution completes, the platform will present a clean proof summary here instead of raw payloads.";
  }
  if (anchor?.reason) {
    return "The AIProof was generated successfully. Anchoring is unavailable in this environment, so the proof is shown without an on-chain receipt.";
  }
  return "A proof bundle has been generated for this governed action and is ready for audit review.";
}

export default function App() {
  const [form, setForm] = useState(EMPTY_INTENT);
  const [verifyResult, setVerifyResult] = useState(null);
  const [executeResult, setExecuteResult] = useState(null);
  const [proof, setProof] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeAction, setActiveAction] = useState(null);

  function clearRunState() {
    setVerifyResult(null);
    setExecuteResult(null);
    setProof(null);
    setError(null);
  }

  function buildIntent() {
    const intent = {
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

  function onChange(e) {
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
    // /execute returns 402 when payment is required/failed — that's expected,
    // so we treat any JSON response as a usable result.
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
  const journey = [
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
  const insightItems = [
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

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <div className="app">
        <header className="hero-panel card card-cut">
          <div className="hero-copy">
            <span className="eyebrow">Governed Autonomous Execution</span>
            <h1 className="hero-title">
              Review the request, run the action, and capture the proof.
            </h1>
            <p className="hero-text">
              This workspace guides an operator through a professional flow:
              prepare the intent, confirm the governance decision, complete the
              action, and review the resulting audit evidence.
            </p>

            <div className="hero-note card-subtle">
              <strong className="hero-note-title">Current workspace state</strong>
              <p className="hero-note-text">{topMessage}</p>
            </div>
          </div>

          <aside className="hero-side">
            <div className="hero-side-head">
              <span className="card-kicker">Operator Guidance</span>
              <h2 className="card-title">What this flow does</h2>
            </div>

            <div className="insight-grid">
              {insightItems.map((item) => (
                <InsightCard key={item.title} title={item.title} body={item.body} />
              ))}
            </div>
          </aside>
        </header>

        {error && <div className="banner error">{error}</div>}

        <div className="workspace-grid">
          <Section
            title="1. Prepare the request"
            subtitle="Set the actor, action, amount, and optional payment reference for this governed run."
            kicker="Request Setup"
            className="composer"
          >
            <div className="form-grid">
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

            <div className="actions">
              <button className="secondary" onClick={onVerify} disabled={loading}>
                {activeAction === "verify" ? "Reviewing..." : "Review Request"}
              </button>

              <button className="primary" onClick={onExecute} disabled={loading || !verifyResult}>
                {activeAction === "execute" ? "Running..." : "Run Governed Action"}
              </button>

              <button className="secondary" onClick={onLoadLatestProof} disabled={loading || !executeResult}>
                {activeAction === "proof" ? "Opening..." : "Open Latest Proof"}
              </button>

              <button className="ghost" onClick={resetWorkspace} disabled={loading}>
                Reset Workspace
              </button>
            </div>

            <div className="form-footnote">
              The default request uses the seeded demo actor and a payment
              reference so you can test the full flow quickly.
            </div>
          </Section>

          <Section
            title="2. Guided journey"
            subtitle="Follow how the request progresses from review to proof generation."
            kicker="Workflow"
          >
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
            title="Policy review"
            subtitle="The governance decision appears here in business terms, not raw response data."
            kicker="Decision"
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
            title="Payment and execution"
            subtitle="Execution readiness and settlement handling are summarized here."
            kicker="Run Outcome"
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
                    <Field label="Settlement network" value={formatNetwork(payment?.network)} />
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
                      displayValue={truncateMiddle(execution?.execution_reference)}
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
            subtitle="Audit evidence is presented as a concise summary without exposing raw payloads."
            kicker="Proof"
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
                    <Field label="Settlement chain" value={formatNetwork(proof.settlement_chain)} />
                    <Field label="Anchor chain" value={formatNetwork(proof.anchor_chain)} />
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
    </div>
  );
}
