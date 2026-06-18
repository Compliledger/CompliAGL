import React, { useEffect, useState } from "react";
import {
  apiBaseUrl,
  executeIntent,
  getHealth,
  getLatestProof,
  verifyIntent,
} from "./api.js";

const DEMO_ACTOR_ID = "00000000-0000-0000-0000-000000000001";

const EMPTY_INTENT = {
  actor_id: DEMO_ACTOR_ID,
  action: "book_flight",
  amount: 100,
  currency: "USDC",
  payment_reference: "pay-demo-001",
};

function Section({ title, children }) {
  return (
    <section className="card">
      <h2>{title}</h2>
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

function Json({ value }) {
  if (value === null || value === undefined) {
    return <p className="muted">No data yet.</p>;
  }
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

function StatusPill({ status }) {
  if (!status) return null;
  const cls = `pill pill-${String(status).toLowerCase().replace(/_/g, "-")}`;
  return <span className={cls}>{status}</span>;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [form, setForm] = useState(EMPTY_INTENT);
  const [verifyResult, setVerifyResult] = useState(null);
  const [executeResult, setExecuteResult] = useState(null);
  const [proof, setProof] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshHealth();
  }, []);

  async function refreshHealth() {
    const { ok, data } = await getHealth();
    setHealth(ok ? data : null);
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
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function onVerify() {
    setError(null);
    setLoading(true);
    const { ok, status, data } = await verifyIntent(buildIntent());
    setLoading(false);
    if (!ok) {
      setError(`Verify failed (HTTP ${status})`);
      return;
    }
    setVerifyResult(data);
  }

  async function onExecute() {
    setError(null);
    setLoading(true);
    // /execute returns 402 when payment is required/failed — that's expected,
    // so we treat any JSON response as a usable result.
    const { data } = await executeIntent(buildIntent());
    setLoading(false);
    if (!data) {
      setError("Execute failed: no response from backend.");
      return;
    }
    setExecuteResult(data);
    setProof(data.proof || null);
  }

  async function onLoadLatestProof() {
    setError(null);
    const { ok, status, data } = await getLatestProof();
    if (!ok) {
      setError(`No proof available (HTTP ${status})`);
      return;
    }
    setProof(data);
  }

  const decision = executeResult?.decision || verifyResult?.decision || null;
  const payment = executeResult?.payment || null;
  const execution = executeResult?.execution || null;
  const anchor = executeResult?.anchor || null;
  const actorIdentity = proof?.actor_identity || null;

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>CompliAGL · Compli402</h1>
          <p className="subtitle">
            Governed autonomous execution — Actor → Intent → Policy → x402
            Payment → Execution → AIProof → Algorand Anchor
          </p>
        </div>
        <div className="health">
          <StatusPill status={health ? "HEALTHY" : "OFFLINE"} />
          <span className="muted small">{apiBaseUrl()}</span>
          <button onClick={refreshHealth}>Refresh</button>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <Section title="Submit Intent">
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
            x402 Payment Reference
            <input
              name="payment_reference"
              value={form.payment_reference}
              onChange={onChange}
              placeholder="leave blank to trigger 402"
            />
          </label>
        </div>
        <div className="actions">
          <button onClick={onVerify} disabled={loading}>
            Verify Intent
          </button>
          <button className="primary" onClick={onExecute} disabled={loading}>
            Execute
          </button>
          <button onClick={onLoadLatestProof} disabled={loading}>
            Load Latest Proof
          </button>
        </div>
      </Section>

      <div className="grid">
        <Section title="Actor">
          {actorIdentity ? (
            <>
              <Field label="Actor ID" value={proof?.actor_id} />
              <Field label="Name" value={actorIdentity.name} />
              <Field label="Type" value={actorIdentity.actor_type} />
              <Field label="Wallet" value={actorIdentity.wallet_address} />
            </>
          ) : (
            <Field label="Actor ID" value={form.actor_id} />
          )}
        </Section>

        <Section title="Intent">
          <Field label="Action" value={form.action} />
          <Field label="Amount" value={`${form.amount} ${form.currency}`} />
          <Field label="Intent ID" value={proof?.intent_id} />
        </Section>

        <Section title="Policy Decision">
          {decision ? (
            <>
              <StatusPill status={decision.result} />
              <Field
                label="Reason Codes"
                value={(decision.reason_codes || []).join(", ")}
              />
              <Field
                label="Matched Policies"
                value={(decision.matched_policies || []).join(", ")}
              />
            </>
          ) : (
            <p className="muted">Verify or execute an intent to see the decision.</p>
          )}
        </Section>

        <Section title="x402 Payment Status">
          {executeResult ? (
            <>
              <StatusPill status={executeResult.status} />
              <Field
                label="Payment Required"
                value={String(payment?.payment_required ?? "—")}
              />
              <Field
                label="Payment Verified"
                value={String(payment?.payment_verified ?? "—")}
              />
              <Field label="Reference" value={payment?.payment_reference} />
              <Field label="Facilitator" value={payment?.facilitator} />
              <Field label="Network" value={payment?.network} />
            </>
          ) : (
            <p className="muted">Execute an intent to see x402 payment status.</p>
          )}
        </Section>

        <Section title="Execution Result">
          {execution ? (
            <>
              <Field label="Adapter" value={execution.adapter} />
              <StatusPill status={execution.status} />
              <Field
                label="Execution Reference"
                value={execution.execution_reference}
              />
              <Field label="Timestamp" value={execution.timestamp} />
            </>
          ) : (
            <p className="muted">No execution yet.</p>
          )}
        </Section>

        <Section title="Algorand Anchor Receipt">
          {anchor ? (
            <>
              <Field label="Chain" value={anchor.chain} />
              <Field label="Network" value={anchor.network} />
              <Field label="Anchor Tx ID" value={anchor.txid} />
              <Field label="Proof Hash" value={anchor.proof_hash} />
              <Field label="Anchored At" value={anchor.anchored_at} />
              <Field label="Adapter" value={anchor.adapter} />
              {anchor.explorer_url && (
                <Field
                  label="Explorer"
                  value={
                    <a href={anchor.explorer_url} target="_blank" rel="noreferrer">
                      {anchor.explorer_url}
                    </a>
                  }
                />
              )}
              {anchor.reason && <Field label="Note" value={anchor.reason} />}
            </>
          ) : (
            <p className="muted">No anchor receipt yet.</p>
          )}
        </Section>
      </div>

      <Section title="AIProof Bundle">
        {proof ? (
          <>
            <div className="proof-summary">
              <Field label="Proof ID" value={proof.proof_id} />
              <Field label="Proof Type" value={proof.proof_type} />
              <Field label="Proof Hash" value={proof.proof_hash} />
              <Field label="Decision" value={proof.decision} />
              <Field label="Payment Protocol" value={proof.payment_protocol} />
              <Field label="Settlement Chain" value={proof.settlement_chain} />
              <Field label="Anchor Chain" value={proof.anchor_chain} />
              <Field label="Anchor Tx ID" value={proof.anchor_tx_id} />
              <Field label="Verification URL" value={proof.verification_url} />
              <Field label="Created At" value={proof.created_at} />
            </div>
            <Json value={proof} />
          </>
        ) : (
          <p className="muted">
            Execute an intent (or load the latest proof) to view the AIProof
            bundle.
          </p>
        )}
      </Section>
    </div>
  );
}
