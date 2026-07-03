"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Building2, Shield, Activity, Users, History } from "lucide-react";
import { User } from "@/lib/api";

interface AppHeaderProps {
  user: User;
}

export default function AppHeader({ user }: AppHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  const navLinkClass = (href: string, exact = false) => {
    const isActive = exact ? pathname === href : pathname.startsWith(href);
    return `px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
      isActive
        ? "text-blue-400 bg-blue-900/20"
        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
    }`;
  };

  return (
    <header className="glass border-b border-slate-800 sticky top-0 z-50">
      <div className="w-full px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-6 w-6 text-blue-400" />
          <h1 className="text-xl font-bold text-slate-100">DevOps AI Analyzer</h1>
        </div>

        <nav className="flex items-center gap-1">
          <Link href="/dashboard" className={navLinkClass("/dashboard", true)}>
            <Activity className="inline h-4 w-4 mr-2" />
            Analyze
          </Link>
          <Link href="/dashboard/history" className={navLinkClass("/dashboard/history")}>
            <History className="inline h-4 w-4 mr-2" />
            History
          </Link>
          {user.role === "admin" && (
            <Link href="/dashboard/users" className={navLinkClass("/dashboard/users")}>
              <Users className="inline h-4 w-4 mr-2" />
              Users
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Building2 className="h-4 w-4" />
            <span>{user.organization_name}</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-full">
            <Shield className={`h-4 w-4 ${user.role === "admin" ? "text-purple-400" : user.role === "sre" ? "text-blue-400" : "text-slate-400"}`} />
            <span className="text-sm capitalize text-slate-300">{user.role}</span>
          </div>

          <div className="text-sm text-slate-300">{user.full_name}</div>

          <button
            onClick={handleLogout}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
