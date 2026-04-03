import React, { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

interface SignUpPageProps {
  className?: string;
}

export const SignUpPage = ({ className }: SignUpPageProps) => {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
   const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: hook up real signup logic
    console.log({ name, email, password, confirmPassword });
    setSuccess(true);
    setTimeout(() => {
      navigate("/login");
    }, 1500);
  };

  return (
    <div className={cn("flex w-full flex-col min-h-screen bg-black relative", className)}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(15,23,42,1)_0%,_black_70%)]" />
      <div className="absolute top-0 left-0 right-0 h-1/3 bg-gradient-to-b from-black to-transparent" />

      <div className="relative z-10 flex flex-1 items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="w-full max-w-md space-y-6 text-center"
        >
          <div className="space-y-1">
            <h1 className="text-[2.2rem] font-bold leading-[1.1] tracking-tight text-white">
              Create account
            </h1>
            <p className="text-sm text-white/60">
              Enter your details to get started.
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4 text-left">
            <div className="space-y-2">
              <label className="text-sm text-white/70">Full name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                className="w-full backdrop-blur-[1px] text-white border border-white/15 rounded-full py-3 px-4 focus:outline-none focus:border-white/40 bg-black/40"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-white/70">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full backdrop-blur-[1px] text-white border border-white/15 rounded-full py-3 px-4 focus:outline-none focus:border-white/40 bg-black/40"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-white/70">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full backdrop-blur-[1px] text-white border border-white/15 rounded-full py-3 px-4 focus:outline-none focus:border-white/40 bg-black/40"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-white/70">Confirm password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full backdrop-blur-[1px] text-white border border-white/15 rounded-full py-3 px-4 focus:outline-none focus:border-white/40 bg-black/40"
                required
              />
            </div>

            <button
              type="submit"
              className="mt-2 w-full rounded-full bg-white text-black font-medium py-3 hover:bg-white/90 transition-colors"
            >
              Sign up
            </button>
          </form>

          {success && (
            <p className="mt-3 text-xs text-emerald-400">
              Sign up successful. Redirecting to login...
            </p>
          )}

          <button
            type="button"
            onClick={() => navigate("/login")}
            className="text-xs text-white/60 hover:text-white/80 transition-colors"
          >
            Back to login
          </button>
        </motion.div>
      </div>
    </div>
  );
};
