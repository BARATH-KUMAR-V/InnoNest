import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

const variants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-brand-dark",
        outline: "border border-line bg-white text-ink hover:bg-brand-tint",
        ghost: "text-ink hover:bg-brand-soft",
        danger: "bg-bad text-white hover:bg-[#8C2F22]",
        subtle: "bg-brand-soft text-brand hover:bg-[#D8E6DC]",
      },
      size: { sm: "h-8 px-3", md: "h-10 px-4", lg: "h-11 px-6", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof variants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp ref={ref} className={cn(variants({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {asChild ? children : (
        <>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {children}
        </>
      )}
    </Comp>
  );
});
Button.displayName = "Button";
