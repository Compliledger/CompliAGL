import { AsciiIcon } from "@/components/ascii-icon";
import { CutButton } from "@/components/cut-button";
import { ArrowRight } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

type Shape = "scan" | "shield" | "key";

type Feature = {
  shape: Shape;
  title: string;
  body: string;
  meta: string;
  href: string;
};

const FEATURES: Feature[] = [
  {
    shape: "scan",
    title: "Actor Identity & Intent",
    body: "Identify autonomous actors (AI agents, humans, organizations, devices, workflows, services) and normalize requested actions into canonical intent objects for policy evaluation.",
    meta: "Identity · Intent · CompliAGL",
    href: "#capabilities",
  },
  {
    shape: "shield",
    title: "Policy & Decision Automation",
    body: "Evaluate intent against applicable policy sets using deterministic reasoning. Generate explainable decisions (Approved, Denied, Escalated) before execution begins.",
    meta: "Policy · Decision · CompliAGL",
    href: "#capabilities",
  },
  {
    shape: "key",
    title: "Execution & AIProof",
    body: "Execute authorized actions through configurable adapters (x402, REST APIs, payment networks, workflows) and generate machine-verifiable AIProof capturing the complete lifecycle.",
    meta: "Execution · AIProof · CompliAGL",
    href: "#capabilities",
  },
];

const CARD_CLIP =
  "polygon(0 0, calc(100% - 34px) 0, 100% 34px, 100% 100%, 0 100%)";

export function Features(): ReactNode {
  const clip = { clipPath: CARD_CLIP } as CSSProperties;

  return (
    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 sm:pb-32 lg:px-10">
      <div className="max-w-2xl">
        <h2 className="text-balance font-serif text-3xl font-normal leading-[1.12] tracking-[-0.01em] sm:text-4xl lg:text-[2.75rem]">
          Platform{" "}
          <span className="font-sans font-semibold tracking-tight">Capabilities</span>
        </h2>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          CompliAGL gives enterprises the governance stack required to move from experimental AI usage to trusted autonomous execution in production.
        </p>
      </div>

      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
        {FEATURES.map((feature) => (
          <div key={feature.title} className="bg-border p-px" style={clip}>
            <article
              className="flex h-full flex-col bg-background p-6 sm:p-7"
              style={clip}
            >
              <h3 className="text-lg font-semibold tracking-tight">
                {feature.title}
              </h3>

              <div className="my-5 border-t border-dotted border-border" />
              <div className="flex justify-center py-6 sm:py-8">
                <AsciiIcon shape={feature.shape} />
              </div>
              <div className="mb-6 border-t border-dotted border-border" />

              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.body}
              </p>

              <div className="mt-auto flex items-center justify-between gap-4 pt-8">
                <span className="text-xs font-medium text-muted-foreground">
                  {feature.meta}
                </span>
                <CutButton
                  href={feature.href}
                  variant="outline"
                  iconOnly
                  aria-label={`Learn more about ${feature.title}`}
                >
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </CutButton>
              </div>
            </article>
          </div>
        ))}
      </div>
    </section>
  );
}
