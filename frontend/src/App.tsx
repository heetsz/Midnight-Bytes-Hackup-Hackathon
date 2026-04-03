import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DashboardApp } from "@/components/landing-page";
import { LandingMarketing } from "@/components/landing-marketing";
import { SignInPage } from "@/components/ui/sign-in-flow-1";
import { SignUpPage } from "@/components/ui/sign-up";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingMarketing />} />
        <Route path="/login" element={<SignInPage />} />
        <Route path="/signup" element={<SignUpPage />} />
        <Route path="/dashboard" element={<DashboardApp />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
