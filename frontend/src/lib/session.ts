const KEY = "ai-matchmaker.session";

type StoredSession = {
  token: string;
  accountId: string;
  expiresAt?: string;
};

function readStore(store: Storage): StoredSession | null {
  const raw = store.getItem(KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      typeof (parsed as StoredSession).token !== "string" ||
      typeof (parsed as StoredSession).accountId !== "string"
    ) {
      store.removeItem(KEY);
      return null;
    }
    const session = parsed as StoredSession;
    if (session.expiresAt && Date.parse(session.expiresAt) <= Date.now()) {
      store.removeItem(KEY);
      return null;
    }
    return session;
  } catch {
    store.removeItem(KEY);
    return null;
  }
}

function loadStored(): StoredSession | null {
  try {
    return readStore(localStorage) ?? readStore(sessionStorage);
  } catch {
    return null;
  }
}

const initial = loadStored();
let token: string | null = initial?.token ?? null;
let accountId: string | null = initial?.accountId ?? null;

export function getSessionToken(): string | null {
  return token;
}

export function getAccountId(): string | null {
  return accountId;
}

export function setSession(next: StoredSession | null, persist = true): void {
  if (!next) {
    token = null;
    accountId = null;
    try {
      localStorage.removeItem(KEY);
      sessionStorage.removeItem(KEY);
    } catch {
      return;
    }
    return;
  }
  token = next.token;
  accountId = next.accountId;
  const raw = JSON.stringify({
    token: next.token,
    accountId: next.accountId,
    expiresAt: next.expiresAt,
  });
  try {
    const write = persist ? localStorage : sessionStorage;
    const clear = persist ? sessionStorage : localStorage;
    write.setItem(KEY, raw);
    clear.removeItem(KEY);
  } catch {
    return;
  }
}
