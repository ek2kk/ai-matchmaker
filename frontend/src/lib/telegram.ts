type TelegramBackButton = {
  isVisible: boolean;
  show(): void;
  hide(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
};

type TelegramWebApp = {
  initData: string;
  themeParams: Record<string, string | undefined>;
  BackButton: TelegramBackButton;
  ready(): void;
  expand(): void;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

function webApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function isTelegramMiniApp(): boolean {
  return webApp() !== null;
}

export function telegramInitData(): string {
  return webApp()?.initData ?? "";
}

export function initializeTelegram(): void {
  const app = webApp();
  if (!app) return;
  const { bg_color, text_color } = app.themeParams;
  if (bg_color) document.documentElement.style.setProperty("--app-background", bg_color);
  if (text_color) document.documentElement.style.setProperty("--app-foreground", text_color);
  app.ready();
  app.expand();
}

export function setTelegramBackButton(onClick: (() => void) | null): () => void {
  const button = webApp()?.BackButton;
  if (!button || !onClick) return () => undefined;
  button.onClick(onClick);
  button.show();
  return () => {
    button.offClick(onClick);
    button.hide();
  };
}
