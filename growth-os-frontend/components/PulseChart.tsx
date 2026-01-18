// components/PulseChart.tsx

"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * PulseChart – dual‑axis area chart showing Spend (soft slate) and Conversions (electric blue).
 * Data format: [{ date: string, spend: number, conversions: number }]
 */
export default function PulseChart({ campaignId }: { campaignId: string }) {
    const [data, setData] = useState<Array<{ date: string; spend: number; conversions: number }>>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Fetch 30‑day time‑series for the campaign. For now we reuse the campaign endpoint
        // which returns a `trend` array inside `metrics` if present. If not, we fallback to empty.
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        fetch(`${apiUrl}/api/campaign/${campaignId}`)
            .then((res) => res.json())
            .then((c) => {
                // Expect c.metrics.trend = [{date, spend, conversions}]
                const trend = (c.metrics?.trend as any[]) ?? [];
                setData(trend.map((d) => ({ date: d.date, spend: d.spend, conversions: d.conversions })));
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, [campaignId]);

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <div className="h-8 w-8 animate-pulse rounded-full border-2 border-blue-500" />
            </div>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                    <linearGradient id="colorSpend" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#64748B" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#64748B" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorConv" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.6} />
                        <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                    </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis yAxisId="left" orientation="left" tick={{ fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend verticalAlign="top" height={36} />
                <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="spend"
                    stroke="#64748B"
                    fillOpacity={1}
                    fill="url(#colorSpend)"
                />
                <Area
                    yAxisId="right"
                    type="monotone"
                    dataKey="conversions"
                    stroke="#0EA5E9"
                    strokeWidth={3}
                    fillOpacity={1}
                    fill="url(#colorConv)"
                    className="chart-line"
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}
