import { HeroGeometric } from "@/components/ui/shape-landing-hero";
import { LiquidButton } from "@/components/ui/liquid-glass-button";
import { Link } from "react-router-dom";

export function LandingMarketing() {
  return (
    <div className="relative min-h-screen w-full text-slate-50">
      <HeroGeometric
        badge=""
        title1="AI Fraud Detection System"
        title2="Real-time Transaction Monitoring"
      />
      <Link to="/login" className="absolute top-4 right-4">
        <LiquidButton>
          Login
        </LiquidButton>
      </Link>
    </div>
  );
}
