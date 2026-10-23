'use client';

const STATUS_STYLES: Record<string, string> = {
  succeeded: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/20',
  confirming: 'bg-blue-400/10 text-blue-300 ring-blue-400/20',
  requires_payment: 'bg-amber-400/10 text-amber-300 ring-amber-400/20',
  underpaid: 'bg-orange-400/10 text-orange-300 ring-orange-400/20',
  overpaid: 'bg-orange-400/10 text-orange-300 ring-orange-400/20',
  failed: 'bg-red-400/10 text-red-300 ring-red-400/20',
  reorged: 'bg-red-400/10 text-red-300 ring-red-400/20',
  canceled: 'bg-slate-400/10 text-slate-300 ring-slate-400/20',
  expired: 'bg-slate-400/10 text-slate-300 ring-slate-400/20',
};

export function StatusBadge({ status }: { status: string }) {
  const badgeStyle =
    STATUS_STYLES[status] || 'bg-slate-400/10 text-slate-300 ring-slate-400/20';

  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${badgeStyle}`}
    >
      {status.replaceAll('_', ' ')}
    </span>
  );
}
