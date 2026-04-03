// @ts-nocheck

import { HeroGeometric } from "@/components/ui/shape-landing-hero";
import { Link } from "react-router-dom";

export function LandingMarketing() {
  return (
    <div className="relative min-h-screen w-full text-slate-50">
      <HeroGeometric
        badge="AI Fraud Detection System"
        title1="AI Fraud Detection System"
        title2="Real-time Transaction Monitoring"
      />
      <Link
        to="/login"
        className="absolute top-4 right-4 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400 text-slate-950 shadow-soft-glow hover:brightness-110 transition-all"
      >
        Login
      </Link>
    </div>
  );
}
