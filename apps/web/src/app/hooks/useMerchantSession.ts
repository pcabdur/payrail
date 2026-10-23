'use client';

import { useEffect, useState } from 'react';
import type { Merchant } from '../types';

export function useMerchantSession() {
  const [apiKey, setApiKey] = useState('');
  const [merchantName, setMerchantName] = useState('');
  const [merchantId, setMerchantId] = useState<number | null>(null);
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

  function saveMerchantSession(merchant: Merchant) {
    sessionStorage.setItem('payrail_demo_api_key', merchant.api_key);
    sessionStorage.setItem('payrail_demo_merchant_name', merchant.name);
    sessionStorage.setItem('payrail_demo_merchant_id', String(merchant.id));

    setApiKey(merchant.api_key);
    setMerchantName(merchant.name);
    setMerchantId(merchant.id);
  }

  function clearDemoSession(): boolean {
    const confirmed = window.confirm(
      'Clear this browser session’s merchant credentials? This does not delete the merchant or its payment records.',
    );

    if (!confirmed) return false;

    sessionStorage.removeItem('payrail_demo_api_key');
    sessionStorage.removeItem('payrail_demo_merchant_name');
    sessionStorage.removeItem('payrail_demo_merchant_id');

    setApiKey('');
    setMerchantName('');
    setMerchantId(null);
    return true;
  }

  return {
    apiKey,
    merchantName,
    merchantId,
    showKey,
    setShowKey,
    saveMerchantSession,
    clearDemoSession,
  };
}
