import { useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { api } from "@/lib/api";
import { ApiError } from "@/lib/http";
import { getSessionToken } from "@/lib/session";
import {
  initializeTelegram,
  isTelegramMiniApp,
  setTelegramBackButton,
  telegramInitData,
} from "@/lib/telegram";
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

function TelegramBackButton() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    const root = pathname === "/" || pathname === "/onboarding" || pathname === "/recommendations";
    return setTelegramBackButton(root ? null : () => navigate(-1));
  }, [navigate, pathname]);
  return null;
}

function TelegramBootstrap({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isTelegramMiniApp()) return;
    initializeTelegram();
    if (started.current) return;
    started.current = true;
    const initData = telegramInitData();
    if (!initData) {
      setError("Telegram did not provide launch data. Reopen the app from the bot.");
      return;
    }
    api
      .loginTelegram(initData)
      .then(() => api.getOnboarding())
      .then((state) => navigate(state.onboarding_completed ? "/recommendations" : "/onboarding", { replace: true }))
      .catch((caught: unknown) => {
        if (!(caught instanceof ApiError)) {
          setError("The app is temporarily unavailable. Try again shortly.");
          return;
        }
        if (caught.code === "admission_closed" || caught.code === "invite_required" || caught.code === "invite_invalid") {
          setError("This invitation is unavailable.");
          return;
        }
        if (caught.code === "invalid_telegram_launch") {
          setError("This Telegram launch has expired. Reopen the app from the bot.");
          return;
        }
        setError(caught.isNetworkError ? "The app is temporarily unavailable. Try again shortly." : "Unable to sign in with Telegram.");
      });
  }, [navigate]);

  if (error) return <main className="p-6 text-slate-900">{error}</main>;
  return <>{children}</>;
}

function TelegramRoute({ children }: { children: React.ReactNode }) {
  return isTelegramMiniApp() ? <Navigate to="/" replace /> : <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <TelegramBootstrap>
        <TelegramBackButton />
        <SignedInBar />
        <Routes>
          <Route path="/" element={<StatusPage />} />
          <Route path="/register" element={<TelegramRoute><RegisterPage /></TelegramRoute>} />
          <Route path="/login" element={<TelegramRoute><LoginPage /></TelegramRoute>} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/onboarding/pending" element={<OnboardingPendingPage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/people/:profileId" element={<PersonPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
          <Route path="/matches" element={<MatchesPage />} />
          <Route path="/conversations/:conversationId" element={<ConversationPage />} />
        </Routes>
      </TelegramBootstrap>
    </BrowserRouter>
  );
}
