'use client';

type DevelopersTabProps = {
  apiBase: string;
  merchantId: number | null;
  apiKey: string;
  showKey: boolean;
  onToggleShowKey: () => void;
  onCopy: (value: string) => void;
  onClearDemoSession: () => void;
};

export function DevelopersTab({
  apiBase,
  merchantId,
  apiKey,
  showKey,
  onToggleShowKey,
  onCopy,
  onClearDemoSession,
}: DevelopersTabProps) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="rounded-2xl border border-white/[0.08] bg-[#101827] p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
          API configuration
        </p>
        <h2 className="mt-2 text-xl font-semibold">Developer settings</h2>

        <div className="mt-6 space-y-5">
          <div>
            <p className="mb-2 text-xs text-slate-500">API base URL</p>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[#090f1a] p-3">
              <code className="break-all text-sm text-slate-300">
                {apiBase || 'Not configured'}
              </code>
              <button
                disabled={!apiBase}
                onClick={() => onCopy(apiBase)}
                className="shrink-0 text-xs text-blue-300 disabled:opacity-40"
              >
                Copy
              </button>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs text-slate-500">Merchant ID</p>
            <p className="rounded-xl border border-white/[0.07] bg-[#090f1a] p-3 font-mono text-sm">
              {merchantId ?? '—'}
            </p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs text-slate-500">Development API key</p>
              <button
                onClick={onToggleShowKey}
                className="text-xs text-blue-300"
              >
                {showKey ? 'Hide key' : 'Reveal key'}
              </button>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-[#090f1a] p-3">
              <code className="min-w-0 flex-1 break-all text-sm text-slate-300">
                {showKey ? apiKey : `${apiKey.slice(0, 10)}••••••••••••••••`}
              </code>
              <button
                onClick={() => onCopy(apiKey)}
                className="shrink-0 text-xs text-blue-300"
              >
                Copy
              </button>
            </div>
          </div>
        </div>

        <p className="mt-5 text-xs leading-5 text-amber-200/80">
          Demo only: this key is held in sessionStorage. A production merchant
          dashboard should keep privileged credentials on a protected server,
          not in browser storage.
        </p>
      </section>

      <section className="rounded-2xl border border-white/[0.08] bg-[#101827] p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
          Quick start
        </p>
        <h2 className="mt-2 text-xl font-semibold">Create a payment intent</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Payment operations require a merchant Bearer API key and an
          Idempotency-Key header.
        </p>

        <pre className="mt-5 overflow-x-auto rounded-xl border border-white/[0.07] bg-[#090f1a] p-4 text-xs leading-6 text-slate-300">
          <code>{`curl -X POST ${apiBase || '<NEXT_PUBLIC_API_URL>'}/v1/payment_intents \\
  -H "Authorization: Bearer YOUR_TEST_KEY" \\
  -H "Idempotency-Key: YOUR_UNIQUE_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 10000000,
    "currency": "USDC",
    "network": "base-sepolia",
    "recipient": "0xYOUR_40_HEX_ADDRESS",
    "description": "Demo payment"
  }'`}</code>
        </pre>

        <p className="mt-4 text-xs leading-5 text-slate-500">
          Amounts are integer USDC base units: 1 USDC equals 1,000,000 units.
          Replace the example placeholders before running the command.
        </p>

        <button
          onClick={onClearDemoSession}
          className="mt-6 rounded-xl border border-red-400/20 px-4 py-2.5 text-sm text-red-300 hover:bg-red-400/[0.07]"
        >
          Clear browser demo credentials
        </button>
      </section>
    </div>
  );
}
