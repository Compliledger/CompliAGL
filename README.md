# CompliAGL — Agent Governance Layer

**AI agents can already transact on your behalf — but who's watching the agents?**

Today's autonomous agents negotiate deals, sign contracts, and move money. But they operate without guardrails. There are no spend limits, no approval workflows, no audit trails, and no way for an enterprise to prove that a transaction was compliant *before* it executed. CompliAGL is the governance layer that fixes this. It sits between agent intent and wallet execution, enforcing policies, generating compliance proofs, and ensuring every autonomous transaction is controlled, auditable, and trustworthy.

---

## 🔍 Why This Matters

Autonomous commerce is here — agents are buying cloud resources, executing trades, and managing supply chains in real time. But without governance:

- **Enterprises can't adopt agent wallets** — regulated industries require policy enforcement and auditability before they can trust an agent with real money.
- **Compliance must happen *before* execution, not after** — post-hoc audits don't prevent bad transactions; they just find them too late.
- **Autonomous commerce needs controls** — spending limits, multi-party approvals, and escalation workflows are not optional for real-world deployment.

CompliAGL makes agent-driven transactions enterprise-ready by embedding compliance directly into the transaction lifecycle.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Policy Enforcement** | Define and enforce spend limits, allowlists, blocklists, and custom rules — evaluated before every transaction. |
| **Decision Engine** | A rules engine that evaluates each transaction against the active policy set and returns an allow / deny / escalate decision in milliseconds. |
| **Escalation Workflows** | When a transaction exceeds policy thresholds, it's automatically routed to a human approver or a higher-authority agent — no silent failures. |
| **Proof Generation** | Every decision produces a cryptographic compliance proof that can be independently verified, anchored on-chain, or attached to the transaction. |
| **Audit Logging** | Immutable, structured logs capture the full decision context — who requested, what policy applied, what was decided, and why. |

---

## 🎬 Demo Scenarios

### ✅ Approved Transaction
> An agent requests a \$50 cloud compute purchase. The policy engine evaluates: amount is under the \$500 daily limit, vendor is on the allowlist, and the agent role has the required permission. **Result:** Transaction is approved instantly with a compliance proof attached.

### ❌ Denied Transaction
> An agent attempts a \$10,000 transfer to an unknown wallet. The policy engine flags: amount exceeds the per-transaction cap, recipient is not on the allowlist. **Result:** Transaction is denied, the agent receives a structured rejection reason, and the event is logged for audit.

### ⏫ Escalated Transaction
> An agent requests a \$2,500 software license purchase — within the global cap but above the agent's individual authority. The decision engine escalates the request to a human treasury approver. **Result:** The approver reviews and confirms; the transaction proceeds with dual-signature proof.

---

## 🚀 Future Vision

CompliAGL is designed to grow with the ecosystem:

- **OWS Integration** — Native support for the Open Wallet Standard, enabling plug-and-play governance for any OWS-compatible agent wallet.
- **x402 Payment Protocol** — Built-in compliance for HTTP 402-based micropayments, so agents can pay for APIs and services with policy enforcement baked in.
- **Blockchain Anchoring** — Anchor compliance proofs on-chain (Ethereum, Solana, or any EVM chain) for tamper-proof, publicly verifiable audit trails.
- **ZK Identity** — Zero-knowledge proof-based identity verification — agents can prove they are authorized without revealing sensitive organizational data.

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).

---

<p align="center">
  <strong>CompliAGL</strong> — Because autonomous agents need governance too.
</p>
