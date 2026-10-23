'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Payment } from '../types';
import { getApiBase, parseResponse } from '../utils/api';

export function usePayments(apiKey: string) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyPayment, setBusyPayment] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadPayments = useCallback(async (key: string) => {
    if (!key) return;
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
    if (apiKey) {
      void loadPayments(apiKey);
    } else {
      setPayments([]);
    }
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

  const totalVolume = useMemo(
    () => succeeded.reduce((sum, p) => sum + p.amount, 0),
    [succeeded],
  );

  const cancelPayment = useCallback(
    async (payment: Payment) => {
      if (!apiKey) return false;

      const confirmed = window.confirm(
        `Cancel payment intent ${payment.public_id}?`,
      );

      if (!confirmed) return false;

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
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Cancellation failed.');
        return false;
      } finally {
        setBusyPayment('');
      }
    },
    [apiKey, loadPayments],
  );

  const clearPayments = useCallback(() => {
    setPayments([]);
  }, []);

  return {
    payments,
    loading,
    busyPayment,
    error,
    setError,
    notice,
    setNotice,
    loadPayments,
    cancelPayment,
    clearPayments,
    succeeded,
    pending,
    totalVolume,
  };
}
