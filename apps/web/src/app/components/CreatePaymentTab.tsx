'use client';

import { useState } from 'react';
import type { Payment } from '../types';
import { getApiBase, parseResponse } from '../utils/api';
import { parseUSDC } from '../utils/formatters';

type CreatePaymentTabProps = {
  apiKey: string;
  onPaymentCreated: (payment: Payment) => void;
  onError: (error: string) => void;
  onNotice: (notice: string) => void;
};

export function CreatePaymentTab({
  apiKey,
  onPaymentCreated,
  onError,
  onNotice,
}: CreatePaymentTabProps) {
  const [amount, setAmount] = useState('10.00');
  const [recipient, setRecipient] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onError('');
    onNotice('');
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

      onNotice(`Payment intent ${payment.public_id} created successfully.`);
      setDescription('');
      onPaymentCreated(payment);
    } catch (err) {
      onError(
        err instanceof Error ? err.message : 'Could not create payment intent.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-3xl rounded-2xl border border-white/[0.08] bg-[#101827] p-6 sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
        Payment intents
      </p>
      <h2 className="mt-2 text-2xl font-semibold tracking-tight">
        Create a payment
      </h2>
      <p className="mt-3 text-sm leading-6 text-slate-400">
        Create an intent for USDC on Base Sepolia. This records a payment
        request; it does not transfer funds by itself.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
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
            Description <span className="text-slate-500">(optional)</span>
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
          This creates a payment intent that expires after 30 minutes. An
          on-chain transfer and independent backend verification are separate
          steps.
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-blue-500 px-4 py-3 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Creating payment intent…' : 'Create payment intent'}
        </button>
      </form>
    </section>
  );
}
