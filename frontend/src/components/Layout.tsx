import { useQuery } from "@tanstack/react-query";
import { Activity, Bell, BookOpen, Calculator, FileText, Gauge, History, LayoutDashboard, LogOut, Menu, Plug, ScrollText, Settings2, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { brand } from "@/lib/brand";
import { cn, titleCase } from "@/lib/utils";
import type { NotificationRecord, Page } from "@/lib/types";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

const applicantNav: NavItem[] = [
  { to: "/portal", label: "My applications", icon: <FileText className="h-4 w-4" />, end: true },
  { to: "/portal/notifications", label: "Notifications", icon: <Bell className="h-4 w-4" /> },
  { to: "/portal/calculator", label: "EMI calculator", icon: <Calculator className="h-4 w-4" /> },
];

const staffNav: NavItem[] = [
  { to: "/workspace", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" />, end: true },
  { to: "/workspace/applications", label: "Application register", icon: <BookOpen className="h-4 w-4" /> },
  { to: "/workspace/follow-up", label: "Follow-up monitoring", icon: <Activity className="h-4 w-4" /> },
  { to: "/workspace/policies", label: "Policy configuration", icon: <Settings2 className="h-4 w-4" /> },
  { to: "/workspace/integrations", label: "Integrations", icon: <Plug className="h-4 w-4" /> },
  { to: "/workspace/audit", label: "Audit history", icon: <ScrollText className="h-4 w-4" /> },
  { to: "/workspace/calculator", label: "Calculator", icon: <Gauge className="h-4 w-4" /> },
];

function Sidebar({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5">
        <Link to="/" onClick={onNavigate}>
          <Logo />
        </Link>
        <p className="mt-2 text-xs leading-snug text-muted">{brand.identity}</p>
      </div>
      <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium", isActive ? "bg-brand text-white" : "text-ink hover:bg-brand-soft")
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-line px-5 py-4">
        <p className="text-sm font-medium">{user?.full_name}</p>
        <p className="text-xs text-muted">{titleCase(user?.role)}</p>
        <p className="mt-3 text-[11px] leading-snug text-muted">{brand.tagline}</p>
      </div>
    </div>
  );
}

export function Layout() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const staff = user?.role !== "applicant";
  const items = staff ? staffNav : applicantNav;
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api<Page<NotificationRecord> & { unread_in_app: number }>("/notifications", { params: { channel: "IN_APP", unread: true, page_size: 1 } }),
    refetchInterval: 30000,
    enabled: !staff,
  });
  const unreadCount = unread.data?.unread_in_app ?? 0;

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <aside className="hidden border-r border-line bg-white lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar items={items} />
        </div>
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 bg-white">
            <button className="absolute right-3 top-4 rounded-md p-1 hover:bg-brand-soft" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <Sidebar items={items} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-canvas/95 px-4 backdrop-blur lg:px-8">
          <button className="rounded-md p-1.5 hover:bg-brand-soft lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-sm text-muted lg:block">{staff ? "Lender workspace" : "Applicant portal"}</div>
          <div className="flex items-center gap-2">
            {!staff && (
              <Link to="/portal/notifications" className="relative rounded-md p-2 hover:bg-brand-soft" aria-label={`Notifications, ${unreadCount} unread`}>
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-bold text-white">{unreadCount}</span>}
              </Link>
            )}
            <button className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium hover:bg-brand-soft" onClick={signOut}>
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-8 lg:py-8" key={location.pathname.split("/").slice(0, 3).join("/")}>
          <Outlet />
        </main>
        <footer className="border-t border-line px-4 py-4 text-xs text-muted lg:px-8">
          <span className="font-medium text-ink">{brand.name}</span> · {brand.tagline} · Illustrative lender policies. Not a lending offer.
        </footer>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions, back }: { title: string; description?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <div className="mb-6">
      {back}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="page-title">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export const historyIcon = <History className="h-4 w-4" />;
