"use client";

import { CutButton } from "@/components/cut-button";
import { CornerPlus } from "@/components/corner-plus";
import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

type QA = { question: string; answer: string };

const FAQS: QA[] = [
  {
    question: "What is CompliAGL?",
    answer:
      "CompliAGL is the AI Execution Governance Platform that governs autonomous AI execution through policy automation, deterministic decision-making, and machine-verifiable proof. Powered by CompliLedger Proof Infrastructure.",
  },
  {
    question: "What are the core functions of CompliAGL?",
    answer:
      "CompliAGL performs 11 core functions: Actor Identity, Intent Resolution, Context Resolution, Policy Resolution, Applicable Policy Set, Decision Automation, Decision, Execution Authorization, Execution, Execution Result, and AIProof Generation.",
  },
  {
    question: "What actor types does CompliAGL support?",
    answer:
      "CompliAGL governs AI agents, humans, organizations, devices, workflows, and services across machine and enterprise environments.",
  },
  {
    question: "What execution adapters does CompliAGL support?",
    answer:
      "CompliAGL is chain-agnostic and execution-adapter agnostic, supporting x402, REST APIs, payment networks, workflow engines, blockchain adapters, and custom enterprise integrations.",
  },
  {
    question: "What is AIProof?",
    answer:
      "AIProof is a canonical artifact representing the complete governance and execution lifecycle, capturing actor, intent, context, applicable policies, decision, execution authorization, execution result, and metadata.",
  },
  {
    question: "What is the relationship between CompliAGL and CompliLedger?",
    answer:
      "CompliAGL governs autonomous execution and generates AIProof. CompliLedger transforms AIProof into machine-verifiable proof. CompliAGL responsibilities end with AIProof generation.",
  },
  {
    question: "What are CompliAGL's platform characteristics?",
    answer:
      "CompliAGL is AI-native, deterministic, policy-driven, explainable, chain-agnostic, execution-adapter agnostic, extensible, and automation-first.",
  },
];

const EASE = [0.22, 1, 0.36, 1] as const;

function FaqItem({
  item,
  isOpen,
  onToggle,
  index,
}: {
  item: QA;
  isOpen: boolean;
  onToggle: () => void;
  index: number;
}): ReactNode {
  const panelId = `faq-panel-${index}`;
  const buttonId = `faq-button-${index}`;

  return (
    <div className="border-dotted border-border [&:not(:first-child)]:border-t">
      <h3>
        <button
          id={buttonId}
          type="button"
          aria-expanded={isOpen}
          aria-controls={panelId}
          onClick={onToggle}
          className="focus-ring flex w-full items-center justify-between gap-6 py-5 pr-1 text-left lg:py-6 lg:pl-12"
        >
          <span className="text-base font-medium tracking-tight sm:text-lg">
            {item.question}
          </span>
          <motion.span
            animate={{ rotate: isOpen ? 180 : 0 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="shrink-0 text-muted-foreground"
          >
            <ChevronDown className="h-5 w-5" aria-hidden="true" />
          </motion.span>
        </button>
      </h3>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={panelId}
            role="region"
            aria-labelledby={buttonId}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.4, ease: EASE }}
            className="overflow-hidden"
          >
            <p className="max-w-xl pb-6 pr-6 text-sm leading-relaxed text-muted-foreground lg:pl-12">
              {item.answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Faq(): ReactNode {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const accordionRef = useRef<HTMLDivElement | null>(null);
  const [minHeight, setMinHeight] = useState<number | undefined>(undefined);

  useEffect(() => {
    const node = accordionRef.current;
    if (node === null) return;

    let peak = 0;
    let width = node.offsetWidth;

    const observer = new ResizeObserver(() => {
      if (node.offsetWidth !== width) {
        width = node.offsetWidth;
        peak = 0;
        setMinHeight(undefined);
        return;
      }
      const next = node.offsetHeight;
      if (next > peak) {
        peak = next;
        setMinHeight(next);
      }
    });

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 sm:pb-32 lg:px-10">
      <div className="relative grid border-y border-border lg:grid-cols-[0.85fr_1.15fr]">
        {/* Outer frame corners */}
        <CornerPlus className="left-0 top-0 -translate-x-1/2 -translate-y-1/2" />
        <CornerPlus className="right-0 top-0 translate-x-1/2 -translate-y-1/2" />
        <CornerPlus className="bottom-0 left-0 -translate-x-1/2 translate-y-1/2" />
        <CornerPlus className="bottom-0 right-0 translate-x-1/2 translate-y-1/2" />

        {/* Left: heading */}
        <div className="border-b border-border py-10 lg:border-b-0 lg:border-r lg:py-16 lg:pr-12">
          <h2 className="text-balance font-serif text-4xl font-normal leading-[1.05] tracking-[-0.01em] sm:text-5xl lg:text-[3.5rem]">
            Frequently asked questions
          </h2>
          <p className="mt-6 max-w-sm text-sm leading-relaxed text-muted-foreground sm:text-base">
            Common questions from enterprise teams evaluating execution governance, operational control, and proof for AI systems in production.
          </p>
          <div className="mt-8">
            <CutButton href="#contact" variant="outline">
              Talk to CompliAGL
            </CutButton>
          </div>
        </div>

        {/* Right: accordion */}
        <div
          ref={accordionRef}
          className="relative"
          style={minHeight !== undefined ? { minHeight } : undefined}
        >
          {/* Plus marks where the divider meets the frame */}
          <CornerPlus className="left-0 top-0 hidden -translate-x-1/2 -translate-y-1/2 lg:block" />
          <CornerPlus className="bottom-0 left-0 hidden -translate-x-1/2 translate-y-1/2 lg:block" />
          {FAQS.map((item, i) => (
            <FaqItem
              key={item.question}
              item={item}
              index={i}
              isOpen={openIndex === i}
              onToggle={() => setOpenIndex((cur) => (cur === i ? null : i))}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
