type Props = {
  onReload: () => void;
};

export function VersionConflictDialog({ onReload }: Props) {
  return (
    <div
      role="alertdialog"
      aria-labelledby="version-conflict-title"
      className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
    >
      <h2 id="version-conflict-title" className="font-medium">
        This draft changed in another session
      </h2>
      <p className="mt-1">Reload the server version. Unsaved edits on this step will be discarded.</p>
      <button
        type="button"
        onClick={onReload}
        className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-white"
      >
        Reload server version
      </button>
    </div>
  );
}
