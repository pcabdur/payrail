'use client';

import { useMemo, useState } from 'react';
import type { Payment } from '../types';
import { PaymentsTable } from './PaymentsTable';

type PaymentsTabProps = {
  payments: Payment[];
  loading: boolean;
  onNavigateToCreate: () => void;
  onCancelPayment: (payment: Payment) => void;
  busyPayment: string;
};

export function PaymentsTab({
  payments,
  loading,
  onNavigateToCreate,
  onCancelPayment,
  busyPayment,
}: PaymentsTabProps) {
  const [search, setSearch] = useState('');

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

  return (
    <section className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#101827]">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.07] px-5 py-5 sm:px-6">
        <div>
          <h2 className="text-lg font-semibold">All payment intents</h2>
          <p className="mt-1 text-sm text-slate-500">
            Search by ID, recipient, description, status, or transaction hash.
          </p>
        </div>
        <button
          onClick={onNavigateToCreate}
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
        onCancel={onCancelPayment}
        busyPayment={busyPayment}
      />
    </section>
  );
}
