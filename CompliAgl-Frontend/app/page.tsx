import { CoverageGrid } from "@/components/coverage-grid";
import { CaseStudy } from "@/components/case-study";
import { Hero } from "@/components/hero";
import { HeroWaves } from "@/components/hero-waves";
import { Faq } from "@/components/faq";
import { Features } from "@/components/features";
import { FinalCta } from "@/components/final-cta";
import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";
import { Pricing } from "@/components/pricing";
import { Stats } from "@/components/stats";
import { Testimonials } from "@/components/testimonials";
import { TrustedBy } from "@/components/trusted-by";
import { ValueProp } from "@/components/value-prop";
import { PortalWindowMockup } from "@/components/portal-window-mockup";
import { InView, MotionSection } from "@/lib/motion";
import { createMetadata, siteConfig } from "@/lib/metadata";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  ...createMetadata({
    title: "Home",
    description: `Welcome to ${siteConfig.name}. ${siteConfig.description}`,
    path: "/",
  }),
  title: { absolute: "CompliAGL \u2014 AI Execution Governance Platform" },
};

// Plain literals (built server-side) passed as props to the client motion
// wrappers — kept inline to avoid importing values from a "use client" module.
const SOFT_EASE = [0.22, 1, 0.36, 1] as const;
const RISE_IN = {
  hidden: { opacity: 0, y: 24, scale: 0.985 },
  visible: { opacity: 1, y: 0, scale: 1 },
};

export default function HomePage(): ReactNode {
  return (
    <>
      <span id="top" className="sr-only" />
      <Nav />
      <main id="main-content" className="flex-1">
        <div className="relative">
          <HeroWaves />
          <Hero />
          <div id="portal-demo">
            <MotionSection
              variants={RISE_IN}
              transition={{ duration: 0.85, delay: 0.55, ease: SOFT_EASE }}
              className="relative px-5 pb-24 sm:px-8 lg:px-10"
            >
              <PortalWindowMockup />
            </MotionSection>
          </div>
        </div>
        <InView>
          <TrustedBy />
        </InView>
        <CoverageGrid />
        <InView>
          <Features />
        </InView>
        <InView>
          <ValueProp />
        </InView>
        <InView>
          <Testimonials />
        </InView>
        <InView>
          <Stats />
        </InView>
        <InView>
          <CaseStudy />
        </InView>
        <InView>
          <Pricing />
        </InView>
        <InView>
          <Faq />
        </InView>
        <FinalCta />
      </main>
      <InView>
        <Footer />
      </InView>
    </>
  );
}
