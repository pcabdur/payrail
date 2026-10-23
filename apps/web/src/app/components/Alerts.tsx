'use client';

type AlertsProps = {
  error: string;
  notice: string;
  onClearError: () => void;
  onClearNotice: () => void;
};

export function Alerts({
  error,
  notice,
  onClearError,
  onClearNotice,
}: AlertsProps) {
  return (
    <>
      {error && (
        <div
          role="alert"
          className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-red-400/20 bg-red-400/[0.07] p-4 text-sm text-red-200"
        >
          <span>{error}</span>
          <button
            onClick={onClearError}
            aria-label="Dismiss error"
            className="text-base leading-none text-red-300 hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {notice && (
        <div
          role="status"
          className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.07] p-4 text-sm text-emerald-200"
        >
          <span>{notice}</span>
          <button
            onClick={onClearNotice}
            aria-label="Dismiss message"
            className="text-base leading-none text-emerald-300 hover:text-white"
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}
