"use client";

import Link from "next/link";
import { ArrowRight, TrendingUp, Zap, Target, BarChart3, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts";

interface CampaignCardProps {
    campaign: {
        id: string;
        name: string;
        type: string;
        status: string;
        optimization_mode?: string;
        expected_impact?: {
            primary_metric_target: string;
            primary_metric_value: number;
            secondary_metric_target: string;
            secondary_metric_value: number;
            secondary_metric_unit?: string;
        };
        metrics: {
            spend: number;
            roas: number;
            conversions: number;
            trend_status?: string;
            trend?: Array<{ date: string; spend: number; conversions: number }>;
        };
        actions_preview?: string;
        pending_actions_count: number;
    };
}

export default function CampaignCard({ campaign }: CampaignCardProps) {
    const modeColors: Record<string, string> = {
        BALANCED_OPTIMIZATION: "bg-gradient-to-r from-blue-400 to-blue-200 text-white border-blue-300",
        WASTE_REDUCTION: "bg-gradient-to-r from-amber-400 to-amber-200 text-white border-amber-300",
        SCALE_FOCUSED: "bg-gradient-to-r from-emerald-400 to-emerald-200 text-white border-emerald-300",
        DATA_COLLECTION: "bg-gradient-to-r from-purple-400 to-purple-200 text-white border-purple-300",
        AGGRESSIVE_SCALING: "bg-gradient-to-r from-rose-500 to-rose-300 text-white border-rose-400",
        ACTIVE: "bg-gray-200 text-gray-700 border-gray-300",
    };

    const sparklineData = campaign.metrics.trend?.map((d) => ({ date: d.date, spend: d.spend })) || [];

    return (
        <Link
            href={`/campaign/${campaign.id}`}
            className="group block rounded-[2.5rem] border border-slate-200/60 bg-white p-2 shadow-sm transition-all duration-500 hover:shadow-2xl hover:border-blue-500/30 hover:-translate-y-1 relative overflow-hidden"
        >
            <div className="flex flex-col lg:flex-row lg:items-center gap-2 relative z-10">
                {/* Visual Accent */}
                <div className={cn(
                    "w-full lg:w-2 rounded-[2rem] h-2 lg:h-24 self-stretch transition-all duration-500 group-hover:w-3",
                    modeColors[campaign.optimization_mode || "ACTIVE"].split(' ')[0]
                )} />

                <div className="flex-1 min-w-0 p-6 flex flex-col lg:flex-row lg:items-center gap-8">
                    {/* Left: Info & Mode */}
                    <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center gap-3">
                            <h3 className="text-xl font-black text-slate-900 truncate tracking-tight">{campaign.name}</h3>
                            <span className={cn(
                                "px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border shadow-sm",
                                modeColors[campaign.optimization_mode || "ACTIVE"]
                            )}>
                                {campaign.optimization_mode?.replace("_", " ") || "ACTIVE"}
                            </span>
                        </div>

                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-1.5 opacity-60 group-hover:opacity-100 transition-all">
                                <Target className="h-3.5 w-3.5 text-blue-500" />
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-tight">{campaign.type}</span>
                            </div>
                            <div className="h-1 w-1 rounded-full bg-slate-200" />
                            <span className="text-sm font-bold text-slate-400 truncate">{campaign.actions_preview}</span>
                        </div>
                    </div>

                    {/* Middle: Sparkline */}
                    <div className="w-full lg:w-48 h-16 flex flex-col justify-center">
                        <div className="flex items-center justify-between mb-2 px-1">
                            <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">7D Velocity</p>
                            <span className="text-[9px] font-black text-emerald-500 flex items-center gap-1">
                                <span className="h-1 w-1 rounded-full bg-emerald-500 animate-pulse" />
                                {campaign.metrics.trend_status === "LIVE_FEED" ? "LIVE" : "SYNCING"}
                            </span>
                        </div>
                        <div className="h-10">
                            {sparklineData.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={sparklineData}>
                                        <defs>
                                            <linearGradient id={`colorSpend-${campaign.id}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2} />
                                                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <Area
                                            type="monotone"
                                            dataKey="spend"
                                            stroke="#3B82F6"
                                            strokeWidth={2}
                                            fillOpacity={1}
                                            fill={`url(#colorSpend-${campaign.id})`}
                                            animationDuration={1500}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full bg-slate-50 rounded-xl flex items-center justify-center border border-dashed border-slate-200">
                                    <span className="text-[8px] font-black text-slate-300">ESTABLISHING DATA</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Impact Predictions */}
                    <div className="flex items-center gap-6 shrink-0 lg:border-l lg:border-slate-100 lg:pl-8">
                        {campaign.expected_impact && (
                            <div className="group/impact flex items-center gap-4 bg-slate-50 rounded-2xl p-3 border border-slate-100 pr-5 transition-all group-hover:bg-blue-50 group-hover:border-blue-100">
                                <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-600/20 group-hover/impact:scale-110 transition-transform">
                                    <Zap className="h-5 w-5 fill-current" />
                                </div>
                                <div className="flex flex-col">
                                    <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.15em] mb-0.5 group-hover:text-blue-600">30D Forecast</p>
                                    <div className="flex items-baseline gap-1.5">
                                        <p className="text-xl font-black text-slate-900 leading-none">
                                            {campaign.expected_impact.secondary_metric_target === "ROAS" ? "+" : ""}
                                            {campaign.expected_impact.secondary_metric_value}
                                        </p>
                                        <span className="text-[10px] font-black text-slate-500 uppercase group-hover:text-blue-700">
                                            {campaign.expected_impact.secondary_metric_unit || ""} {campaign.expected_impact.secondary_metric_target}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-1 gap-1">
                            <div>
                                <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-0.5">Efficiency</p>
                                <p className="text-sm font-black text-slate-900 leading-tight">{(campaign.metrics.roas || 0).toFixed(2)}x</p>
                            </div>
                        </div>

                        <div className="h-10 w-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-300 group-hover:bg-blue-600 group-hover:text-white transition-all duration-300">
                            <ChevronRight className="h-6 w-6" />
                        </div>
                    </div>
                </div>
            </div>
        </Link>
    );
}
