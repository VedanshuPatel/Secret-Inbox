import { useState } from "react";
import Dashboard from "./Dashboard";
import Feedback from "./Feedback";
import CheckReply from "./CheckReply";
import { USER_API } from "./api";

/** Render the public-link route, saved owner session, or sign-in screen. */
export default function App() {
  const [accessToken, setAccessToken] = useState<string | null>(() => localStorage.getItem("accessToken"));
  const [userId, setUserId] = useState<string | null>(() => (
    localStorage.getItem("accessToken") ? localStorage.getItem("userId") : null
  ));
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [registering, setRegistering] = useState(true);
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  // Public links select a screen before the stored owner session is considered.
  const params = new URLSearchParams(window.location.search);
  const isFeedbackRoute = params.get("route") === "feedback";
  const inviteToken = isFeedbackRoute ? params.get("invite") : null;
  const checkToken = params.get("route") === "check" ? params.get("token") : null;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    setIsLoggingIn(true);
    try {
      const res = await fetch(`${USER_API}/auth/${registering ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameInput, password: passwordInput }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not sign in. Please try again.");
      if (!data.access_token) throw new Error("The service did not return an access token.");
      localStorage.setItem("userId", data.id);
      localStorage.setItem("accessToken", data.access_token);
      setUserId(data.id);
      setAccessToken(data.access_token);
      setPasswordInput("");
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Could not connect to the service. Please try again.");
    } finally {
      setIsLoggingIn(false);
    }
  };

  if (isFeedbackRoute) return <Feedback inviteToken={inviteToken} />;
  if (checkToken) return <CheckReply token={checkToken} />;
  if (userId && accessToken) {
    return (
      <Dashboard
        userId={userId}
        accessToken={accessToken}
        onLogout={() => {
          localStorage.removeItem("userId");
          localStorage.removeItem("accessToken");
          setUserId(null);
          setAccessToken(null);
          setPasswordInput("");
          setRegistering(false);
        }}
      />
    );
  }

  return (
    <main className="min-h-screen px-5 py-10 sm:px-8 sm:py-14">
      <div className="mx-auto grid min-h-[calc(100svh-7rem)] w-full max-w-5xl items-center gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
        <section className="mx-auto w-full max-w-lg text-center lg:mx-0 lg:text-left">
          <div className="mb-8 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-gold-500/25 bg-gold-500/10 text-xl text-gold-300 shadow-lg shadow-gold-500/5">
            ✳
          </div>
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-gold-400">A little honesty goes a long way</p>
          <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink-50 sm:text-6xl">
            Say it like you <span className="text-gold-400">mean it.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-md text-base leading-7 text-ink-300 lg:mx-0">
            Create a quiet space for the thoughts your friends have been meaning to share. No names, just honest notes.
          </p>
          <div className="mt-8 hidden items-center gap-3 text-sm text-ink-400 lg:flex">
            <span className="flex h-7 w-7 items-center justify-center rounded-full border border-ink-700 bg-ink-850 text-gold-300">✓</span>
            Anonymous by design
            <span className="mx-1 h-1 w-1 rounded-full bg-ink-600" />
            Yours to manage
          </div>
        </section>

        <form
          onSubmit={handleLogin}
          className="mx-auto w-full max-w-md rounded-[2rem] border border-ink-700/80 bg-ink-900/90 p-7 shadow-2xl shadow-black/40 backdrop-blur sm:p-9"
        >
          <div className="mb-7">
            <span
              className={`mb-3 inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                registering
                  ? "border-gold-500/30 bg-gold-500/10 text-gold-300"
                  : "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
              }`}
            >
              {registering ? "A new beginning" : "Welcome back"}
            </span>
            <h2 className="font-display text-3xl font-semibold tracking-tight text-ink-50">
              {registering ? "Create your inbox." : "Your inbox awaits."}
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-400">
              {registering
                ? "Choose your username and a password to make this space yours."
                : "Sign in with your username and password to pick up where you left off."}
            </p>
          </div>
          {loginError && <p role="alert" className="mb-4 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">{loginError}</p>}
          <label htmlFor="username" className="mb-2 block text-sm font-medium text-ink-200">Username</label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            placeholder={registering ? "Choose a username" : "Your username"}
            value={usernameInput}
            onChange={(e) => setUsernameInput(e.target.value)}
            className="mb-4 w-full rounded-xl border border-ink-600 bg-ink-850 px-4 py-3.5 text-ink-50 placeholder:text-ink-500 transition focus:border-gold-500/70 focus:outline-none focus:ring-2 focus:ring-gold-500/20"
            required
          />
          <label htmlFor="password" className="mb-2 block text-sm font-medium text-ink-200">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={registering ? "new-password" : "current-password"}
            placeholder={registering ? "At least 12 characters" : "Your password"}
            value={passwordInput}
            onChange={(e) => setPasswordInput(e.target.value)}
            className="mb-4 w-full rounded-xl border border-ink-600 bg-ink-850 px-4 py-3.5 text-ink-50 placeholder:text-ink-500 transition focus:border-gold-500/70 focus:outline-none focus:ring-2 focus:ring-gold-500/20"
            minLength={12}
            maxLength={128}
            required
          />
          <button
            type="submit"
            disabled={isLoggingIn}
            className="w-full rounded-xl bg-gold-500 px-4 py-3.5 font-semibold text-ink-950 shadow-lg shadow-gold-500/10 transition hover:bg-gold-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900 disabled:cursor-wait disabled:opacity-70"
          >
            {isLoggingIn ? "Please wait…" : registering ? "Create private inbox" : "Sign in"}
            {!isLoggingIn && <span aria-hidden="true" className="ml-2">→</span>}
          </button>
          <button
            type="button"
            className={`mt-4 w-full text-center text-xs leading-5 transition ${
              registering ? "text-gold-300 hover:text-gold-200" : "text-emerald-300 hover:text-emerald-200"
            }`}
            onClick={() => {
              setRegistering((value) => !value);
              setPasswordInput("");
              setLoginError("");
            }}
          >
            {registering ? "Already have an account? Sign in" : "New here? Create an account"}
          </button>
          <p className="mt-3 text-center text-xs leading-5 text-ink-500">Your inbox is private. You decide what stays.</p>
        </form>
      </div>
    </main>
  );
}
