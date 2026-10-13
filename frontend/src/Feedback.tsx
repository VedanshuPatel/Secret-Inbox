import { useState } from "react";

const CATEGORIES = ["Compliment", "Honest Opinion", "Roast Me", "Advice", "Anything"];

/** Submit an anonymous note through a shared invite and retain its follow-up link. */
export default function Feedback({ inviteToken }: { inviteToken: string | null }) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const [replyToken, setReplyToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const handlePost = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSending(true);
    try {
      if (!inviteToken) throw new Error("This invite link is missing or invalid.");
      const res = await fetch(`http://localhost:8002/messages/invite/${encodeURIComponent(inviteToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, category }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not deliver message.");
      setReplyToken(data.reply_token);
      setComplete(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect to the service. Please try again.");
    } finally {
      setIsSending(false);
    }
  };

  // This unguessable token is the sender's only way to revisit their message.
  const checkUrl = replyToken ? `${window.location.origin}/?route=check&token=${replyToken}` : "";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(checkUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-lg rounded-3xl border border-ink-700/80 bg-ink-900/90 p-6 shadow-2xl shadow-black/40 backdrop-blur sm:p-8">
        <a href="/" className="mb-8 inline-flex items-center gap-2.5 text-sm font-semibold text-ink-300 no-underline transition hover:text-ink-50">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-gold-500/25 bg-gold-500/10 text-gold-300">✳</span>
          Secret Inbox
        </a>
        <div className="mb-6">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold-400">A note, just for them</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-50">Send a little honesty.</h1>
          <p className="mt-2 text-sm leading-6 text-ink-400">Your message is anonymous. The recipient won't see who sent it.</p>
        </div>

        {error && (
          <p role="alert" className="mb-4 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
            {error}
          </p>
        )}
        {!inviteToken ? (
          <p role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-3 text-sm text-rose-300">
            This invite link is missing or invalid. Ask the inbox owner for a fresh link.
          </p>
        ) : complete ? (
          <div className="text-center py-4">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-400/25 bg-emerald-400/10 text-xl text-emerald-300">
              ✓
            </div>
            <h2 className="font-display text-2xl font-semibold text-ink-50">Your note is on its way.</h2>
            <p className="mb-6 mt-2 text-sm leading-6 text-ink-400">
              You can check for a reply now or save the private link to come back later.
            </p>
            <a
              href={checkUrl}
              className="mb-4 inline-flex w-full items-center justify-center rounded-xl bg-gold-500 px-4 py-3.5 font-semibold text-ink-950 transition hover:bg-gold-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900"
            >
              Check for a reply
            </a>
            <div className="flex flex-col gap-2 text-left sm:flex-row">
              <input
                readOnly
                value={checkUrl}
                aria-label="Private reply-check link"
                className="min-w-0 flex-1 rounded-xl border border-ink-700 bg-ink-850 px-3 py-3 text-xs text-gold-300 selection:bg-gold-500/30 font-mono focus:outline-none focus:ring-2 focus:ring-gold-500/30"
              />
              <button
                onClick={handleCopy}
                type="button"
                className={`shrink-0 rounded-xl border px-4 py-3 text-sm font-semibold transition ${
                  copied
                    ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                    : "border-gold-500/30 bg-gold-500 text-ink-950 hover:bg-gold-400"
                }`}
              >
                {copied ? "Copied!" : "Copy link"}
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handlePost} className="space-y-5">
            <fieldset>
              <legend className="mb-2.5 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">Pick a mood <span className="font-normal normal-case tracking-normal">(optional)</span></legend>
              <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  aria-pressed={category === c}
                  onClick={() => setCategory(category === c ? null : c)}
                  className={`rounded-full border px-3.5 py-2 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 ${
                    category === c
                      ? "border-gold-500 bg-gold-500 text-ink-950"
                      : "border-ink-700 bg-ink-850 text-ink-300 hover:border-ink-500"
                  }`}
                >
                  {c}
                </button>
              ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor="feedback-message" className="mb-2.5 block text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">Your message</label>
              <textarea
                id="feedback-message"
                required
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type your honest message here..."
                className="w-full resize-y rounded-xl border border-ink-700 bg-ink-850 px-4 py-3.5 text-sm leading-6 text-ink-50 placeholder:text-ink-500 transition focus:border-gold-500/70 focus:outline-none focus:ring-2 focus:ring-gold-500/20"
              />
            </div>
            <button
              type="submit"
              disabled={isSending}
              className="w-full rounded-xl bg-gold-500 px-4 py-3.5 font-semibold text-ink-950 transition hover:bg-gold-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-300 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900 disabled:cursor-wait disabled:opacity-70"
            >
              {isSending ? "Sending your note…" : "Send anonymously"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
