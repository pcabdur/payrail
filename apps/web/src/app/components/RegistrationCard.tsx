'use client';

import { useState } from 'react';
import type { Merchant } from '../types';
import { getApiBase, parseResponse } from '../utils/api';

type RegistrationCardProps = {
  onMerchantRegistered: (merchant: Merchant) => void;
  onError: (error: string) => void;
  onNotice: (notice: string) => void;
};

export function RegistrationCard({
  onMerchantRegistered,
  onError,
  onNotice,
}: RegistrationCardProps) {
  const [registrationName, setRegistrationName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onError('');
    onNotice('');
    setSubmitting(true);

    try {
      const response = await fetch(`${getApiBase()}/v1/merchants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: registrationName.trim() }),
      });

      const merchant = await parseResponse<Merchant>(response);
      onMerchantRegistered(merchant);
      onNotice(
        'Merchant created. Your development API key is stored for this browser session.',
      );
    } catch (err) {
      onError(
        err instanceof Error ? err.message : 'Merchant registration failed.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
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
        Register a development merchant to access payment intents and the
        dashboard. Your API key is stored only in this browser session.
      </p>

      <form onSubmit={handleSubmit} className="mt-7 space-y-4">
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
            onChange={(event) => setRegistrationName(event.target.value)}
            placeholder="Acme Store"
            className="w-full rounded-xl border border-white/10 bg-[#090f1a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-blue-400/60"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Creating merchant…' : 'Create development merchant'}
        </button>
      </form>
      <p className="mt-4 text-xs leading-5 text-slate-500">
        Development only. Do not use production credentials or real funds in
        this demo.
      </p>
    </section>
  );
}
