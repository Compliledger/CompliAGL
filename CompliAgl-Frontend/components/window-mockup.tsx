import {
  ArrowDownRight,
  ArrowUpRight,
  BadgeCheck,
  Bell,
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

const CUT =
  "[clip-path:polygon(5px_0,100%_0,100%_calc(100%-5px),calc(100%-5px)_100%,0_100%,0_5px)]";

type NavItem = { label: string; icon: LucideIcon; active?: boolean };

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", icon: Gauge, active: true },
  { label: "Intents", icon: Play },
  { label: "Executions", icon: Workflow },
  { label: "Proofs", icon: ShieldCheck },
  { label: "Actors", icon: BadgeCheck },
  { label: "Reports", icon: FileText },
];

type Kpi = {
  label: string;
  value: string;
  delta: string;
  dir: "up" | "down";
  icon: LucideIcon;
};

const KPIS: Kpi[] = [
  {
    label: "Intents Governed",
    value: "12,847",
    delta: "14.2%",
    dir: "up",
    icon: Play,
  },
  {
    label: "Executions Verified",
    value: "3,204",
    delta: "2.1%",
    dir: "up",
    icon: Workflow,
  },
  {
    label: "Proofs Generated",
    value: "98.6%",
    delta: "0.8%",
    dir: "up",
    icon: ShieldCheck,
  },
  {
    label: "Avg. Verification",
    value: "1.2s",
    delta: "0.3s",
    dir: "down",
    icon: Timer,
  },
];

type Alert = {
  sev: string;
  dot: string;
  title: string;
  meta: string;
  time: string;
  status: string;
};

const ALERTS: Alert[] = [
  {
    sev: "Critical",
    dot: "bg-foreground",
    title: "Intent verification failed",
    meta: "actor-001",
    time: "2m",
    status: "Rejected",
  },
  {
    sev: "High",
    dot: "bg-foreground/60",
    title: "Policy violation detected",
    meta: "workflow-04",
    time: "14m",
    status: "Blocked",
  },
  {
    sev: "Medium",
    dot: "bg-foreground/35",
    title: "Proof generation pending",
    meta: "execution-12",
    time: "1h",
    status: "Review",
  },
  {
    sev: "Low",
    dot: "bg-foreground/20",
    title: "Actor registration approved",
    meta: "actor-045",
    time: "3h",
    status: "Verified",
  },
];

function Sidebar(): ReactNode {
  return (
    <aside className="hidden w-[212px] shrink-0 flex-col border-r border-border/60 bg-muted/20 lg:flex">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-border/60 px-4">
        <span className={`h-6 w-6 bg-foreground ${CUT}`} aria-hidden="true" />
        <span className="text-[15px] font-semibold tracking-tight">
          CompliAGL
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 p-3">
        <p className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
          Workspace
        </p>
        {NAV_ITEMS.map((item) => (
          <span
            key={item.label}
            className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors ${
              item.active
                ? "bg-foreground/[0.06] font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <item.icon
              className="h-[15px] w-[15px]"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {item.label}
          </span>
        ))}
      </nav>

      {/* Footer status */}
      <div className="border-t border-border/60 p-3">
        <div className="flex items-center gap-2 rounded-md border border-border/60 bg-background px-2.5 py-2">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-muted-foreground/40" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-muted-foreground" />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-[11px] font-medium">Governance active</span>
            <span className="text-[10px] text-muted-foreground">
              Updated just now
            </span>
          </span>
        </div>
      </div>
    </aside>
  );
}

function Topbar(): ReactNode {
  return (
    <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4 sm:px-5">
      <div className="flex min-w-0 flex-col">
        <h2 className="truncate text-sm font-semibold tracking-tight">
          Governance Overview
        </h2>
        <p className="hidden text-[11px] text-muted-foreground sm:block">
          Last 24 hours · All Actors
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
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border/60 text-muted-foreground">
          <Bell className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
        </span>
        <span className="grid h-8 w-8 place-items-center rounded-full bg-foreground text-[11px] font-semibold text-background">
          AR
        </span>
      </div>
    </div>
  );
}

function KpiCard({ kpi }: { kpi: Kpi }): ReactNode {
  const positive = kpi.dir === "up";
  const Arrow = positive ? ArrowUpRight : ArrowDownRight;
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

function ThreatChart(): ReactNode {
  return (
    <div className="flex min-h-0 flex-col rounded-lg border border-border/60 bg-background p-4 lg:col-span-2">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[13px] font-semibold tracking-tight">
            Intent Activity
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Governed vs. executed intents
          </p>
        </div>
        <div className="hidden items-center gap-1 rounded-md border border-border/60 p-0.5 sm:flex">
          {["24h", "7d", "30d"].map((r, i) => (
            <span
              key={r}
              className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                i === 0
                  ? "bg-foreground/[0.06] text-foreground"
                  : "text-muted-foreground"
              }`}
            >
              {r}
            </span>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 flex items-center gap-4">
        <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-foreground" />
          Governed
        </span>
        <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
          Executed
        </span>
      </div>

      {/* Chart */}
      <div className="relative mt-3 min-h-0 flex-1 text-foreground">
        <svg
          viewBox="0 0 600 200"
          preserveAspectRatio="none"
          className="h-full w-full"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="threatFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.16" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* gridlines */}
          {[40, 80, 120, 160].map((y) => (
            <line
              key={y}
              x1="0"
              y1={y}
              x2="600"
              y2={y}
              stroke="currentColor"
              strokeOpacity="0.08"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {/* executed (muted, dashed) */}
          <path
            d="M0,165 C40,160 50,150 90,150 C140,150 150,128 190,126 C240,124 250,140 300,132 C350,124 360,104 410,100 C460,96 470,108 510,104 C550,101 570,92 600,90"
            fill="none"
            stroke="currentColor"
            strokeOpacity="0.28"
            strokeWidth="1.5"
            strokeDasharray="4 4"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* governed area */}
          <path
            d="M0,140 C30,130 30,128 60,120 C90,112 100,138 120,135 C150,131 155,98 180,95 C210,92 215,114 240,110 C270,106 280,72 300,70 C330,68 335,88 360,85 C390,82 400,57 420,55 C450,53 455,78 480,75 C510,72 520,42 540,40 C570,38 580,54 600,52 L600,200 L0,200 Z"
            fill="url(#threatFill)"
            stroke="none"
          />
          {/* governed line */}
          <path
            d="M0,140 C30,130 30,128 60,120 C90,112 100,138 120,135 C150,131 155,98 180,95 C210,92 215,114 240,110 C270,106 280,72 300,70 C330,68 335,88 360,85 C390,82 400,57 420,55 C450,53 455,78 480,75 C510,72 520,42 540,40 C570,38 580,54 600,52"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
    </div>
  );
}

function AlertsCard(): ReactNode {
  return (
    <div className="flex min-h-0 flex-col rounded-lg border border-border/60 bg-background p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-semibold tracking-tight">
          Recent Events
        </h3>
        <span className="flex items-center gap-0.5 text-[11px] font-medium text-muted-foreground">
          View all
          <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
        </span>
      </div>

      <ul className="mt-2 flex min-h-0 flex-1 flex-col divide-y divide-border/50 overflow-hidden">
        {ALERTS.map((a) => (
          <li
            key={a.title}
            className="flex items-center gap-2.5 py-2.5 first:pt-1"
          >
            <span
              className={`mt-1 h-1.5 w-1.5 shrink-0 self-start rounded-full ${a.dot}`}
              aria-hidden="true"
            />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-xs font-medium tracking-tight">
                {a.title}
              </span>
              <span className="truncate text-[11px] text-muted-foreground">
                {a.sev} · {a.meta} · {a.time}
              </span>
            </span>
            <span className="shrink-0 rounded border border-border/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              {a.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function WindowMockup(): ReactNode {
  return (
    <div className="mx-auto max-w-[1100px] overflow-hidden rounded-2xl border border-border/60 bg-background shadow-2xl shadow-black/[0.08]">
      {/* Title bar */}
      <div className="relative flex h-7 items-center border-b border-border/60 px-2.5">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <span className="pointer-events-none absolute inset-x-0 text-center text-xs font-normal text-muted-foreground">
          CompliAGL
        </span>
      </div>

      {/* App */}
      <div className="flex h-[560px]">
        <Sidebar />

        <section className="flex min-w-0 flex-1 flex-col">
          <Topbar />

          <main className="flex min-h-0 flex-1 flex-col gap-3 p-3 sm:p-4">
            {/* KPI row */}
            <div className="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
              {KPIS.map((kpi) => (
                <KpiCard key={kpi.label} kpi={kpi} />
              ))}
            </div>

            {/* Chart + alerts */}
            <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-3">
              <ThreatChart />
              <AlertsCard />
            </div>
          </main>
        </section>
      </div>
    </div>
  );
}
