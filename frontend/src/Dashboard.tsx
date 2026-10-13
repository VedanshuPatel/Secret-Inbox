import { useEffect, useState } from "react";
import { MESSAGE_API, USER_API } from "./api";

interface Msg {
  id: number;
  content: string;
  status: "active" | "archived" | "reported";
  category: string | null;
  reaction: string | null;
  reply: string | null;
  reply_at: string | null;
  report_reason: string | null;
  created_at: string;
}

const REACTIONS = ["❤️", "😂", "😮", "👍", "🔥"];
const TABS: { key: Msg["status"]; label: string }[] = [
  { key: "active", label: "Inbox" },
  { key: "archived", label: "Archived" },
  { key: "reported", label: "Reported" },
];
const authorizationHeaders = (accessToken: string, headers: Record<string, string> = {}) => ({
  ...headers,
  Authorization: `Bearer ${accessToken}`,
});

/** Load an owner's inbox and provide controls for its messages and settings. */
export default function Dashboard({
  userId,
  accessToken,
  onLogout,
}: {
  userId: string;
  accessToken: string;
  onLogout: () => void;
}) {
  const [username, setUsername] = useState("");
  const [acceptingMessages, setAcceptingMessages] = useState(true);
  const [tab, setTab] = useState<Msg["status"]>("active");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [copiedInvite, setCopiedInvite] = useState(false);
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [replyDraftId, setReplyDraftId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState("");
  const [reportDraftId, setReportDraftId] = useState<number | null>(null);
  const [reportReason, setReportReason] = useState("");
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [suggestingId, setSuggestingId] = useState<number | null>(null);
  const [suggestError, setSuggestError] = useState("");
  const [reactingId, setReactingId] = useState<number | null>(null);
  const [reactionError, setReactionError] = useState("");
  const [deleteAccountError, setDeleteAccountError] = useState("");
  const [deletingAccount, setDeletingAccount] = useState(false);
  const inviteUrl = inviteToken ? `${window.location.origin}/?route=feedback&invite=${encodeURIComponent(inviteToken)}` : "";

  useEffect(() => {
    // Load the owner's display name and persisted inbox setting for this session.
    fetch(`${USER_API}/users/${userId}`, { headers: authorizationHeaders(accessToken) })
      .then((r) => r.json())
      .then((data) => {
        setUsername(data.username);
        setAcceptingMessages(data.accepting_messages);
      });
  }, [userId, accessToken]);

  useEffect(() => {
    fetch(`${MESSAGE_API}/invites/${userId}`, { headers: authorizationHeaders(accessToken) })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load your shared invite.");
        if (data.invite_token) setInviteToken(data.invite_token);
      })
      .catch((err) => {
        setInviteError(err instanceof Error ? err.message : "Could not load your shared invite.");
      });
  }, [userId, accessToken]);

  useEffect(() => {
    // Refresh the current tab so new feedback appears without a manual reload.
    const fetchMessages = () => {
      fetch(`${MESSAGE_API}/messages/${userId}?status=${tab}`, {
        headers: authorizationHeaders(accessToken),
      })
        .then((r) => r.json())
        .then((data) => setMessages(data))
        .catch((err) => console.error("Error background fetching inbox:", err));
    };

    fetchMessages();

    // Clean up the interval when the owner switches tabs or leaves the dashboard.
    const intervalId = setInterval(fetchMessages, 3000);
    return () => clearInterval(intervalId);
  }, [userId, tab, accessToken]);

  const handleCopyInvite = async (inviteUrl: string) => {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopiedInvite(true);
      setTimeout(() => setCopiedInvite(false), 2000);
    } catch (err) {
      console.error("Failed to copy invite link:", err);
    }
  };

  const handleCreateInvite = async () => {
    setCreatingInvite(true);
    setInviteError("");
    setCopiedInvite(false);
    try {
      const response = await fetch(`${MESSAGE_API}/invites/${userId}`, {
        method: "POST",
        headers: authorizationHeaders(accessToken),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create an invite.");
      if (!data.invite_token) {
        throw new Error("The service did not return the shared invite token.");
      }
      setInviteToken(data.invite_token);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Could not connect to the service. Please try again.");
    } finally {
      setCreatingInvite(false);
    }
  };

  const handleToggleAccepting = async () => {
    const next = !acceptingMessages;
    setAcceptingMessages(next);
    try {
      await fetch(`${USER_API}/users/${userId}/settings`, {
        method: "PATCH",
        headers: authorizationHeaders(accessToken, { "Content-Type": "application/json" }),
        body: JSON.stringify({ accepting_messages: next }),
      });
    } catch (err) {
      console.error("Failed to update inbox settings:", err);
      setAcceptingMessages(!next);
    }
  };

  const handleDeleteAccount = async () => {
    if (!window.confirm("Permanently delete your account, all messages, and invite links? This cannot be undone.")) return;
    setDeletingAccount(true);
    setDeleteAccountError("");
    try {
      const response = await fetch(`${USER_API}/users/${userId}`, {
        method: "DELETE",
        headers: authorizationHeaders(accessToken),
      });
      const data = response.status === 204 ? {} : await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not delete your account.");
      onLogout();
    } catch (err) {
      setDeleteAccountError(err instanceof Error ? err.message : "Could not delete your account. Please try again.");
    } finally {
      setDeletingAccount(false);
    }
  };

  const removeFromView = (id: number) => setMessages((prev) => prev.filter((m) => m.id !== id));

  const handleArchive = async (id: number) => {
    await fetch(`${MESSAGE_API}/messages/${id}/archive`, {
      method: "PATCH",
      headers: authorizationHeaders(accessToken),
    });
    removeFromView(id);
  };

  const handleRestore = async (id: number) => {
    await fetch(`${MESSAGE_API}/messages/${id}/restore`, {
      method: "PATCH",
      headers: authorizationHeaders(accessToken),
    });
    removeFromView(id);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Permanently delete this message?")) return;
    await fetch(`${MESSAGE_API}/messages/${id}`, {
      method: "DELETE",
      headers: authorizationHeaders(accessToken),
    });
    removeFromView(id);
  };

  const handleReact = async (id: number, reaction: string) => {
    const previousReaction = messages.find((m) => m.id === id)?.reaction ?? null;
    setReactionError("");
    setReactingId(id);
    // Reflect the click immediately; restore the saved value if persistence fails.
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, reaction } : m)));

    try {
      const res = await fetch(`${MESSAGE_API}/messages/${id}/reaction`, {
        method: "PATCH",
        headers: authorizationHeaders(accessToken, { "Content-Type": "application/json" }),
        body: JSON.stringify({ reaction }),
        signal: AbortSignal.timeout(8000),
      });
      const updated = await res.json();
      if (!res.ok) throw new Error(updated.detail || "Could not save your reaction.");
      setMessages((prev) => prev.map((m) => (m.id === id ? updated : m)));
    } catch (err) {
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, reaction: previousReaction } : m)));
      setReactionError(
        err instanceof DOMException && err.name === "TimeoutError"
          ? "Saving your reaction took too long. Please try again."
          : err instanceof Error
            ? err.message
            : "Could not connect to save your reaction.",
      );
    } finally {
      setReactingId(null);
    }
  };

  const submitReply = async (id: number) => {
    if (!replyText.trim()) return;
    const res = await fetch(`${MESSAGE_API}/messages/${id}/reply`, {
      method: "PATCH",
      headers: authorizationHeaders(accessToken, { "Content-Type": "application/json" }),
      body: JSON.stringify({ reply: replyText }),
    });
    const updated = await res.json();
    setMessages((prev) => prev.map((m) => (m.id === id ? updated : m)));
    setReplyDraftId(null);
    setReplyText("");
  };

  const handleSummarize = async () => {
    setSummarizing(true);
    setSummaryError("");
    setSummary(null);
    try {
      const res = await fetch(`${MESSAGE_API}/messages/${userId}/summarize`, {
        method: "POST",
        headers: authorizationHeaders(accessToken),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not summarize inbox.");
      setSummary(data.summary);
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : "Could not summarize inbox.");
    } finally {
      setSummarizing(false);
    }
  };

  const handleSuggestReply = async (id: number) => {
    setSuggestingId(id);
    setSuggestError("");
    try {
      const res = await fetch(`${MESSAGE_API}/messages/${id}/suggest-reply`, {
        method: "POST",
        headers: authorizationHeaders(accessToken),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not suggest a reply.");
      setReplyDraftId(id);
      setReplyText(data.suggestion);
    } catch (err) {
      setSuggestError(err instanceof Error ? err.message : "Could not suggest a reply.");
    } finally {
      setSuggestingId(null);
    }
  };

  const submitReport = async (id: number) => {
    const res = await fetch(`${MESSAGE_API}/messages/${id}/report`, {
      method: "PATCH",
      headers: authorizationHeaders(accessToken, { "Content-Type": "application/json" }),
      body: JSON.stringify({ reason: reportReason }),
    });
    await res.json();
    setReportDraftId(null);
    setReportReason("");
    removeFromView(id);
  };

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <div className="mb-8 flex items-center justify-between">
        <a href="/" className="flex items-center gap-3 text-ink-50 no-underline">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-gold-500/25 bg-gold-500/10 text-lg text-gold-300">✳</span>
          <span className="font-display text-lg font-semibold tracking-tight">Secret Inbox</span>
        </a>
        <button onClick={onLogout} className="rounded-lg px-3 py-2 text-sm font-medium text-ink-400 transition hover:bg-ink-850 hover:text-ink-100">Log out</button>
      </div>

      <section className="relative mb-5 overflow-hidden rounded-3xl border border-ink-700/80 bg-gradient-to-br from-ink-900 to-ink-850 p-6 shadow-2xl shadow-black/20 sm:p-8">
        <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-gold-500/10 blur-3xl" />
        <div className="relative">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold-400">Your space</p>
              <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-50 sm:text-4xl">Welcome, {username || "friend"}</h1>
              <p className="mt-2 text-sm text-ink-400">A little curiosity looks good on you.</p>
            </div>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-300">
              Private inbox
            </span>
          </div>
          <div className="rounded-2xl border border-ink-700/80 bg-ink-950/40 p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-400">Shared invite link</p>
            <p className="mb-3 mt-1 text-sm text-ink-300">
              Create one link and share it with everyone you want to hear from. Generating a new link invalidates the previous one.
            </p>
            {inviteError && <p role="alert" className="mb-3 text-sm text-rose-300">{inviteError}</p>}
            <button
              onClick={handleCreateInvite}
              disabled={creatingInvite}
              className="rounded-xl border border-gold-500/30 bg-gold-500 px-4 py-3 text-sm font-semibold text-ink-950 transition hover:bg-gold-400 disabled:cursor-wait disabled:opacity-70"
            >
              {creatingInvite ? "Creating invite…" : "Generate invite link"}
            </button>
            {inviteUrl && (
              <div className="mt-4 rounded-xl border border-ink-700 bg-ink-900/70 p-3" aria-label="Shared invite link">
                <input
                  readOnly
                  aria-label="Shared invite link"
                  value={inviteUrl}
                  className="mb-2 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-xs text-gold-300 font-mono"
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleCopyInvite(inviteUrl)}
                    className="rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-xs font-semibold text-ink-100 hover:bg-ink-700"
                  >
                    {copiedInvite ? "Copied!" : "Copy link"}
                  </button>
                  <a
                    href={`https://outlook.office.com/mail/deeplink/compose?subject=${encodeURIComponent("Could you share some honest feedback?")}&body=${encodeURIComponent(`Hi there,\n\nI'm collecting honest feedback and would really value your thoughts. If you have a moment, you can share them using this link:\n\n${inviteUrl}\n\nThe form doesn't ask for your name, so you can be completely anonymous.\n\nThanks for taking the time!\n${username || "A friend"}`)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-lg border border-gold-500/30 bg-gold-500 px-3 py-2 text-xs font-semibold text-ink-950 hover:bg-gold-400"
                  >
                    Email with Outlook
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="mb-8 flex items-center justify-between gap-4 rounded-2xl border border-ink-700/80 bg-ink-900/75 px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-ink-100">{acceptingMessages ? "Your inbox is open" : "Your inbox is paused"}</p>
          <p className="mt-1 text-xs text-ink-400">{acceptingMessages ? "Friends can send you anonymous notes." : "New notes are temporarily turned off."}</p>
        </div>
        <button
          onClick={handleToggleAccepting}
          type="button"
          role="switch"
          aria-checked={acceptingMessages}
          aria-label="Accept new messages"
          className={`relative h-7 w-12 shrink-0 rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950 ${acceptingMessages ? "bg-gold-500" : "bg-ink-600"}`}
        >
          <span
            className={`absolute left-1 top-1 h-5 w-5 rounded-full bg-ink-950 shadow transition-transform ${
              acceptingMessages ? "translate-x-5" : ""
            }`}
          />
        </button>
      </section>

      <section aria-label="Messages">
      <div className="mb-5 flex gap-1 rounded-xl border border-ink-800 bg-ink-900/60 p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined}
            className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 ${
              tab === t.key ? "bg-ink-700 text-gold-300 shadow-sm" : "text-ink-400 hover:bg-ink-850 hover:text-ink-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">Your messages</p>
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink-50">{TABS.find((t) => t.key === tab)?.label} <span className="font-sans text-sm font-medium text-ink-500">({messages.length})</span></h2>
        </div>
        {tab === "active" && (
          <button
            onClick={handleSummarize}
            disabled={summarizing || messages.length === 0}
            className="rounded-xl border border-gold-500/25 bg-gold-500/10 px-3 py-2 text-xs font-semibold text-gold-300 transition hover:bg-gold-500/15 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {summarizing ? "✨ Thinking..." : "✨ Summarize Inbox"}
          </button>
        )}
      </div>

      {summaryError && (
        <p className="text-sm text-rose-400 mb-3 font-medium bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">⚠️ {summaryError}</p>
      )}
      {summary && (
        <div className="p-4 mb-4 bg-gold-500/5 border border-gold-500/30 rounded-xl relative">
          <span className="text-[10px] font-semibold text-gold-400 uppercase tracking-wider">✨ Inbox Summary</span>
          <p className="text-sm text-ink-100 mt-1 leading-relaxed pr-5">{summary}</p>
          <button onClick={() => setSummary(null)} className="absolute top-3 right-3 text-xs text-ink-400 hover:text-ink-100">✕</button>
        </div>
      )}
      {suggestError && (
        <p className="text-sm text-rose-400 mb-3 font-medium bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">⚠️ {suggestError}</p>
      )}
      {reactionError && (
        <p role="alert" className="mb-3 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-300">{reactionError}</p>
      )}

      <div className="space-y-3">
        {messages.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-700 bg-ink-900/40 px-6 py-12 text-center">
            <span aria-hidden="true" className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-850 text-xl text-gold-300">✳</span>
            <h3 className="font-medium text-ink-100">{tab === "active" ? "Your inbox is waiting" : `Nothing ${tab} here`}</h3>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-ink-400">
              {tab === "active" ? "Create a shared invite and send it to anyone you want to hear from." : `Messages you ${tab} will show up here.`}
            </p>
          </div>
        ) : (
          messages.map((m) => (
            <article key={m.id} className="rounded-2xl border border-ink-700/80 bg-ink-900/75 p-5 transition hover:border-ink-600">
              {m.category && (
                <span className="mb-3 inline-block rounded-full border border-ink-600/60 bg-ink-800 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-ink-300">
                  {m.category}
                </span>
              )}
              <p className="text-[15px] leading-7 text-ink-100">{m.content}</p>
              <span className="mt-3 block text-xs text-ink-500">
                {new Date(m.created_at).toLocaleString()}
              </span>

              {m.reply && (
                <div className="mt-4 rounded-xl border border-gold-500/20 bg-gold-500/5 p-4">
                  <span className="text-[10px] font-semibold text-gold-400 uppercase tracking-wider">Your reply</span>
                  <p className="text-sm text-ink-100 mt-1">{m.reply}</p>
                </div>
              )}

              <div className="flex items-center gap-1 mt-3">
                {REACTIONS.map((r) => (
                  <button
                    key={r}
                    onClick={() => handleReact(m.id, r)}
                    type="button"
                    aria-label={`React with ${r}`}
                    aria-pressed={m.reaction === r}
                    disabled={reactingId !== null}
                    className={`rounded-lg px-2 py-1.5 text-base transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 disabled:cursor-wait disabled:opacity-60 ${
                      m.reaction === r ? "bg-gold-500/15 ring-1 ring-gold-500/40" : "hover:bg-ink-800"
                    }`}
                  >
                    {r}
                  </button>
                ))}
                {reactingId === m.id && <span role="status" className="ml-2 text-xs text-ink-400">Saving reaction…</span>}
              </div>

              {replyDraftId === m.id ? (
                <div className="mt-3 space-y-2">
                  <textarea
                    rows={2}
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="Write a reply..."
                    className="w-full p-2 text-sm bg-ink-900 border border-ink-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-gold-500/50 focus:border-gold-500/50 transition text-ink-50 placeholder:text-ink-400"
                  />
                  <div className="flex gap-2">
                    <button onClick={() => submitReply(m.id)} className="rounded-lg bg-gold-500 px-3 py-2 text-xs font-semibold text-ink-950 transition hover:bg-gold-400">Send reply</button>
                    <button onClick={() => { setReplyDraftId(null); setReplyText(""); }} className="rounded-lg px-3 py-2 text-xs font-medium text-ink-400 transition hover:text-ink-100">Cancel</button>
                  </div>
                </div>
              ) : reportDraftId === m.id ? (
                <div className="mt-3 space-y-2">
                  <input
                    value={reportReason}
                    onChange={(e) => setReportReason(e.target.value)}
                    placeholder="Reason for reporting (optional)"
                    className="w-full p-2 text-sm bg-ink-900 border border-ink-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-gold-500/50 focus:border-gold-500/50 transition text-ink-50 placeholder:text-ink-400"
                  />
                  <div className="flex gap-2">
                    <button onClick={() => submitReport(m.id)} className="rounded-lg bg-rose-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-rose-600">Confirm report</button>
                    <button onClick={() => { setReportDraftId(null); setReportReason(""); }} className="rounded-lg px-3 py-2 text-xs font-medium text-ink-400 transition hover:text-ink-100">Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-ink-700/70 pt-3 text-xs font-semibold">
                  {!m.reply && tab === "active" && (
                    <>
                      <button onClick={() => { setReplyDraftId(m.id); setReplyText(""); }} className="text-ink-300 hover:text-ink-50 transition">💬 Reply</button>
                      <button
                        onClick={() => handleSuggestReply(m.id)}
                        disabled={suggestingId === m.id}
                        className="text-gold-400 hover:text-gold-300 transition disabled:opacity-40"
                      >
                        {suggestingId === m.id ? "✨ Thinking..." : "✨ Suggest Reply"}
                      </button>
                    </>
                  )}
                  {tab === "archived" && (
                    <button onClick={() => handleRestore(m.id)} className="text-ink-300 hover:text-ink-50 transition">↩️ Move to Inbox</button>
                  )}
                  {tab !== "archived" && (
                    <button onClick={() => handleArchive(m.id)} className="text-ink-300 hover:text-ink-50 transition">🗄️ Archive</button>
                  )}
                  {tab !== "reported" && (
                    <button onClick={() => { setReportDraftId(m.id); setReportReason(""); }} className="text-amber-400 hover:text-amber-300 transition">🚩 Report</button>
                  )}
                  <button onClick={() => handleDelete(m.id)} className="text-rose-400 hover:text-rose-300 transition">🗑️ Delete</button>
                </div>
              )}
            </article>
          ))
        )}
      </div>
      </section>
      <section aria-label="Danger zone" className="mt-8 rounded-2xl border border-rose-500/25 bg-rose-500/5 p-5">
        <h2 className="text-sm font-semibold text-rose-300">Delete account</h2>
        <p className="mt-1 text-xs leading-5 text-ink-400">
          Permanently remove your account, all inbox messages, and shared invite links.
        </p>
        {deleteAccountError && <p role="alert" className="mt-3 text-sm text-rose-300">{deleteAccountError}</p>}
        <button
          type="button"
          onClick={handleDeleteAccount}
          disabled={deletingAccount}
          className="mt-4 rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-300 transition hover:bg-rose-500/20 disabled:cursor-wait disabled:opacity-60"
        >
          {deletingAccount ? "Deleting account…" : "Delete my account"}
        </button>
      </section>
    </main>
  );
}
