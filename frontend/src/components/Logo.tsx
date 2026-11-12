import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-9 w-9", className)} role="img" aria-label="InnoNest">
      <rect width="64" height="64" rx="15" fill="#244A36" />
      <path d="M14 31 32 16l18 15" fill="none" stroke="#F7F7F3" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19 37c0 8 6 13 13 13s13-5 13-13" fill="none" stroke="#9FCBAE" strokeWidth="5" strokeLinecap="round" />
      <circle cx="32" cy="37" r="3.4" fill="#F7F7F3" />
    </svg>
  );
}

export function Logo({ className, light }: { className?: string; light?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className={cn("font-display text-xl font-extrabold tracking-tight", light ? "text-white" : "text-ink")}>
        Inno<span className={light ? "text-[#9FCBAE]" : "text-brand"}>Nest</span>
      </span>
    </div>
  );
}
