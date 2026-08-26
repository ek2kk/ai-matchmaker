import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { api } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { ConversationPage } from "@/pages/ConversationPage";
import { LoginPage } from "@/pages/LoginPage";
import { MatchesPage } from "@/pages/MatchesPage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { OnboardingPendingPage } from "@/pages/OnboardingPendingPage";
import { PeoplePage } from "@/pages/PeoplePage";
import { PersonPage } from "@/pages/PersonPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { StatusPage } from "@/pages/StatusPage";

function SignedInBar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  if (!getSessionToken() || pathname === "/login" || pathname === "/register") {
    return null;
  }
  return (
    <div className="flex justify-end border-b border-slate-200 bg-white px-6 py-2">
      <button
        type="button"
        className="text-sm text-slate-700 underline"
        onClick={() => {
          api.logout().finally(() => navigate("/login"));
        }}
      >
        Log out
      </button>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <SignedInBar />
      <Routes>
        <Route path="/" element={<StatusPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/onboarding/pending" element={<OnboardingPendingPage />} />
        <Route path="/people" element={<PeoplePage />} />
        <Route path="/people/:profileId" element={<PersonPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/matches" element={<MatchesPage />} />
        <Route path="/conversations/:conversationId" element={<ConversationPage />} />
      </Routes>
    </BrowserRouter>
  );
}
