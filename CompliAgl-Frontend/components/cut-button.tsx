import type { ComponentPropsWithoutRef, CSSProperties, ReactNode } from "react";

const CUT =
  "[clip-path:polygon(var(--cut)_0,100%_0,100%_calc(100%-var(--cut)),calc(100%-var(--cut))_100%,0_100%,0_var(--cut))]";

type Variant = "solid" | "outline";

type BaseProps = {
  variant?: Variant;
  iconOnly?: boolean;
  fullWidth?: boolean;
  cut?: number;
  className?: string;
  children: ReactNode;
};

type ButtonProps = BaseProps &
  Omit<ComponentPropsWithoutRef<"button">, "className" | "children"> & {
    href?: undefined;
  };

type AnchorProps = BaseProps &
  Omit<ComponentPropsWithoutRef<"a">, "className" | "children"> & {
    href: string;
  };

type CutButtonProps = ButtonProps | AnchorProps;

const BASE =
  "inline-flex items-center justify-center gap-2 text-sm font-medium tracking-wide transition-colors duration-200 focus-ring";

export function CutButton({
  variant = "solid",
  iconOnly = false,
  fullWidth = false,
  cut = 9,
  className = "",
  children,
  ...props
}: CutButtonProps): ReactNode {
  const cutVar = { "--cut": `${cut}px` } as CSSProperties;
  const isAnchor = "href" in props && props.href !== undefined;

  if (variant === "solid") {
    const size = iconOnly ? "h-10 w-10" : `h-10 px-5 ${fullWidth ? "w-full" : ""}`;
    const cls = `${BASE} ${size} ${CUT} bg-foreground text-background hover:bg-foreground/85 ${className}`;

    if (isAnchor) {
      const { href, ...rest } = props as AnchorProps;
      return (
        <a href={href} style={cutVar} className={cls} {...rest}>
          {children}
        </a>
      );
    }
    return (
      <button style={cutVar} className={cls} {...(props as ButtonProps)}>
        {children}
      </button>
    );
  }

  const wrapperSize = iconOnly ? "h-10 w-10" : `h-10 ${fullWidth ? "w-full" : ""}`;
  const wrapper = `inline-flex ${wrapperSize} bg-border p-px ${CUT} ${className}`;
  const innerSize = iconOnly ? "w-full" : `px-5 ${fullWidth ? "w-full" : ""}`;
  const inner = `${BASE} h-full ${innerSize} ${CUT} bg-background text-foreground hover:bg-muted`;

  if (isAnchor) {
    const { href, ...rest } = props as AnchorProps;
    return (
      <span style={cutVar} className={wrapper}>
        <a href={href} style={cutVar} className={inner} {...rest}>
          {children}
        </a>
      </span>
    );
  }
  return (
    <span style={cutVar} className={wrapper}>
      <button style={cutVar} className={inner} {...(props as ButtonProps)}>
        {children}
      </button>
    </span>
  );
}
