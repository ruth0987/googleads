"use client";

import { useState } from "react";
import {
    CheckCircle2,
    Info,
    ChevronRight,
    ArrowRight,
    Loader2,
    Edit3,
    Sparkles,
    ShieldCheck
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionDiffCardProps {
    action: {
        resource_type: string;
        action_type: string;
        resource_name: string;
        old_value: any;
        new_suggested_value: any;
        rationale: string;
        prediction_30d?: string;
    };
    campaignId: string;
}

export default function ActionDiffCard({ action, campaignId }: ActionDiffCardProps) {
    const [value, setValue] = useState(action.new_suggested_value);
    const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
    const [isEditing, setIsEditing] = useState(false);

    const handleApply = async () => {
        setStatus("loading");
        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/actions/apply`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ...action,
                    new_suggested_value: value,
                    campaign_id: campaignId
                }),
            });
            const data = await res.json();
            if (data.status === "success") {
                setStatus("success");
            } else {
                setStatus("error");
            }
        } catch (e) {
            setStatus("error");
        }
    };

    const isApplied = status === "success";

    return (
        <div className={cn(
            "overflow-hidden rounded-[2.5rem] border transition-all duration-500",
            isApplied ? "border-emerald-200 bg-emerald-50/20" : "border-gray-200 bg-white hover:border-blue-500/30 hover:shadow-2xl hover:shadow-blue-500/10 group"
        )}>
            <div className="p-10">
                <div className="flex items-start justify-between mb-8">
                    <div className="space-y-1.5">
                        <div className="flex items-center gap-3">
                            <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-600 bg-blue-50 px-3 py-1 rounded-full border border-blue-100/50">
                                {action.resource_type.replace(/_/g, " ")}
                            </h4>
                            <div className="h-1 w-1 rounded-full bg-slate-200" />
                            <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                                {action.action_type.replace(/_/g, " ")}
                            </h4>
                        </div>
                        <p className="text-sm font-bold text-slate-900 font-mono tracking-tight truncate max-w-[350px]">
                            {action.resource_name.split('/').pop()}
                        </p>
                    </div>
                    {isApplied && (
                        <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-full font-black text-[10px] uppercase tracking-widest shadow-lg shadow-emerald-500/20 animate-in fade-in zoom-in duration-500">
                            <ShieldCheck className="h-4 w-4" />
                            Synchronized
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-[1fr,auto,1fr] items-center gap-10">
                    <div className="space-y-3">
                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                            Current State
                        </p>
                        <div className="rounded-3xl bg-slate-50/50 px-6 py-5 border border-slate-100/50 line-through text-slate-400 decoration-slate-300 decoration-2 transition-all group-hover:bg-slate-50">
                            <span className="font-mono text-lg font-black tracking-tight">
                                {typeof action.old_value === "number" && action.action_type.includes("BUDGET") ? "$" : ""}
                                {action.old_value || "0.00"}
                            </span>
                        </div>
                    </div>

                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-xl shadow-slate-900/10 group-hover:scale-110 group-hover:bg-blue-600 group-hover:rotate-90 transition-all duration-500">
                        <ArrowRight className="h-6 w-6" />
                    </div>

                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <p className="text-[10px] font-black uppercase tracking-widest text-blue-600 flex items-center gap-2">
                                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-pulse" />
                                Target State
                            </p>
                            <button
                                onClick={() => setIsEditing(!isEditing)}
                                className="text-slate-300 hover:text-blue-600 transition-colors p-1"
                            >
                                <Edit3 className="h-3.5 w-3.5" />
                            </button>
                        </div>
                        <div className={cn(
                            "rounded-3xl px-6 py-5 border transition-all duration-500",
                            isEditing ? "border-blue-500 bg-white ring-8 ring-blue-50" : "border-blue-100 bg-blue-50/30 group-hover:bg-blue-50/50"
                        )}>
                            {isEditing ? (
                                <input
                                    type={typeof action.new_suggested_value === "number" ? "number" : "text"}
                                    value={value}
                                    onChange={(e) => setValue(e.target.value)}
                                    onBlur={() => setIsEditing(false)}
                                    autoFocus
                                    className="w-full bg-transparent p-0 font-mono text-lg font-black text-blue-600 outline-none"
                                />
                            ) : (
                                <span className="font-mono text-lg font-black text-blue-600 tracking-tight">
                                    {typeof value === "number" && action.action_type.includes("BUDGET") ? "$" : ""}
                                    {value}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="group/pred p-6 rounded-3xl bg-white border border-slate-100 transition-all hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-500/5">
                        <div className="flex items-center gap-2.5 mb-3">
                            <div className="h-7 w-7 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
                                <Sparkles className="h-4 w-4" />
                            </div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-indigo-600">30D Forecast</p>
                        </div>
                        <p className="text-sm font-bold text-slate-800 leading-relaxed italic">
                            "{action.prediction_30d || "Analyzing potential strategic impact..."}"
                        </p>
                    </div>

                    <div className="p-6 rounded-3xl bg-slate-50 border border-slate-100/50">
                        <div className="flex items-center gap-2.5 mb-3">
                            <div className="h-7 w-7 rounded-lg bg-white flex items-center justify-center text-slate-400 shadow-sm">
                                <Info className="h-4 w-4" />
                            </div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Rationale</p>
                        </div>
                        <p className="text-sm font-medium text-slate-500 leading-relaxed">
                            {action.rationale}
                        </p>
                    </div>
                </div>

                <div className="mt-10">
                    <button
                        onClick={handleApply}
                        disabled={status === "loading" || isApplied}
                        className={cn(
                            "group/btn relative flex w-full items-center justify-center gap-4 rounded-3xl py-5 text-[12px] font-black uppercase tracking-[0.25em] transition-all duration-500 overflow-hidden",
                            isApplied
                                ? "bg-white border-2 border-emerald-500 text-emerald-600 cursor-default"
                                : "bg-slate-900 text-white hover:bg-blue-600 hover:scale-[1.02] active:scale-[0.98] hover:shadow-2xl hover:shadow-blue-600/20"
                        )}
                    >
                        {status === "loading" ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : isApplied ? (
                            <CheckCircle2 className="h-5 w-5" />
                        ) : (
                            <Zap className="h-5 w-5 fill-current" />
                        )}
                        <span className="relative z-10 transition-transform group-hover/btn:translate-x-1">
                            {isApplied ? "Deployment Authorized" : "Execute Optimization"}
                        </span>
                    </button>
                </div>
            </div>
        </div>
    );
}

function Zap({ className }: { className?: string }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="none" className={className}><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
    );
}
