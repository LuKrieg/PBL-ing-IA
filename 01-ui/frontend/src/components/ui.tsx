import clsx from "clsx";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Button({
  variant = "primary", size = "md", loading, className, children, ...p
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger"; size?: "sm" | "md"; loading?: boolean; ref?: React.Ref<HTMLButtonElement> }) {
  return (
    <button
      {...p}
      disabled={p.disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-[background,border-color,transform,opacity] duration-150 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-accent text-accent-ink hover:brightness-110",
        variant === "outline" && "border border-line-strong text-ink hover:bg-raised",
        variant === "ghost" && "text-muted hover:text-ink hover:bg-raised",
        variant === "danger" && "bg-defect/15 text-defect border border-defect/40 hover:bg-defect/25",
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Card({ className, children, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...p} className={clsx("rounded-xl border border-line bg-surface", className)} style={{ boxShadow: "var(--shadow)", ...p.style }}>
      {children}
    </div>
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3 mb-3">
      <h2 className="font-display text-[13px] font-semibold uppercase tracking-[0.14em] text-muted">{children}</h2>
      {right}
    </div>
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return <label htmlFor={htmlFor} className="block text-xs font-medium text-muted mb-1.5">{children}</label>;
}

const fieldCls =
  "h-10 w-full rounded-md border border-line-strong bg-raised px-3 text-sm text-ink placeholder:text-muted/70 transition-colors hover:border-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30";

export function Input(p: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={clsx(fieldCls, p.className)} />;
}
export function Select({ children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={clsx(fieldCls, "pr-8 appearance-none bg-no-repeat bg-[right_0.6rem_center]", p.className)} style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238d99a5' stroke-width='2.5'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}>{children}</select>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-raised", className)} aria-hidden />;
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <Inbox className="size-8 text-muted" aria-hidden />
      <p className="font-medium">{title}</p>
      {hint && <p className="text-sm text-muted max-w-sm">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-12 text-center">
      <AlertTriangle className="size-8 text-defect" aria-hidden />
      <p className="text-sm text-muted max-w-md">{message}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Reintentar</Button>}
    </div>
  );
}
