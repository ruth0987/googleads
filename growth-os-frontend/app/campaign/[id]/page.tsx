"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ActionDiffCard from "@/components/ActionDiffCard";
import {
    ArrowLeft,
    Map,
    Target,
    Zap,
    TrendingUp,
    AlertCircle,
    CheckCircle2,
    Package,
    Activity,
    ArrowUpRight,
    ShieldCheck,
    ZapOff,
    Search,
    BrainCircuit,
    Cpu,
    Sparkles,
    BarChart3
} from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export default function CampaignDetail() {
    const params = useParams();
    const router = useRouter();
    const [campaign, setCampaign] = useState<any>(null);
    const [activeTab, setActiveTab] = useState("ALL");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        fetch(`${apiUrl}/api/campaign/${params.id}`)
            .then((res) => res.json())
            .then((data) => {
                setCampaign(data);
                setLoading(false);
            });
    }, [params.id]);

    if (loading)
        return (
            <div className="flex h-screen items-center justify-center bg-gray-50">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
            </div>
        );
    if (!campaign) return <div>Campaign not found</div>;

    const resourceTypes = ["ALL", ...Array.from(new Set(campaign.actions.map((a: any) => a.resource_type)))];

    const filteredActions =
        activeTab === "ALL"
            ? campaign.actions
            : campaign.actions.filter((a: any) => a.resource_type === activeTab);

    return (
        <div className="min-h-screen bg-[#F8FAFC]">
            {/* Header */}
            <header className="flex h-20 items-center border-b border-gray-100 bg-white/80 backdrop-blur-xl px-10 sticky top-0 z-50">
                <button
                    onClick={() => router.back()}
                    className="mr-8 flex h-11 w-11 items-center justify-center rounded-2xl border border-gray-100 text-slate-400 transition-all hover:bg-slate-900 hover:text-white hover:border-slate-900 active:scale-95 shadow-sm"
                >
                    <ArrowLeft className="h-5 w-5" />
                </button>
                <div className="flex flex-col">
                    <div className="flex items-center gap-3 mb-0.5">
                        <div className="rounded-md bg-blue-600 px-2 py-0.5 text-[9px] font-black uppercase text-white tracking-[0.2em]">
                            CAMPAIGN: {campaign.id.slice(-8)}
                        </div>
                        <span className="text-xs font-black text-slate-300 uppercase tracking-widest">{campaign.type}</span>
                    </div>
                    <h1 className="text-2xl font-black tracking-tight text-slate-900">{campaign.name}</h1>
                </div>

                <div className="ml-auto flex items-center gap-8">
                    <nav className="hidden md:flex items-center gap-8 mr-8 border-r border-gray-100 pr-8">
                        <a href="/dashboard" className="text-sm font-black text-slate-400 hover:text-blue-600 uppercase tracking-widest transition-colors">Dashboard</a>
                        <a href="/chat/ads" className="text-sm font-black text-slate-400 hover:text-blue-600 uppercase tracking-widest transition-colors">Ads AI</a>
                    </nav>
                    <div className="flex items-center gap-1.5 px-4 py-2 bg-emerald-50 text-emerald-600 rounded-2xl font-black text-[10px] uppercase tracking-[0.15em] border border-emerald-100">
                        <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Live Sync Active
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto p-10 space-y-12">
                {/* High-Visibility 30-Day Growth Forecast - AT THE TOP */}
                {campaign.expected_impact ? (
                    <motion.section
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-blue-600 rounded-[3rem] p-12 text-white shadow-2xl shadow-blue-500/20 relative overflow-hidden"
                    >
                        <div className="absolute top-0 right-0 p-12 opacity-10">
                            <Sparkles className="h-64 w-64" />
                        </div>
                        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-12">
                            <div className="space-y-6">
                                <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-white/20 backdrop-blur-md rounded-full text-[10px] font-black uppercase tracking-widest border border-white/10">
                                    <Zap className="h-4 w-4 fill-current" />
                                    30-Day Growth Forecast
                                </div>
                                <h3 className="text-5xl font-black tracking-tighter leading-none">
                                    Targeting {campaign.expected_impact.secondary_metric_value}{campaign.expected_impact.secondary_metric_unit || ""} {campaign.expected_impact.secondary_metric_target}
                                </h3>
                                <p className="text-blue-100 font-medium text-xl max-w-2xl leading-relaxed">
                                    Recommended optimizations in <span className="text-white font-bold">{campaign.optimization_mode?.replace("_", " ")}</span> mode are expected to significantly enhance account-level efficiency.
                                </p>
                            </div>
                            <div className="grid grid-cols-2 gap-10 bg-black/10 backdrop-blur-xl p-10 rounded-[3rem] border border-white/20">
                                <div className="text-center">
                                    <p className="text-[10px] font-black uppercase tracking-widest opacity-60 mb-2">{campaign.expected_impact.primary_metric_target || "Target Spend"}</p>
                                    <p className="text-4xl font-black">${campaign.expected_impact.primary_metric_value?.toLocaleString()}</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-[10px] font-black uppercase tracking-widest opacity-60 mb-2">Target Efficiency</p>
                                    <p className="text-4xl font-black text-emerald-300">{campaign.expected_impact.secondary_metric_value}{campaign.expected_impact.secondary_metric_unit || "x"}</p>
                                </div>
                            </div>
                        </div>
                    </motion.section>
                ) : (
                    <div className="bg-slate-100 rounded-[3rem] p-12 text-center border-2 border-dashed border-slate-200">
                        <p className="text-slate-400 font-black uppercase tracking-widest text-xs">Waiting for forecast signals...</p>
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
                    {/* Performance Metrics Card */}
                    <section className="bg-slate-900 rounded-[3rem] p-10 text-white shadow-2xl relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div className="relative z-10 space-y-10">
                            <div className="flex items-center gap-3">
                                <Cpu className="h-6 w-6 text-blue-400" />
                                <h3 className="text-xs font-black uppercase tracking-[0.2em] text-blue-400">Campaign Performance</h3>
                            </div>

                            <div className="space-y-8">
                                <div className="space-y-2">
                                    <div className="flex justify-between items-baseline">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Efficiency (ROAS)</p>
                                        <p className="text-3xl font-black text-white">{(campaign.detailed_metrics?.roas || campaign.metrics.roas || 0).toFixed(2)}x</p>
                                    </div>
                                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(((campaign.detailed_metrics?.roas || campaign.metrics.roas || 0) / 10) * 100, 100)}%` }} />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <div className="flex justify-between items-baseline">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Periodic Spend</p>
                                        <p className="text-3xl font-black text-white">${Math.round(campaign.detailed_metrics?.total_spend_usd || campaign.metrics.spend || 0).toLocaleString()}</p>
                                    </div>
                                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-indigo-500 rounded-full" style={{ width: "75%" }} />
                                    </div>
                                </div>
                            </div>

                            <div className="pt-8 border-t border-slate-800 grid grid-cols-2 gap-y-6 gap-x-4">
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">CTR</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.ctr_pct || 0).toFixed(2)}%</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Avg CPC</p>
                                    <p className="text-lg font-black text-white">${(campaign.detailed_metrics?.avg_cpc_usd || 0).toFixed(2)}</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Conv. Rate</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.conversion_rate_pct || 0).toFixed(2)}%</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Imp. Share</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.search_impression_share_pct || 0).toFixed(1)}%</p>
                                </div>
                            </div>

                            <div className="pt-8 border-t border-slate-800 grid grid-cols-2 gap-y-6 gap-x-4">
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Impressions</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.total_impressions || 0).toLocaleString()}</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Clicks</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.total_clicks || 0).toLocaleString()}</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Conversions</p>
                                    <p className="text-lg font-black text-white">{(campaign.detailed_metrics?.conversions || 0).toLocaleString()}</p>
                                </div>
                                <div>
                                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">CPA (Cost/Conv)</p>
                                    <p className="text-lg font-black text-white">${(campaign.detailed_metrics?.cpa_usd || 0).toFixed(2)}</p>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Strategy summary */}
                    <section className="lg:col-span-2 bg-white rounded-[3rem] p-10 border border-gray-100 shadow-sm relative overflow-hidden flex flex-col">
                        <div className="absolute bottom-0 right-0 p-10 opacity-[0.03]">
                            <BarChart3 className="h-48 w-48 text-blue-600" />
                        </div>
                        <div className="relative z-10 flex-grow flex flex-col">
                            <div className="flex items-center justify-between mb-8">
                                <div className="flex items-center gap-3">
                                    <div className="h-12 w-12 rounded-[1rem] bg-slate-50 flex items-center justify-center border border-slate-100">
                                        <BrainCircuit className="h-6 w-6 text-slate-900" />
                                    </div>
                                    <h2 className="text-xl font-black tracking-tight text-slate-900 uppercase tracking-widest">Strategy Summary</h2>
                                </div>
                                <div className="flex gap-2">
                                    <div className={cn(
                                        "px-4 py-2 rounded-2xl font-black text-[10px] uppercase tracking-widest border",
                                        campaign.strategy_details?.risk_level === "LOW" ? "bg-emerald-50 text-emerald-700 border-emerald-100" : "bg-amber-50 text-amber-700 border-amber-100"
                                    )}>
                                        Risk: {campaign.strategy_details?.risk_level || "LOW"}
                                    </div>
                                    <div className="px-4 py-2 bg-blue-50 text-blue-700 rounded-2xl font-black text-[10px] uppercase tracking-widest border border-blue-100">
                                        {campaign.optimization_mode?.replace(/_/g, " ") || "BALANCED"}
                                    </div>
                                </div>
                            </div>
                            <p className="text-3xl font-black tracking-tighter leading-[1.15] text-slate-800 mb-10">
                                {campaign.strategy_summary || "Analyzing performance signals for optimization opportunities..."}
                            </p>

                            {/* 30-Day Forecast */}
                            {campaign.expected_impact && (
                                <div className="mb-10 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-3xl border border-blue-100">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Zap className="h-4 w-4 text-blue-600" />
                                        <p className="text-[10px] font-black uppercase tracking-widest text-blue-600">30-Day Impact Forecast</p>
                                    </div>
                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <p className="text-xs font-bold text-slate-500 mb-1">Primary Target</p>
                                            <p className="text-2xl font-black text-slate-900">
                                                {campaign.expected_impact.primary_metric_value} {campaign.expected_impact.primary_metric_target}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-bold text-slate-500 mb-1">Secondary Target</p>
                                            <p className="text-2xl font-black text-slate-900">
                                                {campaign.expected_impact.secondary_metric_value}{campaign.expected_impact.secondary_metric_unit || ""} {campaign.expected_impact.secondary_metric_target}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="mt-auto grid grid-cols-1 md:grid-cols-3 gap-6 pt-10 border-t border-gray-100">
                                {campaign.strategy_details?.primary_strategy && (
                                    <div className="space-y-2">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-blue-600">Primary Strategy</p>
                                        <p className="text-sm font-black text-slate-900 leading-tight">{campaign.strategy_details.primary_strategy}</p>
                                    </div>
                                )}
                                {campaign.strategy_details?.secondary_strategy && (
                                    <div className="space-y-2">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Secondary Strategy</p>
                                        <p className="text-sm font-bold text-slate-600 leading-tight">{campaign.strategy_details.secondary_strategy}</p>
                                    </div>
                                )}
                                {campaign.strategy_details?.tertiary_strategy && (
                                    <div className="space-y-2">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Tertiary Strategy</p>
                                        <p className="text-sm font-bold text-slate-600 leading-tight">{campaign.strategy_details.tertiary_strategy}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </section>
                </div>

                {/* Growth Funnel Audit */}
                <section className="bg-white rounded-[3rem] p-10 border border-gray-100 shadow-sm space-y-8">
                    <div className="flex flex-col gap-1">
                        <h3 className="text-3xl font-black tracking-tighter text-slate-900">Growth Funnel Audit</h3>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Full-funnel performance metrics</p>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-8">
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Spend</p>
                            <p className="text-2xl font-black text-slate-900">${(campaign.detailed_metrics?.total_spend_usd || 0).toLocaleString()}</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Impressions</p>
                            <p className="text-2xl font-black text-slate-900">{(campaign.detailed_metrics?.total_impressions || 0).toLocaleString()}</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Clicks</p>
                            <p className="text-2xl font-black text-slate-900">{(campaign.detailed_metrics?.total_clicks || 0).toLocaleString()}</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Conversions</p>
                            <p className="text-2xl font-black text-slate-900">{(campaign.detailed_metrics?.conversions || 0).toLocaleString()}</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">ROAS</p>
                            <p className="text-2xl font-black text-slate-900">{(campaign.detailed_metrics?.roas || 0).toFixed(2)}x</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">CPA</p>
                            <p className="text-2xl font-black text-slate-900">${(campaign.detailed_metrics?.cpa_usd || 0).toFixed(2)}</p>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 pt-8 border-t border-gray-50">
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">CTR</p>
                            <p className="text-xl font-black text-slate-900">{(campaign.detailed_metrics?.ctr_pct || 0).toFixed(2)}%</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Conv. Rate</p>
                            <p className="text-xl font-black text-slate-900">{(campaign.detailed_metrics?.conversion_rate_pct || 0).toFixed(2)}%</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Budget Lost IS</p>
                            <p className="text-xl font-black text-amber-600">{(campaign.detailed_metrics?.search_budget_lost_impression_share_pct || 0).toFixed(1)}%</p>
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Rank Lost IS</p>
                            <p className="text-xl font-black text-blue-600">{(campaign.detailed_metrics?.search_rank_lost_impression_share_pct || 0).toFixed(1)}%</p>
                        </div>
                    </div>
                </section>


                {/* Deployment Diagnostics */}
                {campaign.signal_breakdown && (
                    <section className="space-y-8">
                        <div className="flex flex-col gap-1">
                            <h3 className="text-3xl font-black tracking-tighter text-slate-900">Deployment Diagnostics</h3>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Cross-sectional signal distribution</p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                            {/* Device Signals */}
                            <div className="bg-white rounded-[2.5rem] p-8 border border-gray-100 shadow-sm space-y-6">
                                <div className="flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-xl bg-blue-50 flex items-center justify-center border border-blue-100">
                                        <Activity className="h-5 w-5 text-blue-600" />
                                    </div>
                                    <h4 className="text-xs font-black uppercase tracking-widest text-slate-900">Device Signals</h4>
                                </div>
                                <div className="space-y-4">
                                    {Object.entries(campaign.signal_breakdown.devices || {}).map(([device, data]: [string, any]) => (
                                        <div key={device} className="space-y-1.5">
                                            <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight">
                                                <span className="text-slate-500">{device}</span>
                                                <span className="text-slate-900 font-black">${Math.round(data.cost).toLocaleString()}</span>
                                            </div>
                                            <div className="h-1.5 w-full bg-slate-50 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-blue-500 rounded-full"
                                                    style={{ width: `${(data.cost / (campaign.metrics.spend || 1)) * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Inventory / Products */}
                            <div className="bg-white rounded-[2.5rem] p-8 border border-gray-100 shadow-sm space-y-6">
                                <div className="flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-xl bg-violet-50 flex items-center justify-center border border-violet-100">
                                        <Package className="h-5 w-5 text-violet-600" />
                                    </div>
                                    <h4 className="text-xs font-black uppercase tracking-widest text-slate-900">Top Inventory</h4>
                                </div>
                                <div className="space-y-4">
                                    {(campaign.signal_breakdown.top_products || []).slice(0, 3).map((product: any, idx: number) => (
                                        <div key={idx} className="space-y-1.5">
                                            <p className="text-[10px] font-bold text-slate-900 truncate leading-none">{product.title}</p>
                                            <div className="flex justify-between items-center">
                                                <span className="text-[9px] font-black text-emerald-600 uppercase tracking-tighter">${product.revenue.toLocaleString()}</span>
                                                <span className="text-[9px] font-bold text-slate-400">Rev.</span>
                                            </div>
                                            <div className="h-1 w-full bg-slate-50 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-violet-500 rounded-full"
                                                    style={{ width: `${Math.min((product.revenue / 1000) * 100, 100)}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* PMax Asset Groups */}
                            {campaign.signal_breakdown.asset_groups?.length > 0 && (
                                <div className="bg-white rounded-[2.5rem] p-8 border border-gray-100 shadow-sm space-y-6">
                                    <div className="flex items-center gap-3">
                                        <div className="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center border border-indigo-100">
                                            <Target className="h-5 w-5 text-indigo-600" />
                                        </div>
                                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-900">Asset Performance</h4>
                                    </div>
                                    <div className="space-y-4">
                                        {campaign.signal_breakdown.asset_groups.slice(0, 3).map((group: any, idx: number) => (
                                            <div key={idx} className="space-y-1.5">
                                                <p className="text-[10px] font-bold text-slate-500 truncate">{group.name.split('/').pop()}</p>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-[10px] font-black text-slate-900">${Math.round(group.cost).toLocaleString()}</span>
                                                    <span className="text-[9px] font-black text-blue-500 uppercase tracking-widest">{group.conversions} Conv.</span>
                                                </div>
                                                <div className="h-1.5 w-full bg-slate-50 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-indigo-500 rounded-full"
                                                        style={{ width: `${Math.min((group.cost / 200) * 100, 100)}%` }}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Budget Health */}
                            <div className="bg-white rounded-[2.5rem] p-8 border border-gray-100 shadow-sm space-y-6">
                                <div className="flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-xl bg-emerald-50 flex items-center justify-center border border-emerald-100">
                                        <Target className="h-5 w-5 text-emerald-600" />
                                    </div>
                                    <h4 className="text-xs font-black uppercase tracking-widest text-slate-900">Budget Status</h4>
                                </div>
                                <div className="space-y-6">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="text-[9px] font-black uppercase tracking-widest text-slate-400 mb-1">Daily Cap</p>
                                            <p className="text-xl font-black text-slate-900">${campaign.budget_health?.daily_budget_usd?.toLocaleString()}</p>
                                        </div>
                                        <div>
                                            <p className="text-[9px] font-black uppercase tracking-widest text-slate-400 mb-1">Utilization</p>
                                            <p className="text-xl font-black text-slate-900">{((campaign.budget_health?.spend_vs_budget_ratio || 0) * 100).toFixed(0)}%</p>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex justify-between text-[9px] font-black uppercase tracking-widest">
                                            <span className="text-slate-400">Pattern</span>
                                            <span className={campaign.budget_health?.is_limited_by_budget ? "text-amber-500" : "text-emerald-500"}>
                                                {campaign.budget_health?.is_limited_by_budget ? "Limited" : "Stable"}
                                            </span>
                                        </div>
                                        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                            <div
                                                className={cn("h-full transition-all", campaign.budget_health?.is_limited_by_budget ? "bg-amber-400" : "bg-emerald-400")}
                                                style={{ width: `${Math.min((campaign.budget_health?.spend_vs_budget_ratio || 0) * 100, 100)}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                )}

                {/* Optimizations */}
                <section className="bg-slate-50/50 rounded-[4rem] p-12 border border-slate-100/50 space-y-12">
                    <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 px-4">
                        <div className="space-y-3">
                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-[10px] font-black uppercase tracking-[0.2em]">
                                <Sparkles className="h-3 w-3" />
                                Growth Engine Ready
                            </div>
                            <h3 className="text-5xl font-black tracking-tighter text-slate-900 leading-none">
                                Optimization Queue
                            </h3>
                            <p className="text-sm font-bold text-slate-400 uppercase tracking-widest pl-1">
                                High-precision deployments available for this cycle
                            </p>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-white rounded-[2rem] border border-slate-200/60 shadow-sm backdrop-blur-xl">
                            {resourceTypes.map((type: any) => (
                                <button
                                    key={type}
                                    onClick={() => setActiveTab(type)}
                                    className={cn(
                                        "rounded-full px-8 py-3 text-[10px] font-black uppercase tracking-widest transition-all duration-300",
                                        activeTab === type
                                            ? "bg-slate-900 text-white shadow-xl shadow-slate-900/20"
                                            : "text-slate-400 hover:text-slate-900 hover:bg-slate-50"
                                    )}
                                >
                                    {type === "ALL" ? "Full Stack" : type.replace(/_/g, " ")}
                                </button>
                            ))}
                        </div>
                    </div>

                    {filteredActions.length > 0 ? (
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-12">
                            {filteredActions.map((action: any, i: number) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ delay: i * 0.05 }}
                                >
                                    <ActionDiffCard action={action} campaignId={campaign.id} />
                                </motion.div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center rounded-[4rem] border-2 border-dashed border-gray-200 bg-white py-32 text-center group">
                            <div className="rounded-full bg-gray-50 p-6 transition-transform group-hover:rotate-12">
                                <Sparkles className="h-12 w-12 text-slate-300" />
                            </div>
                            <h4 className="mt-6 text-2xl font-black text-slate-900 tracking-tighter">Campaign Efficiency Reached</h4>
                            <p className="mt-2 text-sm font-bold text-slate-500 uppercase tracking-widest">No pending optimizations for this cycle.</p>
                        </div>
                    )}
                </section>
            </main>
        </div>
    );
}
