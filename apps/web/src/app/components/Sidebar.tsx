'use client';

import type { NavigationItem, Tab } from '../types';

type SidebarProps = {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  navigation: NavigationItem[];
};

export function Sidebar({ activeTab, onTabChange, navigation }: SidebarProps) {
  return (
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
              onClick={() => onTabChange(item.id)}
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
  );
}
