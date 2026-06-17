# Architecture

## Overview

CompliAGL is the **control plane for autonomous execution**. It governs what
autonomous actors are allowed to do *before* they act, executes approved actions
through configurable adapters, and produces verifiable proof for every outcome.

CompliAGL is **chain-agnostic and payment-rail agnostic**. It does not assume a
single blockchain, settlement layer, or payment protocol. The control plane —
identity, intent, policy, decision, proof, and anchoring — stays constant, while
execution rails, settlement layers, and anchoring layers are pluggable adapters.

The core principle:

> **Authorize first. Execute second. Prove permanently.**

Governance happens *before* execution so that a disallowed action can be stopped
before it ever takes effect. Proof happens *after* execution so that the actual
outcome is captured as a permanent, independently verifiable record.

---

## Architecture Flow

```
AI Agent / Autonomous Actor
        ↓
DID / VC Identity
        ↓
Intent Object
        ↓
CompliAGL Core
        ↓
Decision:
  APPROVE  → continue
  DENY     → stop
  ESCALATE → Human Actor
        ↓
If APPROVED:
  Execution Adapter
        ↓
  x402 / API / Chain / Payment Rail
        ↓
  Settlement Layer, e.g. Solana, XRPL, Base
        ↓
  Execution Result
        ↓
AIProof
        ↓
Execution / Governance State Snapshot
        ↓
Anchoring Layer, e.g. Algorand
        ↓
Proof Graph
        ↓
Compliance Proof Network
```

---

## Layers

### 1. Actor — AI Agent / Autonomous Actor

The **actor** is whatever initiates an action: an AI agent, an autonomous
service, a bot, a workflow, or any non-human (or human-supervised) system that
can attempt to move funds, call an API, or trigger an operational action.

The actor is the *origin* of every request. CompliAGL makes no assumption about
how the actor is built — it only requires that the actor present a verifiable
identity and a structured intent before anything is allowed to happen.

### 2. Identity — DID / VC

Before an intent is evaluated, the actor presents a **verifiable identity** using
Decentralized Identifiers (DIDs) and Verifiable Credentials (VCs).

- A **DID** uniquely and cryptographically identifies the actor without relying
  on a central registry.
- **VCs** attach attestations to that identity (e.g. "this agent is authorized to
  operate on behalf of org X", "this actor passed KYC", "this agent is bound to
  policy set Y").

Identity answers the question *"who is asking?"* so that policy can be applied to
the correct, trusted subject rather than an anonymous request.

### 3. Intent — Intent Object

The **Intent Object** is the structured, machine-readable description of what the
actor wants to do *before* it happens. It is a proposal, not an action.

An intent typically captures the operation type, target, amount/asset, recipient,
payment rail, and any context needed to evaluate it. Expressing the desired
action as an explicit intent — rather than letting the actor execute directly —
is what makes pre-execution governance possible.

### 4. Core Policy Engine — CompliAGL Core

**CompliAGL Core** is the policy and decision engine. It takes the verified
identity and the intent and evaluates them against the active policy set.

Policies express the enforceable boundaries of autonomous behavior — spend
limits, allowed assets, allowed recipients, time windows, rate limits, required
credentials, escalation thresholds, and so on. The Core is the single,
consistent control point through which every intent must pass; nothing reaches
execution without a decision from the Core.

### 5. Decision Output — APPROVE / DENY / ESCALATE

The Core returns exactly one of three verdicts:

- **APPROVE** → the intent satisfies all policy rules and execution may continue.
- **DENY** → the intent violates policy and is stopped. No execution occurs.
- **ESCALATE** → the intent is ambiguous, exceeds an automated threshold, or
  requires human judgment. It is routed to a **Human Actor** for review, who then
  approves or denies it.

This decision is the boundary between *authorization* and *action*. Only an
`APPROVE` (including a human-approved escalation) lets the flow proceed to
execution.

### 6. Execution Adapter

When an intent is approved, the **Execution Adapter** translates the abstract,
rail-neutral intent into a concrete operation on a specific target.

The adapter is the pluggable boundary that keeps the control plane chain-agnostic.
The same approved intent can be routed to different adapters:

- **x402 / API / Chain / Payment Rail** — the protocol or interface used to carry
  out the action (an HTTP `402` payment, a generic API call, a chain transaction,
  or another payment rail).

Adapters can be added or swapped without changing identity, intent, policy, or
proof logic.

### 7. Settlement Layer

The **Settlement Layer** is where the executed action actually settles —
for example **Solana, XRPL, or Base**. This is the network or system that finalizes
the value transfer or state change initiated by the adapter.

The settlement layer is *one possible choice per execution*, not a fixed
dependency. The adapter produces an **Execution Result** describing what actually
happened (transaction hash, status, settled amount, timestamps, etc.).

### 8. AIProof

**AIProof** wraps the execution result into a verifiable proof bundle. It binds
together the identity, the original intent, the policy decision, and the actual
execution result into a single tamper-evident record.

AIProof is what turns "the system did something" into "here is cryptographic
evidence of exactly what was authorized and what occurred." It is generated
*after* execution precisely because it must reflect the real outcome, not just
the intended one.

### 9. State Snapshot — Execution / Governance State Snapshot

The **State Snapshot** captures the relevant execution and governance state at the
moment of the action — the policy version applied, the decision, the execution
result, and surrounding context.

The snapshot makes the proof self-contained and reproducible: a verifier can later
reconstruct *why* a decision was made and *what state* the system was in, without
needing access to live internal databases.

### 10. Anchoring — Anchoring Layer

The **Anchoring Layer** commits proof and state hashes to an external,
tamper-evident ledger — for example **Algorand**. Anchoring records a compact
cryptographic fingerprint of the AIProof and state snapshot.

Because only hashes are anchored, the underlying data stays private while its
integrity becomes publicly and independently verifiable. Like settlement, the
anchoring layer is pluggable — Algorand is *one possible choice*, not a hard
requirement.

### 11. Proof Graph

The **Proof Graph** links every element of an action together: actor → identity →
intent → decision → execution → result → AIProof → snapshot → anchor.

Rather than isolated logs, the graph forms a connected, traceable chain of
custody for autonomous activity. Any node can be followed to its causes and
effects, making full end-to-end traceability possible.

### 12. Compliance Proof Network

The **Compliance Proof Network** is the verification layer where auditors,
regulators, counterparties, and other stakeholders can independently verify
proofs without trusting CompliAGL's internal systems.

It is the destination of the whole pipeline: autonomous activity that has been
governed before execution and proven after execution, exposed as verifiable
compliance evidence to any authorized verifier.

---

## Key Design Principles

### Why governance happens *before* execution

A log tells you what happened *after* the fact. It cannot stop a disallowed action
and it cannot prevent harm. CompliAGL enforces policy on the **intent**, before any
adapter touches a real system. If the Core returns `DENY`, the action never
executes; if it returns `ESCALATE`, a human decides before anything moves. This is
what makes autonomous execution *safe* rather than merely *observable*.

### Why proof happens *after* execution

Authorization decides what is *allowed*; it cannot know the *actual outcome*. Did
the transaction settle? At what value? On which network? Proof must therefore be
generated after execution, capturing the real **Execution Result** into the AIProof
and state snapshot, then anchoring its hash. This turns the real outcome into a
permanent, independently verifiable fact rather than an assumption.

### Why the system is chain-agnostic

CompliAGL is infrastructure, not a bet on a single ecosystem. The control plane —
identity, intent, policy, decision, proof, snapshot, graph — is constant. What
varies is *where* actions execute, settle, and anchor. By isolating those concerns
behind adapters, CompliAGL can govern actions across many ecosystems
simultaneously and add new ones without changing its core. No single blockchain,
settlement layer, or payment protocol is assumed.

### How x402 fits as one possible payment protocol

**x402** is *one* payment rail that an Execution Adapter can target. It carries out
approved payment intents (for example, agent-initiated micro-payments) using the
same identity, policy, decision, and proof pipeline as any other rail. It is a
plug-in at the execution boundary — important but interchangeable. APIs, direct
chain transactions, and other payment rails fit at exactly the same point.

### How Solana fits as one possible settlement layer

**Solana** is *one* settlement layer where an executed action can finalize. An
approved intent routed through the appropriate adapter can settle on Solana, but
the same intent could settle on **XRPL**, **Base**, or another network instead. Solana
is selected per execution; it is never a hard dependency of the control plane.

### How Algorand fits as one possible anchoring layer

**Algorand** is *one* anchoring layer used to commit proof and state hashes to an
external, tamper-evident ledger. It provides fast, low-cost, immutable anchoring,
but the anchoring boundary is pluggable: another ledger could serve the same role.
Because only hashes are anchored, the choice of anchoring layer does not expose the
underlying execution data.

---

## Summary

CompliAGL connects a single, consistent path from autonomous intent to verifiable
proof:

```
Actor → Identity → Intent → Core → Decision → (Execution → Settlement → Result)
      → AIProof → State Snapshot → Anchoring → Proof Graph → Compliance Proof Network
```

Governance is enforced before execution, proof is captured after execution, and
every rail, settlement layer, and anchoring layer is a pluggable adapter — making
CompliAGL a chain-agnostic control plane for autonomous execution.
