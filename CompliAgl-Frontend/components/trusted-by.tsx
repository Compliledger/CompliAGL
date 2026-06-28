import { UsersRound } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

type Brand = { slug: string; name: string; width: number; height: number };

const BRANDS: Brand[] = [
  { slug: "compliedger_wordmark", name: "CompliLedger", width: 90, height: 22 },
  { slug: "nist_wordmark", name: "NIST AI RMF", width: 95, height: 22 },
  { slug: "iso_wordmark", name: "ISO/IEC 42001", width: 100, height: 22 },
];

function CornerPlus({ className }: { className: string }): ReactNode {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={`pointer-events-none absolute h-3.5 w-3.5 text-blue-500 ${className}`}
    >
      <path
        d="M12 4v16M4 12h16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BrandLogo({ brand }: { brand: Brand }): ReactNode {
  const mask = `url(/logos/${brand.slug}.svg) center / contain no-repeat`;
  return (
    <span
      role="img"
      aria-label={brand.name}
      style={
        {
          width: brand.width,
          height: brand.height,
          mask,
          WebkitMask: mask,
        } as CSSProperties
      }
      className="block bg-foreground opacity-60 transition-opacity duration-200 hover:opacity-100"
    />
  );
}

export function TrustedBy(): ReactNode {
  return (
    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 lg:px-10">
      <div className="relative border border-border">
        <CornerPlus className="left-0 top-0 -translate-x-1/2 -translate-y-1/2" />
        <CornerPlus className="right-0 top-0 translate-x-1/2 -translate-y-1/2" />
        <CornerPlus className="bottom-0 left-0 -translate-x-1/2 translate-y-1/2" />
        <CornerPlus className="bottom-0 right-0 translate-x-1/2 translate-y-1/2" />

        <div className="flex flex-col items-stretch md:flex-row">
          {/* Label */}
          <div className="flex shrink-0 items-center justify-center border-b border-border px-6 py-5 md:border-b-0 md:border-r md:py-7">
            <span className="text-xs font-medium text-muted-foreground">
              Frameworks & Standards
            </span>
          </div>

          <div className="flex flex-1 flex-wrap items-center justify-evenly gap-x-8 gap-y-6 px-8 py-7">
            {BRANDS.map((brand) => (
              <BrandLogo key={brand.slug} brand={brand} />
            ))}
          </div>

          <div className="flex shrink-0 items-center justify-center gap-2 border-t border-border px-6 py-5 text-muted-foreground md:border-l md:border-t-0 md:py-7">
            <UsersRound className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            <span className="text-xs font-medium">Governance framework operationalization</span>
          </div>
        </div>
      </div>
    </section>
  );
}
