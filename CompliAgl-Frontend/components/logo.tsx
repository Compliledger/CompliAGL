import type { ReactNode } from "react";

const CUT =
  "[clip-path:polygon(6px_0,100%_0,100%_calc(100%-6px),calc(100%-6px)_100%,0_100%,0_6px)]";

export function Logo(): ReactNode {
  return (
    <a
      href="#top"
      className="focus-ring group inline-flex items-center gap-2.5"
      aria-label="CompliAGL home"
    >
      <span
        className={`h-7 w-7 bg-foreground transition-transform duration-300 group-hover:rotate-3 ${CUT}`}
        aria-hidden="true"
      />
      <span className="text-[17px] font-semibold tracking-tight">CompliAGL</span>
    </a>
  );
}
