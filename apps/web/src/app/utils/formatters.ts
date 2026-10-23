export function formatUSDC(amount: number): string {
  return (amount / 1_000_000).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  });
}

export function parseUSDC(value: string): number {
  const trimmed = value.trim();

  if (!/^\d+(\.\d{1,6})?$/.test(trimmed)) {
    throw new Error('Enter a positive amount with up to 6 decimal places.');
  }

  const [whole, fraction = ''] = trimmed.split('.');
  const units =
    BigInt(whole) * 1_000_000n + BigInt((fraction + '000000').slice(0, 6));

  if (units <= 0n || units > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error('Enter a valid amount greater than zero.');
  }

  return Number(units);
}

export function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString();
}
