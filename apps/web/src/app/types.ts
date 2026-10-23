export type Merchant = {
  id: number;
  name: string;
  api_key: string;
  created_at: string;
};

export type Payment = {
  public_id: string;
  amount: number;
  currency: string;
  network: string;
  recipient: string;
  description: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  transaction_hash: string | null;
};

export type Tab = 'overview' | 'payments' | 'create' | 'developers';

export type NavigationItem = {
  id: Tab;
  label: string;
  symbol: string;
};
