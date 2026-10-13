import { useEffect, useState } from "react";

interface SentMessage {
  content: string;
  category: string | null;
  reply: string | null;
  reply_at: string | null;
  reaction: string | null;
  created_at: string;
}

/** Show a sender their message and poll for a reaction or written reply. */
export default function CheckReply({ token }: { token: string }) {
  const [message, setMessage] = useState<SentMessage | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [copied, setCopied] = useState(false);
  const checkUrl = `${window.location.origin}/?route=check&token=${encodeURIComponent(token)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(checkUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy private reply-check link:", err);
    }
  };

  useEffect(() => {
    const fetchMessage = () => {
      fetch(`http://localhost:8002/messages/token/${token}`)
        .then((r) => {
          if (!r.ok) throw new Error("not found");
          return r.json();
        })
        .then((data) => setMessage(data))
        .catch(() => setNotFound(true));
    };

    fetchMessage();
    const intervalId = setInterval(fetchMessage, 5000);
    // Do not keep polling after leaving this private-link page.
    return () => clearInterval(intervalId);
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-lg rounded-3xl border border-ink-700/80 bg-ink-900/90 p-6 shadow-2xl shadow-black/40 backdrop-blur sm:p-8">
        <a href="/" className="mb-8 inline-flex items-center gap-2.5 text-sm font-semibold text-ink-300 no-underline transition hover:text-ink-50">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-gold-500/25 bg-gold-500/10 text-gold-300">✳</span>
          Secret Inbox
        </a>
        <div className="mb-6">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold-400">Your private link</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-50">A note you sent.</h1>
          <p className="mt-2 text-sm leading-6 text-ink-400">We'll check for a reply or reaction automatically while this page is open.</p>
        </div>

        {notFound ? (
          <div role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm leading-6 text-rose-300">This link is no longer valid — the message may have been deleted.</div>
        ) : !message ? (
          <div role="status" className="rounded-2xl border border-ink-700 bg-ink-850 p-5 text-sm text-ink-400">
            <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-gold-400" />
            Looking for your message…
          </div>
        ) : (
          <div className="space-y-4">
            <article className="rounded-2xl border border-ink-700/80 bg-ink-850 p-5">
              {message.category && (
                <span className="mb-3 inline-block rounded-full border border-ink-600/60 bg-ink-800 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-ink-300">
                  {message.category}
                </span>
              )}
              <p className="text-[15px] leading-7 text-ink-100">{message.content}</p>
              <span className="mt-3 block text-xs text-ink-500">
                {new Date(message.created_at).toLocaleString()}
              </span>
            </article>

            {message.reaction && (
              <div role="status" className="rounded-2xl border border-gold-500/25 bg-gold-500/5 p-5">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-gold-400">A little acknowledgment</span>
                <p className="mt-2 text-[15px] leading-7 text-ink-100">
                  They reacted <span className="text-xl" aria-label={message.reaction}>{message.reaction}</span> to your message.
                </p>
              </div>
            )}

            {message.reply ? (
              <div className="rounded-2xl border border-gold-500/25 bg-gold-500/5 p-5">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-gold-400">Their reply</span>
                <p className="mt-2 text-[15px] leading-7 text-ink-100">{message.reply}</p>
              </div>
            ) : (
              <div role="status" className="rounded-2xl border border-ink-700/80 bg-ink-900/60 p-5">
                <span className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gold-400" />
                  Waiting for a written reply
                </span>
                <p className="text-sm leading-6 text-ink-400">We'll refresh this page automatically. Feel free to leave it open.</p>
              </div>
            )}
          </div>
        )}
        <div className="mt-5 border-t border-ink-700 pt-5">
          <p className="mb-2 text-xs leading-5 text-ink-400">Save this private link to check back later.</p>
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
      </section>
    </main>
  );
}
