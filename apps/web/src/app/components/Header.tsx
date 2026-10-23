'use client';

import type { NavigationItem, Tab } from '../types';

type HeaderProps = {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  navigation: NavigationItem[];
  merchantName: string;
  hasApiKey: boolean;
};

export function Header({
  activeTab,
  onTabChange,
  navigation,
  merchantName,
  hasApiKey,
}: HeaderProps) {
  const currentTabLabel =
    navigation.find((item) => item.id === activeTab)?.label ?? 'Dashboard';

  return (
    <header className="sticky top-0 z-10 border-b border-white/[0.07] bg-[#080d18]/90 px-5 py-4 backdrop-blur-xl sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
            Merchant workspace
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">
            {currentTabLabel}
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
              hasApiKey ? 'Merchant API key loaded' : 'Merchant setup required'
            }
            className={`h-2.5 w-2.5 rounded-full ${
              hasApiKey ? 'bg-emerald-400' : 'bg-slate-600'
            }`}
          />
        </div>
      </div>

      <nav className="mx-auto mt-4 flex max-w-7xl gap-2 overflow-x-auto lg:hidden">
        {navigation.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
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
  );
}
