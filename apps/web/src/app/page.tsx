'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, '') ?? '';

function getApiBase(): string {
  if (!API_BASE) {
    throw new Error(
      'Set NEXT_PUBLIC_API_URL to the API address for this deployment.',
    );
  }
  let parsed: URL;
  try {
    parsed = new URL(API_BASE);
  } catch {
    throw new Error('NEXT_PUBLIC_API_URL must be a valid URL.');
  }
  const localHost = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (
    process.env.NODE_ENV === 'production' &&
    (localHost || parsed.protocol !== 'https:')
  ) {
    throw new Error(
      'Production NEXT_PUBLIC_API_URL must use a public HTTPS host.',
    );
  }
  return API_BASE;
}

type Merchant = {
  id: number;
  name: string;
  api_key: string;
  created_at: string;
};

type Payment = {
  public_id: string;
  amount: number;
  currency: string;
  network: string;
  recipient: string;
  description: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  transaction_hash: string | null;
};

type Tab = 'overview' | 'payments' | 'create' | 'developers';

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();

  let data: { detail?: string };

  try {
    data = text ? (JSON.parse(text) as { detail?: string }) : {};
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(
      data.detail || `Request failed with HTTP ${response.status}`,
    );
  }

  return data as T;
}

function formatUSDC(amount: number): string {
  return (amount / 1_000_000).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  });
}

function parseUSDC(value: string): number {
  const trimmed = value.trim();

  if (!/^\d+(\.\d{1,6})?$/.test(trimmed)) {
    throw new Error('Enter a positive amount with up to 6 decimal places.');
  }

  const [whole, fraction = ''] = trimmed.split('.');
  const units =
    BigInt(whole) * 1_000_000n + BigInt((fraction + '000000').slice(0, 6));

  if (units <= 0n || units > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error('Enter a valid amount greater than zero.');
  }

  return Number(units);
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString();
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
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

  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${
        styles[status] || 'bg-slate-400/10 text-slate-300 ring-slate-400/20'
      }`}
    >
      {status.replaceAll('_', ' ')}
    </span>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#101827] p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
        {value}
      </p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [apiKey, setApiKey] = useState('');
  const [merchantName, setMerchantName] = useState('');
  const [merchantId, setMerchantId] = useState<number | null>(null);

  const [registrationName, setRegistrationName] = useState('');
  const [amount, setAmount] = useState('10.00');
  const [recipient, setRecipient] = useState('');
  const [description, setDescription] = useState('');

  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [busyPayment, setBusyPayment] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    const savedKey = sessionStorage.getItem('payrail_demo_api_key');
    const savedName = sessionStorage.getItem('payrail_demo_merchant_name');
    const savedId = sessionStorage.getItem('payrail_demo_merchant_id');

    if (savedKey) setApiKey(savedKey);
    if (savedName) setMerchantName(savedName);
    if (savedId && Number.isFinite(Number(savedId))) {
      setMerchantId(Number(savedId));
    }
  }, []);

  const loadPayments = useCallback(async (key: string) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(
        `${getApiBase()}/v1/payment_intents?limit=100&offset=0`,
        {
          headers: { Authorization: `Bearer ${key}` },
          cache: 'no-store',
        },
      );

      const data = await parseResponse<Payment[]>(response);
      setPayments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load payments.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (apiKey) void loadPayments(apiKey);
  }, [apiKey, loadPayments]);

  const succeeded = useMemo(
    () => payments.filter((p) => p.status === 'succeeded'),
    [payments],
  );

  const pending = useMemo(
    () =>
      payments.filter((p) =>
        ['requires_payment', 'confirming'].includes(p.status),
      ),
    [payments],
  );

  const totalVolume = succeeded.reduce((sum, p) => sum + p.amount, 0);

  const filteredPayments = useMemo(() => {
    const term = search.trim().toLowerCase();

    if (!term) return payments;

    return payments.filter((p) =>
      [
        p.public_id,
        p.description || '',
        p.status,
        p.transaction_hash || '',
        p.recipient,
      ].some((value) => value.toLowerCase().includes(term)),
    );
  }, [payments, search]);

  async function registerMerchant(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setSubmitting(true);

    try {
      const response = await fetch(`${getApiBase()}/v1/merchants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: registrationName.trim() }),
      });

      const merchant = await parseResponse<Merchant>(response);

      sessionStorage.setItem('payrail_demo_api_key', merchant.api_key);
      sessionStorage.setItem('payrail_demo_merchant_name', merchant.name);
      sessionStorage.setItem('payrail_demo_merchant_id', String(merchant.id));

      setApiKey(merchant.api_key);
      setMerchantName(merchant.name);
      setMerchantId(merchant.id);
      setNotice(
        'Merchant created. Your development API key is stored for this browser session.',
      );
      setActiveTab('overview');
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Merchant registration failed.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function createPayment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setSubmitting(true);

    try {
      if (!apiKey) throw new Error('Register a merchant first.');

      const units = parseUSDC(amount);
      const cleanRecipient = recipient.trim();

      if (!/^0x[a-fA-F0-9]{40}$/.test(cleanRecipient)) {
        throw new Error('Enter a valid 0x wallet address (42 characters).');
      }

      const response = await fetch(`${getApiBase()}/v1/payment_intents`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify({
          amount: units,
          currency: 'USDC',
          network: 'base-sepolia',
          recipient: cleanRecipient,
          description: description.trim() || null,
          expires_in_seconds: 1800,
        }),
      });

      const payment = await parseResponse<Payment>(response);

      setNotice(`Payment intent ${payment.public_id} created successfully.`);
      setDescription('');
      setActiveTab('payments');
      await loadPayments(apiKey);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not create payment intent.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelPayment(payment: Payment) {
    if (!apiKey) return;

    const confirmed = window.confirm(
      `Cancel payment intent ${payment.public_id}?`,
    );

    if (!confirmed) return;

    setError('');
    setNotice('');
    setBusyPayment(payment.public_id);

    try {
      const response = await fetch(
        `${getApiBase()}/v1/payment_intents/${encodeURIComponent(payment.public_id)}/cancel`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${apiKey}` },
        },
      );

      await parseResponse<Payment>(response);
      setNotice(`Payment intent ${payment.public_id} canceled.`);
      await loadPayments(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancellation failed.');
    } finally {
      setBusyPayment('');
    }
  }

  async function copyValue(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice('Copied to clipboard.');
    } catch {
      setError('Clipboard access failed. Select and copy the value manually.');
    }
  }

  function clearDemoSession() {
    const confirmed = window.confirm(
      'Clear this browser session’s merchant credentials? This does not delete the merchant or its payment records.',
    );

    if (!confirmed) return;

    sessionStorage.removeItem('payrail_demo_api_key');
    sessionStorage.removeItem('payrail_demo_merchant_name');
    sessionStorage.removeItem('payrail_demo_merchant_id');

    setApiKey('');
    setMerchantName('');
    setMerchantId(null);
    setPayments([]);
    setNotice('Local demo credentials cleared.');
    setError('');
    setActiveTab('overview');
  }

  const navigation: { id: Tab; label: string; symbol: string }[] = [
    { id: 'overview', label: 'Overview', symbol: '◫' },
    { id: 'payments', label: 'Payments', symbol: '⇄' },
    { id: 'create', label: 'Create payment', symbol: '+' },
    { id: 'developers', label: 'Developers', symbol: '</>' },
  ];

  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-white/[0.07] bg-[#0b111e] px-5 py-6 lg:flex">
        <a href="#" className="flex items-center gap-3 px-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-xl font-bold text-white">
            P
          </span>
          <span>
            <span className="block text-lg font-semibold tracking-tight">
              PayRail
            </span>
            <span className="block text-xs text-slate-500">
              Payment infrastructure
            </span>
          </span>
        </a>

        <div className="mt-10">
          <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
            Workspace
          </p>
          <nav className="mt-3 space-y-1">
            {navigation.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setError('');
                  setNotice('');
                }}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${
                  activeTab === item.id
                    ? 'bg-blue-500/15 font-medium text-blue-300 ring-1 ring-blue-400/20'
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-white'
                }`}
              >
                <span className="w-5 text-center text-base">{item.symbol}</span>
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-auto rounded-2xl border border-blue-400/15 bg-blue-500/[0.07] p-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-400" />
            <span className="text-xs font-semibold text-blue-200">
              Base Sepolia
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            Testnet environment. Test tokens have no monetary value.
          </p>
          <div className="mt-4 border-t border-white/[0.07] pt-3 text-xs text-slate-500">
            Development workspace
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-white/[0.07] bg-[#080d18]/90 px-5 py-4 backdrop-blur-xl sm:px-8">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                Merchant workspace
              </p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">
                {navigation.find((item) => item.id === activeTab)?.label}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.08] px-3 py-1.5 text-xs text-amber-200">
                TESTNET
              </span>
              <span className="hidden max-w-40 truncate text-sm text-slate-400 sm:block">
                {merchantName || 'Merchant not configured'}
              </span>
              <span
                title={
                  apiKey ? 'Merchant API key loaded' : 'Merchant setup required'
                }
                className={`h-2.5 w-2.5 rounded-full ${
                  apiKey ? 'bg-emerald-400' : 'bg-slate-600'
                }`}
              />
            </div>
          </div>

          <nav className="mx-auto mt-4 flex max-w-7xl gap-2 overflow-x-auto lg:hidden">
            {navigation.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs ${
                  activeTab === item.id
                    ? 'bg-blue-500/15 text-blue-300'
                    : 'bg-white/[0.04] text-slate-400'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </header>

        <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
          {error && (
            <div
              role="alert"
              className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-red-400/20 bg-red-400/[0.07] p-4 text-sm text-red-200"
            >
              <span>{error}</span>
              <button onClick={() => setError('')} aria-label="Dismiss error">
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
                onClick={() => setNotice('')}
                aria-label="Dismiss message"
              >
                ×
              </button>
            </div>
          )}

          {!apiKey ? (
            <section className="mx-auto max-w-xl rounded-2xl border border-white/[0.08] bg-[#101827] p-6 sm:p-8">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/15 text-xl text-blue-300">
                ↗
              </div>
              <p className="mt-6 text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
                Get started
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                Create your merchant workspace
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                Register a development merchant to access payment intents and
                the dashboard. Your API key is stored only in this browser
                session.
              </p>

              <form onSubmit={registerMerchant} className="mt-7 space-y-4">
                <div>
                  <label
                    htmlFor="merchant-name"
                    className="mb-2 block text-sm text-slate-300"
                  >
                    Merchant name
                  </label>
                  <input
                    id="merchant-name"
                    required
                    minLength={1}
                    maxLength={120}
                    value={registrationName}
                    onChange={(event) =>
                      setRegistrationName(event.target.value)
                    }
                    placeholder="Acme Store"
                    className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-blue-400/60"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting
                    ? 'Creating merchant…'
                    : 'Create development merchant'}
                </button>
              </form>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                Development only. Do not use production credentials or real
                funds in this demo.
              </p>
            </section>
          ) : (
            <>
              {activeTab === 'overview' && (
                <>
                  <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
                    <div>
                      <p className="text-sm text-slate-400">
                        Welcome back, {merchantName}.
                      </p>
                      <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                        Payment overview
                      </h2>
                      <p className="mt-2 text-sm text-slate-500">
                        Metrics calculated from the payment intents returned by
                        your API.
                      </p>
                    </div>
                    <button
                      onClick={() => void loadPayments(apiKey)}
                      disabled={loading}
                      className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/[0.04] disabled:opacity-50"
                    >
                      {loading ? 'Refreshing…' : 'Refresh data'}
                    </button>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <MetricCard
                      label="Payment intents"
                      value={String(payments.length)}
                      detail="Records returned by the API"
                    />
                    <MetricCard
                      label="Successful payments"
                      value={String(succeeded.length)}
                      detail="Status: succeeded"
                    />
                    <MetricCard
                      label="Confirmed volume"
                      value={`${formatUSDC(totalVolume)} USDC`}
                      detail="Succeeded intents only"
                    />
                    <MetricCard
                      label="Awaiting payment"
                      value={String(pending.length)}
                      detail="Requires payment or confirming"
                    />
                  </div>

                  <section className="mt-8 overflow-hidden rounded-2xl border border-white/[0.08] bg-[#101827]">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-5 sm:px-6">
                      <div>
                        <h3 className="font-semibold">
                          Recent payment intents
                        </h3>
                        <p className="mt-1 text-xs text-slate-500">
                          Latest records from your merchant account
                        </p>
                      </div>
                      <button
                        onClick={() => setActiveTab('payments')}
                        className="text-sm text-blue-300 hover:text-blue-200"
                      >
                        View all payments →
                      </button>
                    </div>
                    <PaymentsTable
                      payments={payments.slice(0, 5)}
                      loading={loading}
                      onCancel={cancelPayment}
                      busyPayment={busyPayment}
                      compact
                    />
                  </section>
                </>
              )}

              {activeTab === 'payments' && (
                <section className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#101827]">
                  <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.07] px-5 py-5 sm:px-6">
                    <div>
                      <h2 className="text-lg font-semibold">
                        All payment intents
                      </h2>
                      <p className="mt-1 text-sm text-slate-500">
                        Search by ID, recipient, description, status, or
                        transaction hash.
                      </p>
                    </div>
                    <button
                      onClick={() => setActiveTab('create')}
                      className="rounded-xl bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-400"
                    >
                      + Create payment
                    </button>
                  </div>
                  <div className="border-b border-white/[0.07] p-5">
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Search payment intents…"
                      aria-label="Search payment intents"
                      className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-blue-400/60 sm:max-w-md"
                    />
                  </div>
                  <PaymentsTable
                    payments={filteredPayments}
                    loading={loading}
                    onCancel={cancelPayment}
                    busyPayment={busyPayment}
                  />
                </section>
              )}

              {activeTab === 'create' && (
                <section className="mx-auto max-w-3xl rounded-2xl border border-white/[0.08] bg-[#101827] p-6 sm:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
                    Payment intents
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                    Create a payment
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    Create an intent for USDC on Base Sepolia. This records a
                    payment request; it does not transfer funds by itself.
                  </p>

                  <form onSubmit={createPayment} className="mt-8 space-y-5">
                    <div className="grid gap-5 sm:grid-cols-2">
                      <div>
                        <label
                          htmlFor="amount"
                          className="mb-2 block text-sm text-slate-300"
                        >
                          Amount (USDC)
                        </label>
                        <input
                          id="amount"
                          inputMode="decimal"
                          required
                          value={amount}
                          onChange={(event) => setAmount(event.target.value)}
                          placeholder="10.00"
                          className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm outline-none focus:border-blue-400/60"
                        />
                        <p className="mt-2 text-xs text-slate-500">
                          Up to 6 decimal places.
                        </p>
                      </div>
                      <div>
                        <label
                          htmlFor="network"
                          className="mb-2 block text-sm text-slate-300"
                        >
                          Network
                        </label>
                        <input
                          id="network"
                          value="Base Sepolia"
                          readOnly
                          className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm text-slate-400"
                        />
                      </div>
                    </div>

                    <div>
                      <label
                        htmlFor="recipient"
                        className="mb-2 block text-sm text-slate-300"
                      >
                        Recipient wallet address
                      </label>
                      <input
                        id="recipient"
                        required
                        value={recipient}
                        onChange={(event) => setRecipient(event.target.value)}
                        placeholder="0x..."
                        spellCheck={false}
                        autoComplete="off"
                        className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 font-mono text-sm outline-none placeholder:text-slate-600 focus:border-blue-400/60"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="description"
                        className="mb-2 block text-sm text-slate-300"
                      >
                        Description{' '}
                        <span className="text-slate-500">(optional)</span>
                      </label>
                      <textarea
                        id="description"
                        rows={3}
                        maxLength={500}
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        placeholder="What is this payment for?"
                        className="w-full resize-y rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-blue-400/60"
                      />
                    </div>

                    <div className="rounded-xl border border-amber-300/15 bg-amber-300/[0.05] p-4 text-xs leading-5 text-amber-100/80">
                      This creates a payment intent that expires after 30
                      minutes. An on-chain transfer and independent backend
                      verification are separate steps.
                    </div>

                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full rounded-xl bg-blue-500 px-4 py-3 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {submitting
                        ? 'Creating payment intent…'
                        : 'Create payment intent'}
                    </button>
                  </form>
                </section>
              )}

              {activeTab === 'developers' && (
                <div className="grid gap-5 xl:grid-cols-2">
                  <section className="rounded-2xl border border-white/[0.08] bg-[#101827] p-6">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
                      API configuration
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">
                      Developer settings
                    </h2>

                    <div className="mt-6 space-y-5">
                      <div>
                        <p className="mb-2 text-xs text-slate-500">
                          API base URL
                        </p>
                        <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[#090f1a] p-3">
                          <code className="break-all text-sm text-slate-300">
                            {API_BASE || 'Not configured'}
                          </code>
                          <button
                            disabled={!API_BASE}
                            onClick={() => void copyValue(API_BASE)}
                            className="shrink-0 text-xs text-blue-300 disabled:opacity-40"
                          >
                            Copy
                          </button>
                        </div>
                      </div>

                      <div>
                        <p className="mb-2 text-xs text-slate-500">
                          Merchant ID
                        </p>
                        <p className="rounded-xl border border-white/[0.07] bg-[#090f1a] p-3 font-mono text-sm">
                          {merchantId ?? '—'}
                        </p>
                      </div>

                      <div>
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p className="text-xs text-slate-500">
                            Development API key
                          </p>
                          <button
                            onClick={() => setShowKey((shown) => !shown)}
                            className="text-xs text-blue-300"
                          >
                            {showKey ? 'Hide key' : 'Reveal key'}
                          </button>
                        </div>
                        <div className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-[#090f1a] p-3">
                          <code className="min-w-0 flex-1 break-all text-sm text-slate-300">
                            {showKey
                              ? apiKey
                              : `${apiKey.slice(0, 10)}••••••••••••••••`}
                          </code>
                          <button
                            onClick={() => void copyValue(apiKey)}
                            className="shrink-0 text-xs text-blue-300"
                          >
                            Copy
                          </button>
                        </div>
                      </div>
                    </div>

                    <p className="mt-5 text-xs leading-5 text-amber-200/80">
                      Demo only: this key is held in sessionStorage. A
                      production merchant dashboard should keep privileged
                      credentials on a protected server, not in browser storage.
                    </p>
                  </section>

                  <section className="rounded-2xl border border-white/[0.08] bg-[#101827] p-6">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
                      Quick start
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">
                      Create a payment intent
                    </h2>
                    <p className="mt-3 text-sm leading-6 text-slate-400">
                      Payment operations require a merchant Bearer API key and
                      an Idempotency-Key header.
                    </p>

                    <pre className="mt-5 overflow-x-auto rounded-xl border border-white/[0.07] bg-[#090f1a] p-4 text-xs leading-6 text-slate-300">
                      <code>{`curl -X POST ${API_BASE || '<NEXT_PUBLIC_API_URL>'}/v1/payment_intents \\
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
                      Amounts are integer USDC base units: 1 USDC equals
                      1,000,000 units. Replace the example placeholders before
                      running the command.
                    </p>

                    <button
                      onClick={clearDemoSession}
                      className="mt-6 rounded-xl border border-red-400/20 px-4 py-2.5 text-sm text-red-300 hover:bg-red-400/[0.07]"
                    >
                      Clear browser demo credentials
                    </button>
                  </section>
                </div>
              )}
            </>
          )}

          <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-5 text-xs text-slate-600">
            <span>PayRail · Development workspace</span>
            <span>Base Sepolia · Testnet only</span>
          </footer>
        </div>
      </div>
    </main>
  );
}

function PaymentsTable({
  payments,
  loading,
  onCancel,
  busyPayment,
  compact = false,
}: {
  payments: Payment[];
  loading: boolean;
  onCancel: (payment: Payment) => void;
  busyPayment: string;
  compact?: boolean;
}) {
  if (loading && payments.length === 0) {
    return (
      <div className="px-6 py-12 text-center text-sm text-slate-400">
        Loading payment records…
      </div>
    );
  }

  if (payments.length === 0) {
    return (
      <div className="px-6 py-14 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.04] text-xl text-slate-400">
          ⇄
        </div>
        <h3 className="mt-4 font-medium text-white">No payment intents yet</h3>
        <p className="mt-2 text-sm text-slate-500">
          Create a payment intent to see its details here.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left">
        <thead>
          <tr className="border-b border-white/[0.07] text-xs text-slate-500">
            <th className="px-5 py-3 font-medium sm:px-6">Payment</th>
            <th className="px-5 py-3 font-medium">Amount</th>
            <th className="px-5 py-3 font-medium">Status</th>
            {!compact && <th className="px-5 py-3 font-medium">Network</th>}
            <th className="px-5 py-3 font-medium">Created</th>
            <th className="px-5 py-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => {
            const canCancel = payment.status === 'requires_payment';

            return (
              <tr
                key={payment.public_id}
                className="border-b border-white/[0.05] last:border-0 hover:bg-white/[0.02]"
              >
                <td className="px-5 py-4 sm:px-6">
                  <p className="font-mono text-xs text-slate-200">
                    {payment.public_id}
                  </p>
                  <p className="mt-1 max-w-56 truncate text-xs text-slate-500">
                    {payment.description || payment.recipient}
                  </p>
                  {payment.transaction_hash && (
                    <a
                      href={`https://sepolia.basescan.org/tx/${payment.transaction_hash}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-xs text-blue-300 hover:text-blue-200"
                    >
                      View transaction ↗
                    </a>
                  )}
                </td>
                <td className="px-5 py-4">
                  <p className="whitespace-nowrap text-sm font-medium text-white">
                    {formatUSDC(payment.amount)} {payment.currency}
                  </p>
                </td>
                <td className="px-5 py-4">
                  <StatusBadge status={payment.status} />
                </td>
                {!compact && (
                  <td className="px-5 py-4 text-xs text-slate-400">
                    {payment.network}
                  </td>
                )}
                <td className="px-5 py-4 text-xs text-slate-400">
                  {formatDate(payment.created_at)}
                </td>
                <td className="px-5 py-4">
                  {canCancel ? (
                    <button
                      disabled={busyPayment === payment.public_id}
                      onClick={() => onCancel(payment)}
                      className="whitespace-nowrap text-xs text-red-300 hover:text-red-200 disabled:opacity-50"
                    >
                      {busyPayment === payment.public_id
                        ? 'Canceling…'
                        : 'Cancel'}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-600">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
