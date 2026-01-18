"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    Send,
    Bot,
    User,
    Sparkles,
    ArrowLeft,
    Loader2,
    TrendingUp,
    BarChart3,
    Search,
    MessageCircle,
    MoreVertical,
    Zap,
    DollarSign,
    Activity,
    ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";

const ADS_CHIPS = [
    "🔍 Where is my budget leaking?",
    "📈 Increase ROAS on PMax",
    "⏰ Find high-performing hours",
    "📱 Desktop vs Mobile CPA",
];

const ANALYTICS_CHIPS = [
    "📊 Analyze top sources",
    "🌍 Geographic opportunities",
    "🎯 Conversion funnel audit",
    "📑 Landing page performance",
];

export default function ChatPage() {
    const params = useParams();
    const router = useRouter();
    const agentType = params.slug === "analytics" ? "analytics" : "ads";
    const chips = agentType === "ads" ? ADS_CHIPS : ANALYTICS_CHIPS;

    const [messages, setMessages] = useState<any[]>([
        {
            role: "ai",
            content:
                agentType === "ads"
                    ? "Hello! I'm your Ads Strategy Assistant. I analyze your campaign data to find hidden optimization opportunities. How can I assist you today?"
                    : "Hi! I'm your Analytics Explorer. I'm connected to your GA4 property to audit traffic and conversion behavior. What would you like to explore?",
        },
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async (customMsg?: string) => {
        const textToSend = customMsg || input.trim();
        if (!textToSend || loading) return;

        setInput("");
        setMessages((prev) => [...prev, { role: "human", content: textToSend }]);
        setLoading(true);

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: textToSend, agent_type: agentType }),
            });
            const data = await res.json();
            setMessages((prev) => [...prev, { role: "ai", content: data.response }]);
        } catch (e) {
            setMessages((prev) => [
                ...prev,
                { role: "ai", content: "Sorry, I encountered an error connecting to the brain." },
            ]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex h-screen bg-[#F8FAFC] flex-col overflow-hidden">
            {/* Header */}
            <header className="flex h-16 items-center shrink-0 border-b border-gray-200 bg-white/80 backdrop-blur-md px-8 sticky top-0 z-50">
                <button
                    onClick={() => router.back()}
                    className="mr-6 flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 text-slate-400 transition-all hover:bg-gray-50 hover:text-slate-900 active:scale-95 shadow-sm"
                >
                    <ArrowLeft className="h-5 w-5" />
                </button>
                <div className="flex items-center gap-4">
                    <div
                        className={cn(
                            "h-10 w-10 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/10",
                            agentType === "ads" ? "bg-blue-600 text-white" : "bg-emerald-600 text-white"
                        )}
                    >
                        {agentType === "ads" ? <TrendingUp className="h-5 w-5" /> : <BarChart3 className="h-5 w-5" />}
                    </div>
                    <div>
                        <h1 className="text-base font-black tracking-tight text-slate-900 leading-tight">
                            {agentType === "ads" ? "AI Strategist" : "Analytics Bot"}
                        </h1>
                        <div className="flex items-center gap-1.5 leading-none">
                            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">System Online</span>
                        </div>
                    </div>
                </div>

                <nav className="ml-12 flex items-center gap-6">
                    <a href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">Dashboard</a>
                </nav>

                <div className="ml-auto flex items-center gap-3">
                    <button className="h-9 w-9 rounded-lg border border-gray-100 flex items-center justify-center text-slate-400 hover:bg-gray-50 transition-colors">
                        <MoreVertical className="h-4 w-4" />
                    </button>
                </div>
            </header>

            <main className="flex-1 overflow-hidden flex flex-col items-center">
                <div
                    ref={scrollRef}
                    className="flex-1 w-full overflow-y-auto p-4 md:p-8 space-y-6 max-w-[1000px]"
                >
                    {messages.map((msg, i) => (
                        <div
                            key={i}
                            className={cn(
                                "flex items-start gap-4 transition-all duration-300",
                                msg.role === "human" ? "flex-row-reverse" : ""
                            )}
                        >
                            <div
                                className={cn(
                                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm border",
                                    msg.role === "ai"
                                        ? agentType === "ads"
                                            ? "bg-blue-50 text-blue-600 border-blue-100"
                                            : "bg-emerald-50 text-emerald-600 border-emerald-100"
                                        : "bg-white text-slate-400 border-gray-200"
                                )}
                            >
                                {msg.role === "ai" ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
                            </div>
                            <div
                                className={cn(
                                    "relative max-w-[85%] rounded-2xl px-5 py-3 shadow-sm",
                                    msg.role === "ai"
                                        ? "bg-white/80 backdrop-blur-sm text-slate-700 border border-white/40 font-medium leading-relaxed"
                                        : "bg-slate-900 text-white font-medium"
                                )}
                            >
                                {msg.content}
                                {msg.role === "ai" && (
                                    <div className="mt-3 flex items-center gap-2 border-t border-gray-50 pt-2 opacity-30">
                                        <Sparkles className="h-2.5 w-2.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-widest italic">Intelligence Thread</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div className="flex items-start gap-4">
                            <div
                                className={cn(
                                    "flex h-9 w-9 items-center justify-center rounded-xl animate-pulse shadow-sm border",
                                    agentType === "ads" ? "bg-blue-50 text-blue-600 border-blue-100" : "bg-emerald-50 text-emerald-600 border-emerald-100"
                                )}
                            >
                                <Bot className="h-4 w-4" />
                            </div>
                            <div className="flex gap-1.5 rounded-xl bg-white/70 backdrop-blur-sm p-4 items-center border border-white/40 shadow-sm">
                                <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse [animation-delay:-0.3s]" />
                                <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse [animation-delay:-0.15s]" />
                                <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Region */}
                <div className="w-full shrink-0 p-4 md:p-8 bg-gradient-to-t from-slate-50 to-transparent">
                    <div className="max-w-[800px] mx-auto space-y-4">
                        {/* Quick Chips */}
                        {!loading && messages.length < 3 && (
                            <div className="flex flex-wrap gap-2 justify-center">
                                {chips.map((chip) => (
                                    <button
                                        key={chip}
                                        onClick={() => handleSend(chip)}
                                        className="px-4 py-2 rounded-full border border-gray-200 bg-white shadow-sm text-xs font-bold text-slate-600 hover:border-blue-400 hover:text-blue-600 transition-all active:scale-95"
                                    >
                                        {chip}
                                    </button>
                                ))}
                            </div>
                        )}

                        <div className="relative glass-card rounded-[2rem] p-2 shadow-2xl shadow-slate-200">
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSend();
                                    }
                                }}
                                placeholder={
                                    agentType === "ads"
                                        ? "Ask about performance optimizations..."
                                        : "Audit website traffic and conversions..."
                                }
                                className="w-full bg-transparent p-4 pr-16 text-sm font-medium outline-none transition-all resize-none min-h-[60px]"
                                rows={1}
                            />
                            <button
                                onClick={() => handleSend()}
                                disabled={!input.trim() || loading}
                                className={cn(
                                    "absolute right-2.5 bottom-2.5 h-11 w-11 flex items-center justify-center rounded-full text-white shadow-xl transition-all active:scale-95 disabled:opacity-50 disabled:shadow-none",
                                    agentType === "ads" ? "bg-blue-600 shadow-blue-500/20" : "bg-emerald-600 shadow-emerald-500/20"
                                )}
                            >
                                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                            </button>
                        </div>
                        <p className="text-center text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                            Growth-OS Intelligence Tier: LLAMA-3.3-70B
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
