"use client";

import { CutButton } from "@/components/cut-button";
import { Logo } from "@/components/logo";
import { NavVisual } from "@/components/nav-visual";
import { softEase, useReducedMotion } from "@/lib/motion";
import {
  ChevronDown,
  Layers,
  Menu,
  Server,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

type PlatformItem = {
  title: string;
  desc: string;
  href: string;
  icon: LucideIcon;
  featureTitle: string;
  featureDesc: string;
};

const PLATFORM_ITEMS: PlatformItem[] = [
  {
    title: "Architecture",
    desc: "Deterministic decision pipeline",
    href: "#architecture",
    icon: Server,
    featureTitle: "Canonical Decision Pipeline",
    featureDesc:
      "From intent to verification, CompliAGL transforms requirements into decisions, execution controls, and machine-verifiable proof.",
  },
  {
    title: "Capabilities",
    desc: "Platform capability layers",
    href: "#capabilities",
    icon: Layers,
    featureTitle: "Core, Identity, Execution, AIProof",
    featureDesc:
      "CompliAGL Core reasoning engine, governed actor identity, payment-gated execution, and canonical proof generation.",
  },
  {
    title: "Use Cases",
    desc: "High-value domain applications",
    href: "#use-cases",
    icon: TrendingUp,
    featureTitle: "AI Governance, Autonomous Agents, Commerce",
    featureDesc:
      "Applied across AI governance, agentic commerce, machine-to-vendor payments, financial crime, and enterprise automation.",
  },
];

const SIMPLE_LINKS = [
  { label: "Framework Operationalization", href: "#frameworks" },
  { label: "Documentation", href: "#docs" },
];

function useScrolled(threshold = 8): boolean {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = (): void => setScrolled(window.scrollY > threshold);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);
  return scrolled;
}

export function Nav(): ReactNode {
  const scrolled = useScrolled();
  const prefersReducedMotion = useReducedMotion();
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeItem, setActiveItem] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobilePlatformOpen, setMobilePlatformOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openMenu = (): void => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setMenuOpen(true);
  };
  const scheduleClose = (): void => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setMenuOpen(false), 120);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const active = PLATFORM_ITEMS[activeItem] ?? PLATFORM_ITEMS[0];
  if (!active) return null;

  return (
    <motion.header
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        prefersReducedMotion
          ? { duration: 0.01 }
          : { duration: 0.6, ease: softEase }
      }
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled || mobileOpen
          ? "border-border/50 bg-background border-b"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 sm:px-8 lg:px-10">
        {/* Left: logo + desktop links */}
        <div className="flex items-center gap-8">
          <Logo />

          <nav className="hidden items-center gap-1 lg:flex">
            {/* Expandable */}
            <div
              className="relative"
              onMouseEnter={openMenu}
              onMouseLeave={scheduleClose}
            >
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
                className={`focus-ring inline-flex items-center gap-1 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
                  menuOpen
                    ? "text-accent"
                    : "text-foreground/80 hover:text-foreground"
                }`}
              >
                Platform
                <ChevronDown
                  className={`h-4 w-4 transition-transform duration-300 ${
                    menuOpen ? "rotate-180" : ""
                  }`}
                  aria-hidden="true"
                />
              </button>

              <AnimatePresence>
                {menuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
                    className="absolute top-full left-3 pt-3"
                  >
                    <div className="border-border bg-background flex w-[600px] overflow-hidden rounded-md border shadow-2xl shadow-black/10">
                      <div className="flex w-[268px] flex-col gap-0.5 p-2">
                        {PLATFORM_ITEMS.map((item, i) => (
                          <a
                            key={item.href}
                            href={item.href}
                            onMouseEnter={() => setActiveItem(i)}
                            onFocus={() => setActiveItem(i)}
                            className="focus-ring group hover:bg-muted flex items-center gap-2.5 rounded p-2 transition-colors"
                          >
                            <span className="border-border bg-background text-muted-foreground group-hover:text-foreground flex h-7 w-7 shrink-0 items-center justify-center rounded-sm border transition-colors">
                              <item.icon
                                className="h-4 w-4"
                                strokeWidth={1.5}
                                aria-hidden="true"
                              />
                            </span>
                            <span className="flex flex-col">
                              <span className="text-[13px] font-medium tracking-tight">
                                {item.title}
                              </span>
                              <span className="text-muted-foreground text-xs">
                                {item.desc}
                              </span>
                            </span>
                          </a>
                        ))}
                      </div>

                      <div className="bg-border w-px self-stretch" />

                      <div className="flex flex-1 flex-col p-3">
                        <div className="relative min-h-0 w-full flex-1 overflow-hidden rounded">
                          <NavVisual />
                        </div>
                        <div className="mt-3 h-16">
                          <AnimatePresence mode="wait">
                            <motion.div
                              key={active.title}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -6 }}
                              transition={{ duration: 0.2 }}
                            >
                              <p className="text-[13px] font-semibold tracking-tight">
                                {active.featureTitle}
                              </p>
                              <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                                {active.featureDesc}
                              </p>
                            </motion.div>
                          </AnimatePresence>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {SIMPLE_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="focus-ring text-foreground/80 hover:text-foreground rounded-md px-3 py-2 text-[13px] font-medium transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          <CutButton variant="outline" href="#portal-demo">
            Try Dashboard
          </CutButton>
          <CutButton variant="solid" href="https://www.compliledger.com/contact">
            Request Demo
          </CutButton>
        </div>

        <div className="flex items-center gap-2.5 lg:hidden">
          <CutButton variant="solid" href="#portal-demo">
            Try Dashboard
          </CutButton>
          <CutButton
            variant="outline"
            iconOnly
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </CutButton>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
            className="border-border/50 overflow-hidden border-t lg:hidden"
          >
            <div className="mx-auto max-w-[1440px] px-5 py-4 sm:px-8">
              <button
                type="button"
                onClick={() => setMobilePlatformOpen((v) => !v)}
                aria-expanded={mobilePlatformOpen}
                className="focus-ring flex w-full items-center justify-between rounded-md px-2 py-3 text-sm font-medium"
              >
                Platform
                <ChevronDown
                  className={`h-4 w-4 transition-transform duration-300 ${
                    mobilePlatformOpen ? "rotate-180" : ""
                  }`}
                  aria-hidden="true"
                />
              </button>

              <AnimatePresence>
                {mobilePlatformOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.22 }}
                    className="overflow-hidden"
                  >
                    <div className="flex flex-col gap-1 pb-2 pl-2">
                      {PLATFORM_ITEMS.map((item) => (
                        <a
                          key={item.href}
                          href={item.href}
                          onClick={() => setMobileOpen(false)}
                          className="focus-ring hover:bg-muted flex items-center gap-3 rounded-md p-2.5"
                        >
                          <span className="border-border text-foreground flex h-8 w-8 shrink-0 items-center justify-center rounded-md border">
                            <item.icon className="h-4 w-4" aria-hidden="true" />
                          </span>
                          <span className="flex flex-col">
                            <span className="text-sm font-medium">
                              {item.title}
                            </span>
                            <span className="text-muted-foreground text-xs">
                              {item.desc}
                            </span>
                          </span>
                        </a>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {SIMPLE_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="focus-ring block rounded-md px-2 py-3 text-sm font-medium"
                >
                  {link.label}
                </a>
              ))}

              <div className="border-border/50 mt-3 border-t pt-4">
                <CutButton variant="outline" href="#portal-demo" fullWidth>
                  Try Dashboard
                </CutButton>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
