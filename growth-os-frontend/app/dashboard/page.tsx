"use client";

import { useEffect, useState } from "react";
import CampaignCard from "@/components/CampaignCard";
import PulseChart from "@/components/PulseChart";
import {
    Plus,
    Search,
    Filter,
    DollarSign,
    BarChart3,
    RefreshCcw,
    Bell,
    Activity,
    Zap,
    Target,
    Cpu,
    Radio
} from "lucide-react";
import { motion } from "framer-motion";

export default function Dashboard() {
    const [campaigns, setCampaigns] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        fetch(`${apiUrl}/api/campaigns`)
            .then((res) => res.json())
            .then((data) => {
                setCampaigns(data);
                setLoading(false);
            });
    }, []);

    const totalSpend = campaigns.reduce((acc, c) => acc + (c.metrics.spend || 0), 0);
    const totalConversions = campaigns.reduce((acc, c) => acc + (c.metrics.conversions || 0), 0);
    const avgRoas =
        campaigns.length > 0
            ? campaigns.reduce((acc, c) => acc + (c.metrics.roas || 0), 0) / campaigns.length
            : 0;

    const container = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1,
            },
        },
    };

    const item = {
        hidden: { y: 20, opacity: 0 },
        show: { y: 0, opacity: 1 },
    };

    const activePulseCampaign = campaigns.find(c => c.metrics.trend_status === "LIVE_FEED") || campaigns[0];

    return (
        <div className="min-h-screen bg-[#F8FAFC]">
            {/* Header */}
            <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white/80 backdrop-blur-md px-8 sticky top-0 z-50">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-200">
                            <Cpu className="h-5 w-5 text-white" />
                        </div>
                        <h1 className="text-xl font-black tracking-tighter text-slate-900">Growth-OS <span className="text-blue-600">V2</span></h1>
                    </div>
                    <div className="h-6 w-px bg-gray-200 mx-2" />
                    <nav className="flex items-center gap-6">
                        <a href="/dashboard" className="text-sm font-black text-blue-600 uppercase tracking-widest">Dashboard</a>
                        <a href="/chat/ads" className="text-sm font-bold text-slate-400 hover:text-slate-900 transition-colors uppercase tracking-widest">Ads AI</a>
                        <a href="/chat/analytics" className="text-sm font-bold text-slate-400 hover:text-slate-900 transition-colors uppercase tracking-widest">Analytics AI</a>
                    </nav>
                </div>

                <div className="flex items-center gap-6">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Scan campaigns..."
                            className="h-10 rounded-full bg-slate-100 pl-10 pr-4 text-sm font-medium outline-none transition-all focus:bg-white focus:ring-2 focus:ring-blue-100 w-64 border border-transparent focus:border-blue-200"
                        />
                    </div>
                    <button className="relative rounded-full p-2 text-slate-400 hover:bg-gray-100 transition-colors">
                        <Bell className="h-5 w-5" />
                        <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-red-500 border-2 border-white" />
                    </button>
                    <div className="h-9 w-9 rounded-full bg-slate-900 flex items-center justify-center text-white text-xs font-bold ring-4 ring-slate-100">
                        RR
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-8 py-10 space-y-8">
                {/* Pulse Section */}
                <motion.section
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white rounded-[3rem] p-10 border border-gray-200 shadow-sm relative overflow-hidden"
                >
                    <div className="absolute top-0 right-0 p-10 opacity-[0.02]">
                        <BarChart3 className="h-64 w-64 text-blue-600" />
                    </div>

                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-8 mb-10 relative z-10">
                        <div className="space-y-1">
                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-black uppercase tracking-widest border border-blue-100 mb-2 shadow-sm">
                                <Radio className="h-3 w-3 animate-pulse" />
                                {activePulseCampaign?.metrics.trend_status === "LIVE_FEED" ? "Live Sync Active" : "Establishing Connection"}
                            </div>
                            <h2 className="text-4xl font-black tracking-tighter text-slate-900">
                                Account Pulse
                            </h2>
                            <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">
                                {activePulseCampaign?.metrics.trend_status === "LIVE_FEED"
                                    ? `Real-time performance for ${activePulseCampaign.name}`
                                    : "Establishing performance metrics"}
                            </p>
                        </div>
                        <div className="flex items-center gap-8 bg-slate-900 p-8 rounded-[2.5rem] border border-slate-800 shadow-2xl">
                            <div className="text-right">
                                <p className="text-[10px] font-black uppercase tracking-widest text-blue-400 mb-1">Total Spend</p>
                                <p className="text-3xl font-black text-white leading-none">${totalSpend.toLocaleString()}</p>
                            </div>
                            <div className="h-10 w-px bg-slate-800" />
                            <div className="text-right">
                                <p className="text-[10px] font-black uppercase tracking-widest text-emerald-400 mb-1">Conversions</p>
                                <div className="flex flex-col items-end">
                                    <p className="text-3xl font-black text-white leading-none">{totalConversions.toLocaleString()}</p>
                                    <span className="text-[8px] font-bold text-slate-500 uppercase tracking-tighter mt-1">Target Account-wide</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="h-[300px] w-full relative">
                        {activePulseCampaign ? (
                            <>
                                <PulseChart campaignId={activePulseCampaign.id} />
                                {activePulseCampaign.metrics.trend_status !== "LIVE_FEED" && (
                                    <div className="absolute inset-0 bg-white/70 backdrop-blur-md flex items-center justify-center rounded-3xl border border-dashed border-gray-300">
                                        <div className="text-center space-y-4 max-w-md p-8">
                                            <div className="h-16 w-16 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto shadow-xl shadow-blue-500/20 rotate-3">
                                                <BarChart3 className="h-8 w-8 text-white" />
                                            </div>
                                            <div className="space-y-2">
                                                <p className="text-sm font-black text-slate-900 uppercase tracking-[0.2em]">Analyzing Campaign Signals</p>
                                                <p className="text-xs font-bold text-slate-500 leading-relaxed">
                                                    Establishing fresh performance velocity for campaign: <span className="text-slate-900">{activePulseCampaign.name}</span>.
                                                </p>
                                            </div>
                                            <div className="flex items-center justify-center gap-2">
                                                <div className="h-1 w-8 bg-blue-600 rounded-full animate-pulse" />
                                                <div className="h-1 w-8 bg-blue-400 rounded-full animate-pulse [animation-delay:200ms]" />
                                                <div className="h-1 w-8 bg-blue-200 rounded-full animate-pulse [animation-delay:400ms]" />
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="h-full bg-slate-50 rounded-3xl animate-pulse flex items-center justify-center">
                                <p className="text-slate-400 font-black uppercase tracking-widest text-xs">Awaiting Network Signals...</p>
                            </div>
                        )}
                    </div>
                </motion.section>

                {/* Pipeline Header */}
                <div className="flex items-center justify-between pt-4">
                    <div className="space-y-1">
                        <h2 className="text-3xl font-black tracking-tighter text-slate-900">Optimization Pipeline</h2>
                        <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">Active precision control for your campaigns.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-sm font-black text-slate-600 shadow-sm hover:bg-gray-50 transition-all">
                            <Filter className="h-4 w-4" />
                            Filter Views
                        </button>
                        <button className="flex items-center gap-2 rounded-2xl bg-blue-600 px-6 py-3 text-sm font-black text-white shadow-[0_10px_20px_rgba(37,99,235,0.2)] transition-all hover:bg-blue-700 active:scale-[0.98]">
                            <RefreshCcw className="h-4 w-4" />
                            Refresh Campaigns
                        </button>
                    </div>
                </div>

                {/* Campaign List */}
                {loading ? (
                    <div className="grid grid-cols-1 gap-6">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="h-48 animate-pulse rounded-[2rem] bg-gray-200" />
                        ))}
                    </div>
                ) : (
                    <motion.div
                        variants={container}
                        initial="hidden"
                        animate="show"
                        className="grid grid-cols-1 gap-6"
                    >
                        {campaigns.map((campaign) => (
                            <motion.div key={campaign.id} variants={item}>
                                <CampaignCard campaign={campaign} />
                            </motion.div>
                        ))}
                    </motion.div>
                )}
            </main>
        </div>
    );
}
