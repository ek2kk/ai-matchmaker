type Props = {
  onBack?: () => void;
  continueLabel?: string;
  busy?: boolean;
};

export function StepNav({ onBack, continueLabel = "Continue", busy }: Props) {
  return (
    <div className="flex gap-3">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm"
        >
          Back
        </button>
      ) : null}
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? "Saving…" : continueLabel}
      </button>
    </div>
  );
}
