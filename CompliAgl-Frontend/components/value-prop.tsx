import { CurtainImage } from "@/components/curtain-image";
import { Kicker } from "@/components/corner-plus";
import {
  DUOTONE_BASE,
  DUOTONE_CONTAINER,
  DuotoneOverlay,
} from "@/components/duotone";
import type { ReactNode } from "react";

const PROBLEMS: { title: string; body: string }[] = [
  {
    title: "Intent without governance creates risk",
    body: "Autonomous systems increasingly execute financial, operational, and digital actions independently. Without pre-execution governance, enterprises inherit operational, regulatory, and reputational risk they cannot reliably contain.",
  },
  {
    title: "Governance without execution creates friction",
    body: "CompliAGL evaluates intent against applicable policy sets using deterministic reasoning before execution begins, turning policy into an execution gate rather than a post-incident review process.",
  },
  {
    title: "Execution without proof creates uncertainty",
    body: "Every governed action generates AIProof capturing the complete lifecycle—actor, intent, context, policies, decision, and execution result. CompliLedger transforms AIProof into machine-verifiable proof for independent verification.",
  },
];

const CUT_CLIP =
  "polygon(28px 0, 100% 0, 100% calc(100% - 28px), calc(100% - 28px) 100%, 0 100%, 0 28px)";

export function ValueProp(): ReactNode {
  return (
    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 sm:pb-32 lg:px-10">
      <div className="grid items-center gap-10 lg:grid-cols-[1.35fr_1fr] lg:gap-12">
        <div
          className={`relative aspect-[4/3] w-full overflow-hidden sm:aspect-square lg:order-2 ${DUOTONE_CONTAINER}`}
          style={{ clipPath: CUT_CLIP }}
        >
          <CurtainImage
            src="/value-prop.jpg"
            alt="Fragmented security tooling"
            className={`absolute inset-0 h-full w-full ${DUOTONE_BASE}`}
          />
          <DuotoneOverlay />
        </div>

        <div className="lg:order-1">
          <Kicker>The Problem</Kicker>
          <h2 className="mt-5 max-w-2xl text-balance font-serif text-3xl font-normal leading-[1.12] tracking-[-0.01em] sm:text-4xl lg:text-[2.75rem]">
            Autonomous execution needs{" "}
            <span className="font-sans font-semibold tracking-tight">
              governance
            </span>{" "}
            before it needs{" "}
            <span className="font-sans font-semibold tracking-tight">
              logs
            </span>
          </h2>

          <dl className="mt-10">
            {PROBLEMS.map((item) => (
              <div
                key={item.title}
                className="border-t border-dotted border-border py-5"
              >
                <dt className="text-sm font-semibold tracking-tight">
                  {item.title}
                </dt>
                <dd className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
                  {item.body}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
