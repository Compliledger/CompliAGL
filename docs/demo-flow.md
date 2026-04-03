# Demo Flow

This document describes the three core governance flows demonstrated by CompliAGL and provides example scenarios with expected outcomes for each.

---

## Overview

Every agent wallet transaction passes through the CompliAGL governance layer before execution. The layer evaluates the transaction against active policies and returns one of three verdicts:

| Verdict | Symbol | Meaning |
|---|---|---|
| Approved | ✅ | Transaction is within policy — execution proceeds |
| Denied | ❌ | Transaction violates policy — execution is blocked |
| Escalated | ⏸ | Transaction requires human review before proceeding |

---

## Flow 1 — Approved

### What happens

The agent proposes a transaction. The decision engine evaluates all active policy rules. Every rule passes. The proof engine generates a signed approval record. The wallet executes the transaction.

### Sequence

```
Agent ──► [Propose TX] ──► CompliAGL
                               │
                     Policy Engine loads rules
                               │
                     Decision Engine evaluates
                               │
                         All rules pass
                               │
                     Proof Engine signs record
                     (verdict: APPROVED)
                               │
                     Wallet executes transaction
                               │
                     Audit log updated ✅
```

### Example Scenario

**Agent:** `agent-007` (an autonomous payment agent)  
**Proposed action:** Send 50 USDC to `0xrecipient_address`  
**Time:** Tuesday, 14:30 UTC  

**Active policy:**
```json
{
  "max_spend_per_tx": 100.00,
  "allowed_assets": ["USDC", "ETH"],
  "allowed_recipients": ["0xrecipient_address"],
  "allowed_hours_utc": [9, 17]
}
```

**Evaluation:**
| Rule | Value | Limit | Result |
|---|---|---|---|
| Amount | 50 USDC | 100 USDC max | ✅ Pass |
| Asset type | USDC | USDC, ETH | ✅ Pass |
| Recipient | 0xrecipient_address | In allow-list | ✅ Pass |
| Time | 14:30 UTC | 09:00–17:00 UTC | ✅ Pass |

**Outcome:** Transaction executes. Proof record created with `verdict: APPROVED`.

**Proof record (excerpt):**
```json
{
  "decision_id": "d-20240315-001",
  "verdict": "APPROVED",
  "agent_id": "agent-007",
  "amount": 50.00,
  "asset": "USDC",
  "timestamp": "2024-03-15T14:30:00Z",
  "rules_evaluated": 4,
  "rules_passed": 4
}
```

---

## Flow 2 — Denied

### What happens

The agent proposes a transaction that violates one or more policy rules. The decision engine identifies the failing rules. The proof engine generates a signed denial record. The wallet is blocked from executing.

### Sequence

```
Agent ──► [Propose TX] ──► CompliAGL
                               │
                     Policy Engine loads rules
                               │
                     Decision Engine evaluates
                               │
                       One or more rules FAIL
                               │
                     Proof Engine signs record
                     (verdict: DENIED)
                               │
                     Wallet execution BLOCKED
                               │
                     Audit log updated ❌
                     Agent notified of denial
```

### Example Scenario A — Spend Limit Exceeded

**Agent:** `agent-007`  
**Proposed action:** Send 250 USDC to `0xrecipient_address`  

**Evaluation:**
| Rule | Value | Limit | Result |
|---|---|---|---|
| Amount | 250 USDC | 100 USDC max | ❌ **Fail** |
| Asset type | USDC | USDC, ETH | ✅ Pass |
| Recipient | 0xrecipient_address | In allow-list | ✅ Pass |
| Time | 11:00 UTC | 09:00–17:00 UTC | ✅ Pass |

**Outcome:** Transaction blocked. Proof record created with `verdict: DENIED`, `reason: spend_limit_exceeded`.

---

### Example Scenario B — Unauthorized Recipient

**Agent:** `agent-007`  
**Proposed action:** Send 20 USDC to `0xunknown_address`  

**Evaluation:**
| Rule | Value | Limit | Result |
|---|---|---|---|
| Amount | 20 USDC | 100 USDC max | ✅ Pass |
| Asset type | USDC | USDC, ETH | ✅ Pass |
| Recipient | 0xunknown_address | Not in allow-list | ❌ **Fail** |
| Time | 10:00 UTC | 09:00–17:00 UTC | ✅ Pass |

**Outcome:** Transaction blocked. Proof record created with `verdict: DENIED`, `reason: unauthorized_recipient`.

---

### Example Scenario C — Out of Hours

**Agent:** `agent-007`  
**Proposed action:** Send 30 USDC to `0xrecipient_address` at 23:00 UTC  

**Evaluation:**
| Rule | Value | Limit | Result |
|---|---|---|---|
| Amount | 30 USDC | 100 USDC max | ✅ Pass |
| Asset type | USDC | USDC, ETH | ✅ Pass |
| Recipient | 0xrecipient_address | In allow-list | ✅ Pass |
| Time | 23:00 UTC | 09:00–17:00 UTC | ❌ **Fail** |

**Outcome:** Transaction blocked. Proof record created with `verdict: DENIED`, `reason: outside_allowed_hours`.

---

## Flow 3 — Escalated

### What happens

The agent proposes a transaction that falls into a gray area — for example, an amount just above the automatic approval threshold, or a first-time recipient not yet on the allow-list. The decision engine cannot automatically approve or deny, so it escalates to a human reviewer. The wallet is paused until a human decision is recorded.

### Sequence

```
Agent ──► [Propose TX] ──► CompliAGL
                               │
                     Policy Engine loads rules
                               │
                     Decision Engine evaluates
                               │
                    Gray area detected — ESCALATE
                               │
                     Proof Engine creates pending record
                     (verdict: ESCALATED)
                               │
                     Human reviewer NOTIFIED
                     Wallet execution PAUSED ⏸
                               │
                   Human reviews in dashboard
                               │
                    ┌──────────┴──────────┐
                 APPROVE               DENY
                    │                    │
            Proof updated          Proof updated
            (APPROVED)             (DENIED)
                    │                    │
            Wallet executes        Wallet blocked
                    │                    │
            Audit log ✅          Audit log ❌
```

### Example Scenario A — New Recipient (Not Yet Allow-Listed)

**Agent:** `agent-007`  
**Proposed action:** Send 40 USDC to `0xnew_vendor` (first transaction to this address)  

**Policy escalation rule:** `escalate_on_new_recipient: true`

**Evaluation:**
| Rule | Value | Result |
|---|---|---|
| Amount | 40 USDC within limit | ✅ Pass |
| Asset type | USDC allowed | ✅ Pass |
| Recipient | 0xnew_vendor — not in allow-list | ⏸ Escalate |
| Time | 11:00 UTC — within hours | ✅ Pass |

**Outcome:** Transaction paused. Human reviewer sees a dashboard notification: _"Agent-007 wants to pay a new recipient 40 USDC. Approve to add to allow-list, or deny."_

---

### Example Scenario B — Near Threshold Amount

**Agent:** `agent-007`  
**Proposed action:** Send 95 USDC (policy limit: 100 USDC; escalation threshold: 80 USDC)  

**Policy escalation rule:** `escalate_above: 80.00`

**Evaluation:**
| Rule | Value | Result |
|---|---|---|
| Amount | 95 USDC — above escalation threshold | ⏸ Escalate |
| Asset type | USDC allowed | ✅ Pass |
| Recipient | In allow-list | ✅ Pass |
| Time | Within hours | ✅ Pass |

**Outcome:** Transaction paused. Human reviewer must confirm before the 95 USDC transfer proceeds.

---

### Example Scenario C — High-Risk Asset

**Agent:** `agent-007`  
**Proposed action:** Send 10 WBTC (policy requires escalation for all non-stablecoin assets)  

**Policy escalation rule:** `escalate_non_stablecoin: true`

**Evaluation:**
| Rule | Value | Result |
|---|---|---|
| Amount | Within limit | ✅ Pass |
| Asset type | WBTC — non-stablecoin | ⏸ Escalate |
| Recipient | In allow-list | ✅ Pass |
| Time | Within hours | ✅ Pass |

**Outcome:** Transaction paused pending human review of the high-risk asset transfer.

---

## Proof Record States

| State | Description |
|---|---|
| `APPROVED` | Fully automated approval — all rules passed |
| `DENIED` | Fully automated denial — one or more rules failed |
| `ESCALATED` | Pending human review |
| `HUMAN_APPROVED` | Escalated and approved by a human reviewer |
| `HUMAN_DENIED` | Escalated and denied by a human reviewer |

All proof records are immutable once finalised and are stored in the audit log with a cryptographic signature.
