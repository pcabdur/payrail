'use client';

import type { Payment } from '../types';
import { formatUSDC } from '../utils/formatters';
import { MetricCard } from './MetricCard';
import { PaymentsTable } from './PaymentsTable';

type OverviewTabProps = {
  merchantName: string;
  payments: Payment[];
  succeeded: Payment[];
  pending: Payment[];
  totalVolume: number;
  loading: boolean;
  onRefresh: () => void;
  onNavigateToPayments: () => void;
  onCancelPayment: (payment: Payment) => void;
  busyPayment: string;
};

export function OverviewTab({
  merchantName,
  payments,
  succeeded,
  pending,
  totalVolume,
  loading,
  onRefresh,
  onNavigateToPayments,
  onCancelPayment,
  busyPayment,
}: OverviewTabProps) {
  return (
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
            Metrics calculated from the payment intents returned by your API.
          </p>
        </div>
        <button
          onClick={onRefresh}
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
            <h3 className="font-semibold">Recent payment intents</h3>
            <p className="mt-1 text-xs text-slate-500">
              Latest records from your merchant account
            </p>
          </div>
          <button
            onClick={onNavigateToPayments}
            className="text-sm text-blue-300 hover:text-blue-200"
          >
            View all payments →
          </button>
        </div>
        <PaymentsTable
          payments={payments.slice(0, 5)}
          loading={loading}
          onCancel={onCancelPayment}
          busyPayment={busyPayment}
          compact
        />
      </section>
    </>
  );
}
