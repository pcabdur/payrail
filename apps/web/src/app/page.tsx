'use client';

import { useState } from 'react';
import { Alerts } from './components/Alerts';
import { CreatePaymentTab } from './components/CreatePaymentTab';
import { DevelopersTab } from './components/DevelopersTab';
import { Header } from './components/Header';
import { OverviewTab } from './components/OverviewTab';
import { PaymentsTab } from './components/PaymentsTab';
import { RegistrationCard } from './components/RegistrationCard';
import { Sidebar } from './components/Sidebar';
import { useMerchantSession } from './hooks/useMerchantSession';
import { usePayments } from './hooks/usePayments';
import type { NavigationItem, Tab } from './types';
import { API_BASE } from './utils/api';

const NAVIGATION_ITEMS: NavigationItem[] = [
  { id: 'overview', label: 'Overview', symbol: '◫' },
  { id: 'payments', label: 'Payments', symbol: '⇄' },
  { id: 'create', label: 'Create payment', symbol: '+' },
  { id: 'developers', label: 'Developers', symbol: '</>' },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const {
    apiKey,
    merchantName,
    merchantId,
    showKey,
    setShowKey,
    saveMerchantSession,
    clearDemoSession,
  } = useMerchantSession();

  const {
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
  } = usePayments(apiKey);

  async function handleCopy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice('Copied to clipboard.');
    } catch {
      setError('Clipboard access failed. Select and copy the value manually.');
    }
  }

  function handleClearSession() {
    const cleared = clearDemoSession();
    if (cleared) {
      clearPayments();
      setNotice('Local demo credentials cleared.');
      setError('');
      setActiveTab('overview');
    }
  }

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setError('');
    setNotice('');
  }

  function handlePaymentCreated() {
    setActiveTab('payments');
    if (apiKey) {
      void loadPayments(apiKey);
    }
  }

  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        navigation={NAVIGATION_ITEMS}
      />

      <div className="lg:pl-64">
        <Header
          activeTab={activeTab}
          onTabChange={handleTabChange}
          navigation={NAVIGATION_ITEMS}
          merchantName={merchantName}
          hasApiKey={Boolean(apiKey)}
        />

        <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
          <Alerts
            error={error}
            notice={notice}
            onClearError={() => setError('')}
            onClearNotice={() => setNotice('')}
          />

          {!apiKey ? (
            <RegistrationCard
              onMerchantRegistered={(merchant) => {
                saveMerchantSession(merchant);
                setActiveTab('overview');
              }}
              onError={setError}
              onNotice={setNotice}
            />
          ) : (
            <>
              {activeTab === 'overview' && (
                <OverviewTab
                  merchantName={merchantName}
                  payments={payments}
                  succeeded={succeeded}
                  pending={pending}
                  totalVolume={totalVolume}
                  loading={loading}
                  onRefresh={() => void loadPayments(apiKey)}
                  onNavigateToPayments={() => handleTabChange('payments')}
                  onCancelPayment={(p) => void cancelPayment(p)}
                  busyPayment={busyPayment}
                />
              )}

              {activeTab === 'payments' && (
                <PaymentsTab
                  payments={payments}
                  loading={loading}
                  onNavigateToCreate={() => handleTabChange('create')}
                  onCancelPayment={(p) => void cancelPayment(p)}
                  busyPayment={busyPayment}
                />
              )}

              {activeTab === 'create' && (
                <CreatePaymentTab
                  apiKey={apiKey}
                  onPaymentCreated={handlePaymentCreated}
                  onError={setError}
                  onNotice={setNotice}
                />
              )}

              {activeTab === 'developers' && (
                <DevelopersTab
                  apiBase={API_BASE}
                  merchantId={merchantId}
                  apiKey={apiKey}
                  showKey={showKey}
                  onToggleShowKey={() => setShowKey((s) => !s)}
                  onCopy={(val) => void handleCopy(val)}
                  onClearDemoSession={handleClearSession}
                />
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
