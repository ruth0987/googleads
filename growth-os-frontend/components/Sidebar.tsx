"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    BarChart3,
    LayoutDashboard,
    MessageSquare,
    Settings,
    Target,
    TrendingUp,
    ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Campaigns", href: "/dashboard", icon: Target },
    { name: "Ads Strategist", href: "/chat/ads", icon: TrendingUp },
    { name: "Analytics Explorer", href: "/chat/analytics", icon: BarChart3 },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex h-full w-64 flex-col border-r border-gray-200 bg-white shadow-sm">
            <div className="flex h-16 items-center px-6 border-b border-gray-200">
                <Link href="/" className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
                        <TrendingUp className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-xl font-bold tracking-tight text-slate-900">Growth-OS</span>
                </Link>
            </div>

            <nav className="flex-1 space-y-1 px-3 py-6">
                {navigation.map((item) => {
                    const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={cn(
                                "group flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                                isActive
                                    ? "bg-blue-50 text-blue-700 shadow-sm"
                                    : "text-slate-600 hover:bg-gray-50 hover:text-slate-900"
                            )}
                        >
                            <item.icon className={cn(
                                "mr-3 h-5 w-5 flex-shrink-0 transition-colors",
                                isActive ? "text-blue-700" : "text-slate-400 group-hover:text-slate-600"
                            )} />
                            {item.name}
                            {isActive && <ChevronRight className="ml-auto h-4 w-4" />}
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 border-t border-gray-200">
                <div className="rounded-xl bg-slate-900 p-4 text-white shadow-xl">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Current CID</p>
                    <p className="mt-1 font-mono text-sm">141-127-4245</p>
                    <div className="mt-3 flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs text-slate-300">System Live</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
