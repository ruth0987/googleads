"use client";

import Link from "next/link";
import { TrendingUp, ArrowRight, Zap, Shield, BarChart3, Globe, Sparkles, Activity, Play, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

export default function LandingPage() {
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2
      }
    }
  };

  const item = {
    hidden: { y: 20, opacity: 0 },
    show: { y: 0, opacity: 1 }
  };

  return (
    <div className="min-h-screen bg-white overflow-x-hidden selection:bg-blue-100 selection:text-blue-900">
      {/* Immersive Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-100/40 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-indigo-100/40 rounded-full blur-[120px] animate-pulse [animation-delay:2s]" />
      </div>

      {/* Nav */}
      <nav className="flex h-20 items-center justify-between px-10 border-b border-gray-100/50 bg-white/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-200">
            <Activity className="h-6 w-6 text-white" />
          </div>
          <span className="text-xl font-black tracking-tighter text-slate-900">Growth-OS <span className="text-blue-600">V2</span></span>
        </div>
        <div className="flex items-center gap-10 text-sm font-bold text-slate-500 uppercase tracking-widest">
          <Link href="#" className="hover:text-blue-600 transition-colors">Framework</Link>
          <Link href="#" className="hover:text-blue-600 transition-colors">Data Engine</Link>
          <div className="h-6 w-px bg-gray-200" />
          <Link href="/dashboard" className="group flex items-center gap-2 rounded-full bg-slate-900 px-8 py-3 text-white shadow-2xl shadow-slate-200 hover:bg-blue-600 transition-all active:scale-95">
            Open Console
            <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="px-10 py-32 relative">
        <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="space-y-10"
          >
            <motion.div variants={item} className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-[10px] font-black uppercase tracking-[0.2em] text-blue-600 border border-blue-100 italic">
              <Sparkles className="h-3.5 w-3.5" />
              Intelligence Engine V2.0 Active
            </motion.div>

            <motion.h1 variants={item} className="text-8xl font-black leading-[0.95] tracking-tighter text-slate-900">
              AD SPEND <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">REIMAGINED.</span>
            </motion.h1>

            <motion.p variants={item} className="text-2xl font-medium leading-relaxed text-slate-500 max-w-[550px]">
              The first autonomous growth operating system for elite marketing teams. Analyze, strategize, and execute with AI-native precision.
            </motion.p>

            <motion.div variants={item} className="flex flex-wrap items-center gap-6 pt-4">
              <Link href="/dashboard" className="flex h-16 items-center gap-4 rounded-full bg-blue-600 px-10 text-lg font-black text-white shadow-[0_20px_40px_rgba(37,99,235,0.3)] transition-all hover:bg-blue-700 hover:-translate-y-1 active:scale-95 uppercase tracking-widest">
                Deploy Growth-OS
                <ArrowRight className="h-5 w-5" />
              </Link>
              <button className="flex h-16 items-center gap-4 rounded-full bg-white border border-gray-200 px-10 text-lg font-bold text-slate-900 shadow-xl transition-all hover:bg-gray-50 active:scale-95">
                <Play className="h-5 w-5 fill-slate-900" />
                Watch Demo
              </button>
            </motion.div>

            <motion.div variants={item} className="flex items-center gap-8 border-t border-gray-100 pt-10">
              <div className="space-y-1">
                <p className="text-3xl font-black text-slate-900">$2.4B</p>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Total Managed Spend</p>
              </div>
              <div className="h-10 w-px bg-gray-100" />
              <div className="space-y-1">
                <p className="text-3xl font-black text-slate-900">140%</p>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Avg. ROAS Increase</p>
              </div>
            </motion.div>
          </motion.div>

          {/* Hero Visual - Animated Bento */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, rotate: 2 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            transition={{ duration: 1, ease: "easeOut" }}
            className="relative"
          >
            <div className="absolute -inset-20 rounded-[100px] bg-gradient-to-br from-blue-500/10 to-indigo-500/10 blur-[120px]" />
            <div className="relative rounded-[3rem] border border-gray-200 bg-white p-8 shadow-[0_50px_100px_-20px_rgba(0,0,0,0.1)] overflow-hidden group">
              <div className="absolute top-0 right-0 p-8">
                <Activity className="h-12 w-12 text-blue-50/50 group-hover:text-blue-100 transition-colors" />
              </div>

              <div className="space-y-8 relative">
                <div className="flex items-center gap-4">
                  <div className="h-12 w-12 rounded-2xl bg-blue-600 flex items-center justify-center shadow-xl shadow-blue-200">
                    <Zap className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <p className="text-xs font-black uppercase tracking-widest text-slate-400">Optimization Pulse</p>
                    <p className="text-2xl font-black text-slate-900 tracking-tight">Strategy Node Integrated</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">Confidence Level</p>
                    <p className="text-3xl font-black text-emerald-500">98.4%</p>
                  </div>
                  <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">Simulated Impact</p>
                    <p className="text-3xl font-black text-blue-600">+22%</p>
                  </div>
                </div>

                <div className="bg-slate-900 rounded-[2rem] p-6 text-white flex items-center justify-between shadow-2xl">
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-full bg-white/10 flex items-center justify-center">
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                    </div>
                    <p className="font-bold tracking-tight">Deploying scaling bid to <br /> 12 campaign nodes...</p>
                  </div>
                  <div className="h-8 w-24 bg-white/10 rounded-full overflow-hidden relative">
                    <div className="absolute inset-0 bg-blue-500 w-[70%] animate-pulse" />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </header>

      {/* Features Grid - Scroll Reveal */}
      <section className="px-10 py-40 border-t border-gray-100 bg-[#FBFDFE]">
        <div className="max-w-[1200px] mx-auto text-center space-y-20">
          <div className="space-y-4">
            <h2 className="text-5xl font-black tracking-tighter text-slate-900">ENGINEERED FOR VELOCITY.</h2>
            <p className="text-xl font-medium text-slate-500 max-w-[700px] mx-auto">Traditional dashboards are passive. Growth-OS is reactive, predictive, and relentless.</p>
          </div>

          <div className="grid grid-cols-3 gap-12">
            {[
              { title: "Anomaly Pulse", desc: "Real-time detection of spending spikes and conversion drops. Never miss a leak again.", icon: BarChart3 },
              { title: "Predictive Bidding", desc: "AI-native bid simulation that forecasts ROAS impact before you change a single dollar.", icon: TrendingUp },
              { title: "Universal Schema", desc: "One unified data graph connecting Google Ads, Analytics, and CRM signals into one consciousness.", icon: Globe },
            ].map((feat, idx) => (
              <motion.div
                key={feat.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="group space-y-6 text-left p-10 rounded-[2.5rem] bg-white border border-gray-100 shadow-sm hover:shadow-xl hover:border-blue-100 transition-all"
              >
                <div className="h-14 w-14 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-900 group-hover:bg-blue-600 group-hover:text-white transition-all">
                  <feat.icon className="h-7 w-7" />
                </div>
                <h3 className="text-2xl font-black text-slate-900 tracking-tight">{feat.title}</h3>
                <p className="text-base font-medium text-slate-500 leading-relaxed">{feat.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="p-10 pb-32">
        <div className="max-w-[1400px] mx-auto rounded-[4rem] bg-slate-900 p-24 text-center space-y-10 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
            <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-blue-500 rounded-full blur-[150px]" />
          </div>

          <h2 className="text-7xl font-black tracking-tight text-white relative z-10">THE FUTURE OF SEARCH IS <br /> ALREADY RUNNING.</h2>
          <p className="text-xl font-medium text-slate-400 max-w-[600px] mx-auto relative z-10">Join 12,000+ accounts leveraging autonomous strategy.</p>

          <div className="flex justify-center relative z-10">
            <Link href="/dashboard" className="flex h-20 items-center gap-6 rounded-full bg-white px-12 text-2xl font-black text-slate-900 shadow-2xl transition-all hover:scale-105 active:scale-95 uppercase tracking-tighter">
              Get Command Access
              <ArrowRight className="h-8 w-8 text-blue-600" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="m9 18 6-6-6-6" /></svg>
  );
}
