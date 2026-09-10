# Astra tool-calling layer (AIRA / SENTRY) — Design & Implementation

**Status:** Implemented, tests green (50 new). The OpenAI Responses API
**transport** is stubbed pending the API key — everything else is live.

Astra (`gpt-6-astra`, plain Responses API, no hosted-tools config) powers two
agent personas, **AIRA** (AML investigations assistant) and **SENTRY**
(sanctions-screening agent). Astra *reasons*; **the application executes tool
calls**, and only ever read/propose ones.

---

## 1. Where it lives

```
backend/app/services/canonical/governed_action_service.py   NEW — intent→decision pipeline as one call
backend/app/astra/
  __init__.py            package overview + the security boundary
  errors.py              AstraNotConfiguredError / ForbiddenToolError / ToolValidationError
  personas.py            AIRA / SENTRY: default actor id, system prompt, tool allow-list
  context.py             AstraInvocationContext + build_context()
  sentry_screening.py    run_screening() — thin wrapper over the real SENTRY connector
  tools/
    __init__.py          re-exports
    schemas.py           the 4 OpenAI function-calling JSON schemas + tools_for_persona()
    handlers.py          the 4 Python handlers (read / propose only)
    dispatch.py          execute_tool_call() — forbidden-deny → default-deny → schema → run
  responses/
    __init__.py
    client.py            AstraResponsesClient (transport stub) + pure parse/shape helpers
    loop.py              run_agent_turn() — the agentic loop
backend/tests/test_governed_action_service.py
backend/tests/astra/test_tool_schemas.py
backend/tests/astra/test_tool_dispatch_allowlist.py
backend/tests/astra/test_request_sanctions_screening.py
backend/tests/astra/test_propose_governed_action_tool.py
backend/tests/astra/test_read_tools.py
backend/tests/astra/test_responses_client.py
backend/tests/astra/test_responses_loop.py
```

Config (`app/core/config.py`): `OPENAI_API_KEY` (None), `ASTRA_MODEL`
(`"gpt-6-astra"`), `ASTRA_ENABLED` (False — the loop is fail-closed), 
`ASTRA_MAX_TOOL_ITERATIONS` (8). `requirements.txt`: `openai==1.63.0`, imported
lazily in `responses/client.py`.

**No new HTTP routes** — this is the prep layer. A `POST /api/v1/astra/turn`
route is a later, separate decision.

---

## 2. The four tools

Handlers take `ctx: AstraInvocationContext` first (injected by `dispatch`,
**never** model-supplied), then keyword args matching the schema exactly. Each
returns a JSON-serializable dict fed back as the `function_call_output`.

### `get_case_data(case_id, sections)` — read

Sections `case` / `kyc` / `counterparties` / `recent_decisions`. Composed from
canonical records scoped to `ctx.case_id` (see §5 for the Q1 verification):

| section | source |
|---|---|
| `case` | `Target` rows whose `external_identifier == case_id`, + intent/resolution counts |
| `kyc` | normalized (validated) evidence claims for the case's latest `PolicyResolution`, keyed by evidence-requirement id — this is where the sanctions-screening result lives |
| `counterparties` | distinct `counterparty` ids seen in the case's intents, each annotated with its latest screening result if one is in normalized evidence |
| `recent_decisions` | every `Decision` for the case's intents, `demo3`-style projection, most-recent-first |

A `case_id` that isn't `ctx.case_id` → `ToolValidationError` (no cross-case pivot).

### `get_authorized_transaction_history(case_id, limit, direction)` — read

Canonical `Intent` history (Q2): `TRANSFER` / `PAYMENT` intents for the case
whose **current** `Decision` is `APPROVED`, annotated with any issued
`ExecutionAuthorization` ids. `limit` clamped 1–200. `direction` filters on an
`intent.parameters["direction"]` value when present.

### `request_sanctions_screening(subject_id, subject_type, reason)` — delegate to SENTRY

`app/astra/sentry_screening.py::run_screening`:

1. build a `CollectRequest` (`EV_SCREENING` / `SCREENING_EVIDENCE_TYPE` /
   `SCREENING_ISSUER` from `app/db/harborstone_package.py`, `intent_id =
   ctx.correlation_id`),
2. `harborstone_sentry_screening_connector().collect(request)` — **the real
   connector** (Q6). Simulated *lookup*, real integrity-hashed evidence
   contract; `claims.simulation == True`.
3. persist a `RawEvidence` row: synthetic `collection_job_id =
   "astra-delegated-screening:<correlation_id>"`, provenance carries
   `collected_via: "astra_tool_delegation"` + a `delegation` block
   (`requesting_agent_id: agent:harborstone:aira`, `screening_agent_id:
   agent:harborstone:sentry`, `reason`), `payload_hash = hash_dict({"claims":
   …})` — shape matches `evidence_orchestration_service._persist_raw_evidence`
   for the fields validation/normalization read.
4. return `{screening_id, result, match_count, risk_level,
   requires_human_review, screened_at, subject, screening_source, simulation,
   simulation_note, integrity_hash, raw_evidence_id, delegated_by, screened_by,
   case_id}`.

Direct connector call — **not** a nested model call. The authoritative
screening that feeds a decision is still collected inside
`governed_action_service.propose`'s pipeline (the connector is in
`default_production_registry()`); this tool is AIRA's pre-flight look + a
durable delegation record.

### `propose_governed_action(...)` — AIRA's terminal action

Args: `action_type` (`transfer` / `data_access` / `workflow_action`),
`compliidentity_resource`, `compliidentity_action` (`propose` / `read` only —
`approve` is **not** offerable), `resource_instance` (the case),
`target_identifier` (the screened subject / counterparty — becomes
`Target.external_identifier`), `rationale`, `amount_minor`, `amount_currency`,
`parameters` (bounded closed object: `direction` / `note`).

→ `governed_action_service.propose(...)` with `actor_id = ctx.actor_id`. Returns
`{proposed, terminal: true, intent_id, policy_resolution_id, assessment_result,
decision: {…}, outcome, next_step}` where `next_step` is:

- `APPROVED` → `authorization_issuable` (the **application**, not the model,
  calls `authorization_service.issue` — Q5: never auto-issued)
- `DENIED` → `blocked`
- `ESCALATED` → `human_approval_required` (a human approver goes through
  `POST /api/v1/escalation-approvals` then `/apply`; the tool never submits or
  applies an approval)

`loop.py` treats a successful `propose_governed_action` as **terminal** — the
turn ends, no further model round.

---

## 3. `governed_action_service.propose()`

The intent→decision pipeline `demo3_step2/compliagl_scenarios.py::run_pipeline`
stitches by hand, extracted as one reusable call:

```
intent_service.create            (parameters carry compliidentity_resource/_action/_resource_instance)
target_service.create            (external_identifier = target_identifier or resource_instance)
operational_context_service.create
policy_resolution_service.resolve
applicability_service.evaluate_for_resolution
evidence_collection_service.start_collection   (registry defaults to default_production_registry())
decision_service.decide_for_resolution         (re-runs sufficiency/controls/assessment itself)
assessment_service.latest_for_resolution       (read back the assessment the decision consumed)
```

Never auto-approves, never auto-authorizes. Side-effect-symmetric with the demo
driver so the two cannot drift. Reused by the Astra tool **and** available for a
future REST route.

---

## 4. Forbidden-tool enforcement (defense in depth)

`transfer_funds` / `freeze_account` / `restrict_account` / `execute_contract`:

1. **No schema, no handler** exists for any of them anywhere in the package.
2. `FORBIDDEN_TOOL_NAMES` denylist in `tools/dispatch.py`; module-load
   `assert`s that it's disjoint from both the handler registry and the schema
   registry, and that handler/schema registries agree.
3. Personas carry an **explicit** `allowed_tools` tuple. `execute_tool_call` is
   **default-deny** against it.
4. `execute_tool_call` order: forbidden-deny → persona default-deny → no-handler
   → jsonschema validation → run. Every failure is fail-closed and typed,
   before any handler side effect.
5. `responses/client.py` only ever serializes `tools_for_persona(persona)` into
   the wire `tools` array.
6. `loop.py` converts `ForbiddenToolError` / `ToolValidationError` into a
   structured tool-error result the model sees next turn — the loop continues,
   the tool never runs.

**SENTRY is read-only** — `allowed_tools = (get_case_data,
get_authorized_transaction_history)`. Not a cost choice: `propose_governed_action`
on SENTRY would let a bounded, delegated screening task widen into a
consequential action, breaking the AAI-001 bounded-delegation guarantee.
`test_tool_schemas.py::test_aira_gets_all_four_sentry_is_read_only` and
`test_responses_loop.py::test_sentry_cannot_propose_via_the_loop` pin this.

---

## 5. Q1 verification — canonical read pattern

**Verified, with a caveat.** There is **no** `Case` / `KYC` / `Counterparty`
model in the repo. The only canonical records readable for a case are:

- `Target` (by `external_identifier`),
- `Intent` + `Decision` history (bound to the case via
  `intent.parameters["compliidentity_resource_instance"]` — the same key
  `decision_service._authority_request_params` reads),
- `NormalizedEvidence` claims for the case's latest `PolicyResolution`.

`demo3_step2` itself never reads case data back — it only writes and projects
decisions (`_decision_view`). `get_case_data` follows that projection style and
composes the three record types above. Reads currently `list()` + filter in
Python (demo-scale; `limit=1000`). **If HarborStone expects a real KYC record
store, `get_case_data`'s `kyc` section is a follow-up** — today it returns the
validated screening/evidence claims, which is the closest existing signal.

---

## 6. Responses API layer

`AstraResponsesClient.create(instructions, input, tools)` — lazy `import
openai`; raises `AstraNotConfiguredError` when `OPENAI_API_KEY` is unset. Pure
and tested against recorded payloads: `parse_output` (→ `function_calls` +
`text`), `function_call_input_item`, `function_call_output_item`,
`user_message_item`.

`run_agent_turn(ctx, user_message, client=None, max_iterations=None)` — refuses
unless `ASTRA_ENABLED`; loops model → tool calls → dispatch → feed back → stop
on final text / terminal propose / iteration cap. Returns `AgentTurnResult
{stopped, final_text, decision, invocations, iterations}`.

### Strict mode

Every schema — top level **and every nested object** — is closed
(`additionalProperties: false`) with all properties `required` (nullable via a
union type where the argument is optional), so all four are OpenAI strict-mode
compatible. `propose_governed_action.parameters` was resolved from an
open-ended object to a **bounded closed object** with two known optional keys
(`direction`, `note`); the handler flattens them into `intent.parameters` and
also derives `counterparty` from `target_identifier`.
`test_tool_schemas.py::_assert_strict_object` walks every schema recursively and
pins this.

### Known adjustments for when the key lands

- `enum` arrays include `null` (e.g. `direction`) alongside
  `type: ["string","null"]` — confirm the Responses API accepts
  `["inbound","outbound",null]`; if not, drop the `null` enum member (the union
  type already permits null).
- Add one live smoke test (`ASTRA_ENABLED=1`, real key) once available.

---

## 7. Test coverage

| file | what it pins |
|---|---|
| `test_governed_action_service.py` | pipeline → APPROVED / ESCALATED / DENIED; probe params on the intent; nothing downstream auto-happens |
| `astra/test_tool_schemas.py` | exactly 4 tools; forbidden names absent everywhere; AIRA=4 / SENTRY=2 read-only; every schema (nested objects too) strict-shaped & valid |
| `astra/test_tool_dispatch_allowlist.py` | forbidden-deny for both personas; unknown-tool deny; SENTRY can't propose/screen; handler not reached when denied; bad args → validation not forbidden |
| `astra/test_request_sanctions_screening.py` | real connector results; RawEvidence persisted with delegation provenance; integrity hash round-trips; empty subject rejected |
| `astra/test_propose_governed_action_tool.py` | APPROVED terminal without executing; DENIED; out-of-scope case refused; `approve` verb refused; amount w/o currency refused; bounded `parameters` + derived `counterparty` land on the intent; unknown `parameters` keys rejected |
| `astra/test_read_tools.py` | composed `get_case_data` sections; section filter; cross-case refusal; history = authorized+approved only; direction filter; SENTRY can read |
| `astra/test_responses_client.py` | parse tool call / final message / bad-JSON args; item helpers; no-key → not-configured; model defaults to `gpt-6-astra` |
| `astra/test_responses_loop.py` | disabled-loop refusal; read→final; terminal propose (2nd response unconsumed); forbidden call refused mid-loop; SENTRY can't propose; iteration cap |

Full backend suite: **489 passed** (439 prior + 50 new). No regressions.
