import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type ConversationSummary, type MessageView } from "@/lib/api";
import { ApiError } from "@/lib/http";
import { getAccountId, setSession } from "@/lib/session";

const REPORT_REASONS = [
  { code: "harassment", label: "Harassment" },
  { code: "spam", label: "Spam" },
  { code: "fake_profile", label: "Fake profile" },
  { code: "underage", label: "Underage" },
  { code: "other", label: "Other" },
];

async function findConversation(conversationId: string): Promise<ConversationSummary | null> {
  let after: string | null = null;
  for (;;) {
    const listed = await api.listConversations(after);
    const found = listed.items.find((row) => row.conversation_id === conversationId);
    if (found) {
      return found;
    }
    if (!listed.next_cursor) {
      return null;
    }
    after = listed.next_cursor;
  }
}

async function loadHistory(conversationId: string): Promise<MessageView[]> {
  const items: MessageView[] = [];
  let after: string | null = null;
  for (;;) {
    const page = await api.listMessages(conversationId, after);
    items.push(...page.items);
    if (!page.next_cursor) {
      return items;
    }
    after = page.next_cursor;
  }
}

export function ConversationPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const accountId = getAccountId();
  const [conversation, setConversation] = useState<ConversationSummary | null>(null);
  const [allowed, setAllowed] = useState<MessageView[]>([]);
  const [pending, setPending] = useState<MessageView[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const lastRead = useRef<string | null>(null);

  const load = useCallback(() => {
    if (!conversationId) {
      return;
    }
    Promise.all([findConversation(conversationId), loadHistory(conversationId)])
      .then(([found, history]) => {
        if (!found) {
          setUnavailable(true);
          return;
        }
        setConversation(found);
        setAllowed(history);
        setUnavailable(false);
        setError(null);
        setPending((current) =>
          current.filter((row) => !history.some((item) => item.message_id === row.message_id)),
        );
        const last = history.at(-1);
        if (last && last.message_id !== lastRead.current) {
          lastRead.current = last.message_id;
          api.markConversationRead(conversationId, last.message_id).catch(() => undefined);
        }
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setUnavailable(true);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load conversation.");
      });
  }, [conversationId, navigate]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!conversationId || pending.length === 0) {
      return;
    }
    pending.forEach((row) => {
      api
        .getMessage(conversationId, row.message_id)
        .then((fresh) => {
          if (fresh.moderation_state === "rejected") {
            setPending((current) =>
              current.map((item) => (item.message_id === fresh.message_id ? fresh : item)),
            );
          }
        })
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) {
            setUnavailable(true);
          }
        });
    });
  }, [allowed, conversationId, pending]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!conversationId || !draft.trim() || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    api
      .sendMessage(conversationId, {
        client_message_id: crypto.randomUUID(),
        body: draft.trim(),
      })
      .then((row) => {
        setPending((current) => [...current, row]);
        setDraft("");
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setUnavailable(true);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not send.");
      })
      .finally(() => setBusy(false));
  }

  const pendingVisible = pending.filter(
    (row) => !allowed.some((item) => item.message_id === row.message_id),
  );
  const thread = [...allowed, ...pendingVisible];

  if (unavailable) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-4 p-6 py-10">
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm">This conversation is unavailable.</p>
        <Link to="/matches" className="text-sm text-slate-600">
          Back to matches
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-6 p-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {conversation ? `${conversation.counterpart.display_name}, ${conversation.counterpart.age}` : "Conversation"}
        </h1>
        <p className="text-sm text-slate-600">Messages stay private until they are allowed.</p>
      </div>
      {error ? (
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {thread.map((row) => {
          const mine = row.sender_account_id === accountId;
          const rejected = row.moderation_state === "rejected";
          const held = row.moderation_state === "held";
          return (
            <li
              key={row.message_id}
              className={`rounded-lg p-3 text-sm shadow-sm ${mine ? "bg-emerald-50" : "bg-white"}`}
            >
              <p>{rejected ? "This message is unavailable." : (row.body ?? "")}</p>
              {held ? <p className="mt-1 text-xs text-slate-600">Pending review</p> : null}
            </li>
          );
        })}
      </ul>
      <form className="flex flex-col gap-2" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm">
          Message
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={4000}
            rows={3}
            className="rounded-md border border-slate-300 px-3 py-2"
            required
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
      {conversation ? (
        <div className="flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            className="rounded-md border border-slate-300 px-3 py-1.5"
            onClick={() => {
              api
                .unmatch(conversation.match_id)
                .then(() => navigate("/matches"))
                .catch((err: unknown) => {
                  setError(err instanceof ApiError ? err.message : "Could not unmatch.");
                });
            }}
          >
            Unmatch
          </button>
          <button
            type="button"
            className="rounded-md border border-slate-300 px-3 py-1.5"
            onClick={() => {
              api
                .postBlock({ profile_id: conversation.counterpart.profile_id })
                .then(() => navigate("/matches"))
                .catch((err: unknown) => {
                  setError(err instanceof ApiError ? err.message : "Could not block.");
                });
            }}
          >
            Block
          </button>
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              const reason = new FormData(event.currentTarget).get("reason_code");
              if (typeof reason !== "string") {
                return;
              }
              api
                .postReport({
                  profile_id: conversation.counterpart.profile_id,
                  reason_code: reason,
                })
                .then(() => navigate("/matches"))
                .catch((err: unknown) => {
                  setError(err instanceof ApiError ? err.message : "Could not report.");
                });
            }}
          >
            <label className="sr-only" htmlFor="report-reason">
              Report reason
            </label>
            <select
              id="report-reason"
              name="reason_code"
              className="rounded-md border border-slate-300 px-2 py-1.5"
              defaultValue="other"
            >
              {REPORT_REASONS.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.label}
                </option>
              ))}
            </select>
            <button type="submit" className="rounded-md border border-red-300 px-3 py-1.5 text-red-800">
              Report
            </button>
          </form>
        </div>
      ) : null}
      <Link to="/matches" className="text-sm text-slate-600">
        Back to matches
      </Link>
    </main>
  );
}
