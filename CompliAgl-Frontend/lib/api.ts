// Thin API client for the Compli402 backend.
//
// The backend base URL is configured via the NEXT_PUBLIC_API_BASE_URL environment
// variable (see .env.local). It falls back to localhost:8000 for
// local development.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function apiBaseUrl(): string {
  return API_BASE_URL;
}

export type RequestOptions = {
  method?: string;
  body?: string;
  headers?: Record<string, string>;
};

export type ApiResponse<T = unknown> = {
  ok: boolean;
  status: number;
  data: T | null;
};

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  let data: T | null = null;
  try {
    data = await res.json();
  } catch (_e) {
    data = null;
  }

  return { ok: res.ok, status: res.status, data };
}

type Intent = {
  actor_id: string;
  action: string;
  amount: number;
  currency: string;
  payment?: {
    reference: string;
  };
};

export type VerifyIntentResponse = {
  decision: {
    result: string;
    reason_codes?: string[];
  };
};

export type ExecuteIntentResponse = {
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
  proof?: {
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
};

export type LatestProofResponse = {
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

// GET /api/compli402/health
export function getHealth(): Promise<ApiResponse> {
  return request("/api/compli402/health");
}

// POST /api/compli402/verify/intent
export function verifyIntent(intent: Intent): Promise<ApiResponse<VerifyIntentResponse>> {
  return request("/api/compli402/verify/intent", {
    method: "POST",
    body: JSON.stringify(intent),
  });
}

// POST /api/compli402/execute
export function executeIntent(intent: Intent): Promise<ApiResponse<ExecuteIntentResponse>> {
  return request("/api/compli402/execute", {
    method: "POST",
    body: JSON.stringify(intent),
  });
}

// GET /api/compli402/proofs/latest
export function getLatestProof(): Promise<ApiResponse<LatestProofResponse>> {
  return request("/api/compli402/proofs/latest");
}
