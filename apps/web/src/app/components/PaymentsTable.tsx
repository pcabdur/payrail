'use client';

import type { Payment } from '../types';
import { formatDate, formatUSDC } from '../utils/formatters';
import { StatusBadge } from './StatusBadge';

type PaymentsTableProps = {
  payments: Payment[];
  loading: boolean;
  onCancel: (payment: Payment) => void;
  busyPayment: string;
  compact?: boolean;
};

export function PaymentsTable({
  payments,
  loading,
  onCancel,
  busyPayment,
  compact = false,
}: PaymentsTableProps) {
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
