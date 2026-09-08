"use client";

import { useState } from "react";
import { HeroWaves } from "@/components/hero-waves";
import { CutButton } from "@/components/cut-button";
import { executeIntent } from "@/lib/api";
import { MotionDiv, softEase } from "@/lib/motion";
import { Play, AlertTriangle, UserCheck } from "lucide-react";

const DEMO_ACTOR_ID = "00000000-0000-0000-0000-000000000001";

type Scenario = "normal" | "oracle" | "approval";

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

type ExecuteResult = {
  status: string;
  decision?: {
    result: string;
    reason_codes?: string[];
  };
  payment?: {
    payment_verified: boolean;
    network?: string;
    payment_reference?: string;
  };
  execution?: {
    status: string;
    execution_reference?: string;
    timestamp?: string;
  };
  anchor?: {
    reason?: string;
    anchor_tx_id?: string;
  };
  proof?: any;
};

const SCENARIOS = {
  normal: {
    title: "Normal Action",
    description: "Good actor with small amount",
    icon: Play,
    color: "green",
    intent: {
      actor_id: DEMO_ACTOR_ID,
      action: "TRANSFER",
      amount: 5,
      currency: "HBAR",
      payment_reference: "pay-normal-001",
    },
    expectedOutcome: "ALLOW → EXECUTED → coreActionCount=1",
  },
  oracle: {
    title: "Oracle Anomaly",
    description: "Valid actor, anomaly detected",
    icon: AlertTriangle,
    color: "red",
    intent: {
      actor_id: DEMO_ACTOR_ID,
      action: "TRANSFER",
      amount: 1000,
      currency: "HBAR",
      payment_reference: "pay-oracle-001",
    },
    expectedOutcome: "DENY → coreActionCount=0",
  },
  approval: {
    title: "Human Approval",
    description: "Requires manual approval",
    icon: UserCheck,
    color: "yellow",
    intent: {
      actor_id: DEMO_ACTOR_ID,
      action: "TRANSFER",
      amount: 500,
      currency: "HBAR",
      payment_reference: "pay-approval-001",
    },
    expectedOutcome: "REQUIRE_APPROVAL → coreActionCount=0",
  },
};

export default function DemoPage() {
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);
  const [executeResult, setExecuteResult] = useState<ExecuteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coreActionCount, setCoreActionCount] = useState(0);

  function clearState() {
    console.log('🧹 CLEARING ALL STATE');
    setExecuteResult(null);
    setError(null);
    setCoreActionCount(0);
  }

  function selectScenario(scenario: Scenario) {
    console.log(`📋 SELECTING SCENARIO: ${scenario}`);
    clearState();
    setSelectedScenario(scenario);
  }

  function buildIntent(scenario: Scenario): Intent {
    const scenarioConfig = SCENARIOS[scenario];
    const intent: Intent = {
      actor_id: scenarioConfig.intent.actor_id,
      action: scenarioConfig.intent.action,
      amount: scenarioConfig.intent.amount,
      currency: scenarioConfig.intent.currency,
    };
    
    if (scenarioConfig.intent.payment_reference) {
      intent.payment = { reference: scenarioConfig.intent.payment_reference };
    }

    console.log('🔨 BUILT INTENT:', intent);
    return intent;
  }

  async function runScenario() {
    if (!selectedScenario) return;

    console.log(`▶️ RUNNING SCENARIO: ${selectedScenario}`);
    setError(null);
    setLoading(true);

    const intent = buildIntent(selectedScenario);
    
    console.log('📤 SENDING REQUEST WITH PAYLOAD:', {
      scenario: selectedScenario,
      intent: intent,
      expectedOutcome: SCENARIOS[selectedScenario].expectedOutcome,
    });

    const { ok, data, status } = await executeIntent(intent);

    setLoading(false);

    if (!ok || !data) {
      const errorMsg = `Request failed with status ${status}`;
      console.error('❌ REQUEST FAILED:', errorMsg);
      setError(errorMsg);
      return;
    }

    console.log('✅ REQUEST SUCCEEDED:', data);
    setExecuteResult(data);

    if (data.decision?.result === "APPROVED" && data.status === "EXECUTED") {
      setCoreActionCount(1);
      console.log('✓ Core action executed: count = 1');
    } else {
      setCoreActionCount(0);
      console.log('✗ Core action NOT executed: count = 0');
    }
  }

  function resetDemo() {
    console.log('🔄 RESETTING DEMO');
    setSelectedScenario(null);
    clearState();
  }

  const scenario = selectedScenario ? SCENARIOS[selectedScenario] : null;

  return (
    <main id="main-content" className="min-h-screen bg-background relative overflow-hidden">
      <HeroWaves />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% -5%, color-mix(in srgb, var(--foreground) 5%, transparent), transparent 70%)",
        }}
      />

      <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8 sm:py-16 lg:px-10 lg:py-20">
        <MotionDiv
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: softEase }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl mb-4">
            CompliAGL Execution Governance
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            AI Agent Kit · Hedera Agent Kit · CompliAGL Adapter
          </p>
        </MotionDiv>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {(Object.keys(SCENARIOS) as Scenario[]).map((key) => {
            const s = SCENARIOS[key];
            const Icon = s.icon;
            const isSelected = selectedScenario === key;
            
            return (
              <button
                key={key}
                onClick={() => selectScenario(key)}
                className={`p-6 rounded-lg border-2 transition-all text-left ${
                  isSelected
                    ? `border-${s.color}-500 bg-${s.color}-500/10`
                    : "border-border hover:border-border/60"
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-lg bg-${s.color}-500/10`}>
                    <Icon className={`h-6 w-6 text-${s.color}-500`} />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold mb-1">{s.title}</h3>
                    <p className="text-sm text-muted-foreground mb-2">{s.description}</p>
                    <p className="text-xs font-mono text-muted-foreground">
                      {s.expectedOutcome}
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {scenario && (
          <MotionDiv
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-card border border-border rounded-lg p-8 mb-8"
          >
            <h2 className="text-2xl font-semibold mb-6">Scenario Configuration</h2>
            
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium mb-2">Actor ID</label>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {scenario.intent.actor_id}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Action</label>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {scenario.intent.action}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Amount</label>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {scenario.intent.amount} {scenario.intent.currency}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Payment Reference</label>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {scenario.intent.payment_reference || "—"}
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <CutButton variant="solid" onClick={runScenario} disabled={loading}>
                {loading ? "Running..." : "Run Governed Action"}
              </CutButton>
              <CutButton variant="outline" onClick={resetDemo} disabled={loading}>
                Reset Demo
              </CutButton>
            </div>
          </MotionDiv>
        )}

        {error && (
          <MotionDiv
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 mb-8"
          >
            {error}
          </MotionDiv>
        )}

        {executeResult && (
          <MotionDiv
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-card border border-border rounded-lg p-8"
          >
            <h2 className="text-2xl font-semibold mb-6">Governance Decision</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">Status</div>
                <div className={`text-lg font-semibold ${
                  executeResult.status === "EXECUTED" ? "text-green-500" :
                  executeResult.status === "DENIED" ? "text-red-500" :
                  "text-yellow-500"
                }`}>
                  {executeResult.status}
                </div>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">Decision</div>
                <div className={`text-lg font-semibold ${
                  executeResult.decision?.result === "APPROVED" ? "text-green-500" :
                  executeResult.decision?.result === "DENIED" ? "text-red-500" :
                  "text-yellow-500"
                }`}>
                  {executeResult.decision?.result || "—"}
                </div>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">Core Action Count</div>
                <div className="text-lg font-semibold">
                  {coreActionCount}
                </div>
              </div>
            </div>

            {executeResult.decision?.reason_codes && executeResult.decision.reason_codes.length > 0 && (
              <div className="mb-6">
                <div className="text-sm font-medium mb-2">Reason Codes</div>
                <div className="flex flex-wrap gap-2">
                  {executeResult.decision.reason_codes.map((code, idx) => (
                    <span key={idx} className="px-3 py-1 bg-muted rounded-full text-sm font-mono">
                      {code}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {executeResult.payment && (
              <div className="mb-6">
                <div className="text-sm font-medium mb-2">Payment Details</div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-muted rounded-md">
                    <div className="text-xs text-muted-foreground mb-1">Verified</div>
                    <div className="font-mono text-sm">
                      {executeResult.payment.payment_verified ? "Yes" : "No"}
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-md">
                    <div className="text-xs text-muted-foreground mb-1">Network</div>
                    <div className="font-mono text-sm">
                      {executeResult.payment.network || "—"}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {executeResult.execution && (
              <div>
                <div className="text-sm font-medium mb-2">Execution Details</div>
                <div className="p-3 bg-muted rounded-md">
                  <div className="text-xs text-muted-foreground mb-1">Execution Reference</div>
                  <div className="font-mono text-sm break-all">
                    {executeResult.execution.execution_reference || "—"}
                  </div>
                </div>
              </div>
            )}
          </MotionDiv>
        )}
      </div>
    </main>
  );
}
