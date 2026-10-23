'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  useAccount,
  useConnect,
  usePublicClient,
  useSwitchChain,
  useWriteContract,
} from 'wagmi';
import { baseSepolia } from 'wagmi/chains';
import {
  formatUnits,
  isAddress,
  keccak256,
  toBytes,
  type Address,
  type Hash,
} from 'viem';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, '') ?? '';
const BASE_SEPOLIA_USDC = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';
const ERC20_ABI = [
  {
    type: 'function',
    name: 'balanceOf',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    type: 'function',
    name: 'allowance',
    stateMutability: 'view',
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'spender', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    type: 'function',
    name: 'approve',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'value', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
] as const;
const ROUTER_ABI = [
  {
    type: 'function',
    name: 'pay',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'paymentId', type: 'bytes32' },
      { name: 'token', type: 'address' },
      { name: 'recipient', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [],
  },
] as const;

type CheckoutData = {
  public_id: string;
  merchant_name: string;
  amount: string;
  currency: string;
  network: string;
  recipient: Address;
  status: string;
  expires_at: string;
  transaction_hash: Hash | null;
  chain_id: number;
  token_address: Address | null;
  router_address: Address | null;
};

const STATUS_LABEL: Record<string, string> = {
  requires_payment: 'Waiting for payment',
  confirming: 'Confirming on Base Sepolia',
  succeeded: 'Payment complete',
  underpaid: 'Payment amount is too low',
  overpaid: 'Payment amount differs from the requested amount',
  reorged: 'Payment needs review after a chain reorganization',
  expired: 'Payment expired',
  canceled: 'Payment canceled',
};

function getApiUrl(): string {
  if (!API_URL) {
    throw new Error(
      'Set NEXT_PUBLIC_API_URL to the API address for this deployment.',
    );
  }
  let parsed: URL;
  try {
    parsed = new URL(API_URL);
  } catch {
    throw new Error('NEXT_PUBLIC_API_URL must be a valid URL.');
  }
  const localHost = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (
    process.env.NODE_ENV === 'production' &&
    (localHost || parsed.protocol !== 'https:')
  ) {
    throw new Error(
      'Production NEXT_PUBLIC_API_URL must use a public HTTPS host.',
    );
  }
  return API_URL;
}

function validPaymentConfiguration(payment: CheckoutData): boolean {
  return (
    payment.chain_id === baseSepolia.id &&
    payment.network === 'base-sepolia' &&
    payment.currency === 'USDC' &&
    /^\d+$/.test(payment.amount) &&
    isAddress(payment.recipient) &&
    Boolean(payment.token_address && isAddress(payment.token_address)) &&
    payment.token_address?.toLowerCase() === BASE_SEPOLIA_USDC.toLowerCase() &&
    Boolean(payment.router_address && isAddress(payment.router_address))
  );
}

export function Checkout({ publicId }: { publicId: string }) {
  const [payment, setPayment] = useState<CheckoutData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submittedHash, setSubmittedHash] = useState<Hash | null>(null);
  const paymentStatus = payment?.status;
  const recordedTransactionHash = payment?.transaction_hash;
  const { address, chainId, isConnected } = useAccount();
  const { connect, connectors, isPending: isConnecting } = useConnect();
  const { switchChainAsync } = useSwitchChain();
  const client = usePublicClient({ chainId: baseSepolia.id });
  const { writeContractAsync } = useWriteContract();

  useEffect(() => {
    const savedHash = sessionStorage.getItem(`payrail_checkout_tx_${publicId}`);
    if (savedHash && /^0x[0-9a-fA-F]{64}$/.test(savedHash)) {
      setSubmittedHash(savedHash as Hash);
    }
  }, [publicId]);

  const loadPayment = useCallback(async () => {
    const response = await fetch(
      `${getApiUrl()}/checkout/${encodeURIComponent(publicId)}`,
      {
        cache: 'no-store',
      },
    );
    if (!response.ok)
      throw new Error(
        response.status === 404
          ? 'Payment link not found.'
          : 'Checkout service is unavailable.',
      );
    const data = (await response.json()) as CheckoutData;
    if (!/^\d+$/.test(data.amount) || BigInt(data.amount) <= 0n) {
      throw new Error('The checkout API returned an invalid token amount.');
    }
    setPayment(data);
  }, [publicId]);

  const submitForVerification = useCallback(
    async (transactionHash: Hash) => {
      const response = await fetch(
        `${getApiUrl()}/checkout/${encodeURIComponent(publicId)}/verify`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ transaction_hash: transactionHash }),
        },
      );
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(
          data.detail ??
            'Transaction submitted; server verification could not be completed yet. Retry checkout verification.',
        );
      }
      await loadPayment();
    },
    [loadPayment, publicId],
  );

  useEffect(() => {
    void loadPayment().catch((cause: unknown) =>
      setError(
        cause instanceof Error ? cause.message : 'Unable to load this payment.',
      ),
    );
  }, [loadPayment]);

  useEffect(() => {
    if (
      !payment ||
      !['confirming', 'requires_payment'].includes(payment.status)
    )
      return;
    const timer = window.setInterval(() => {
      void loadPayment().catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [loadPayment, payment]);

  useEffect(() => {
    if (
      !submittedHash ||
      (recordedTransactionHash === submittedHash &&
        paymentStatus &&
        !['requires_payment', 'confirming'].includes(paymentStatus))
    )
      return;
    const timer = window.setInterval(() => {
      void submitForVerification(submittedHash).catch((cause: unknown) => {
        setError(
          cause instanceof Error
            ? cause.message
            : 'Transaction verification is unavailable.',
        );
      });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [
    paymentStatus,
    recordedTransactionHash,
    submittedHash,
    submitForVerification,
  ]);

  useEffect(() => {
    if (
      submittedHash &&
      recordedTransactionHash === submittedHash &&
      paymentStatus &&
      !['requires_payment', 'confirming'].includes(paymentStatus)
    ) {
      sessionStorage.removeItem(`payrail_checkout_tx_${publicId}`);
    }
  }, [paymentStatus, publicId, recordedTransactionHash, submittedHash]);

  async function startPayment() {
    if (
      !payment ||
      !address ||
      !client ||
      !payment.token_address ||
      !payment.router_address
    )
      return;
    setBusy(true);
    setError(null);
    try {
      if (chainId !== baseSepolia.id)
        await switchChainAsync({ chainId: baseSepolia.id });
      const amount = BigInt(payment.amount);
      const [balance, allowance] = await Promise.all([
        client.readContract({
          address: payment.token_address,
          abi: ERC20_ABI,
          functionName: 'balanceOf',
          args: [address],
        }),
        client.readContract({
          address: payment.token_address,
          abi: ERC20_ABI,
          functionName: 'allowance',
          args: [address, payment.router_address],
        }),
      ]);
      if (balance < amount)
        throw new Error('Insufficient USDC balance on Base Sepolia.');
      if (allowance < amount) {
        const approvalHash = await writeContractAsync({
          chainId: baseSepolia.id,
          address: payment.token_address,
          abi: ERC20_ABI,
          functionName: 'approve',
          args: [payment.router_address, amount],
        });
        await client.waitForTransactionReceipt({ hash: approvalHash });
      }
      const transactionHash = await writeContractAsync({
        chainId: baseSepolia.id,
        address: payment.router_address,
        abi: ROUTER_ABI,
        functionName: 'pay',
        args: [
          keccak256(toBytes(payment.public_id)),
          payment.token_address,
          payment.recipient,
          amount,
        ],
      });
      setSubmittedHash(transactionHash);
      sessionStorage.setItem(
        `payrail_checkout_tx_${publicId}`,
        transactionHash,
      );
      await submitForVerification(transactionHash);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Wallet payment failed or was rejected.',
      );
    } finally {
      setBusy(false);
    }
  }

  const terminal =
    payment && !['requires_payment', 'confirming'].includes(payment.status);
  const configValid = payment ? validPaymentConfiguration(payment) : false;
  const expirationTimestamp = payment ? Date.parse(payment.expires_at) : NaN;
  const expired =
    !Number.isFinite(expirationTimestamp) || Date.now() >= expirationTimestamp;
  const explorer = payment?.transaction_hash
    ? `https://sepolia.basescan.org/tx/${payment.transaction_hash}`
    : null;

  return (
    <main className="checkout-shell">
      <header className="brand">
        <span className="brand-mark">P</span>
        <span>
          PayRail <small>SECURE CHECKOUT</small>
        </span>
      </header>
      <section className="checkout-card">
        <div className="eyebrow">BASE SEPOLIA · TESTNET</div>
        <h1>{payment ? `Pay ${payment.merchant_name}` : 'Loading checkout'}</h1>
        {payment ? (
          <>
            {!configValid && (
              <p className="error-message" role="alert">
                Checkout configuration is incomplete or invalid. Contact the
                merchant; no payment will be sent.
              </p>
            )}
            <div className="amount">
              {formatUnits(BigInt(payment.amount), 6)}{' '}
              <span>{payment.currency}</span>
            </div>
            <dl className="payment-details">
              <div>
                <dt>Recipient</dt>
                <dd>{shortAddress(payment.recipient)}</dd>
              </div>
              <div>
                <dt>Network</dt>
                <dd>Base Sepolia</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={`status-dot ${payment.status}`} />
                  {STATUS_LABEL[payment.status] ?? payment.status}
                </dd>
              </div>
              {address && (
                <div>
                  <dt>Connected wallet</dt>
                  <dd>{shortAddress(address)}</dd>
                </div>
              )}
            </dl>
            {payment.status === 'requires_payment' && !isConnected && (
              <button
                className="primary-button"
                disabled={
                  !configValid ||
                  expired ||
                  isConnecting ||
                  connectors.length === 0
                }
                onClick={() => connect({ connector: connectors[0] })}
              >
                {isConnecting ? 'Connecting…' : 'Connect wallet'}
              </button>
            )}
            {payment.status === 'requires_payment' &&
              isConnected &&
              !submittedHash && (
                <button
                  className="primary-button"
                  disabled={!configValid || expired || busy}
                  onClick={() => void startPayment()}
                >
                  {busy
                    ? 'Waiting for wallet…'
                    : chainId !== baseSepolia.id
                      ? 'Switch to Base Sepolia and pay'
                      : 'Pay with USDC'}
                </button>
              )}
            {payment.status === 'confirming' && (
              <p className="notice">
                Your transaction was submitted. PayRail is checking the on-chain
                receipt and confirmations.
              </p>
            )}
            {submittedHash && payment.status === 'requires_payment' && (
              <p className="notice">
                Transaction submitted. Waiting for it to appear on-chain;
                checkout will retry verification automatically.
              </p>
            )}
            {expired && payment.status === 'requires_payment' && (
              <p className="error-message" role="alert">
                This payment link has expired. Ask the merchant for a new link.
              </p>
            )}
            {(explorer || submittedHash) && (
              <a
                className="explorer-link"
                href={`https://sepolia.basescan.org/tx/${payment.transaction_hash ?? submittedHash}`}
                target="_blank"
                rel="noreferrer"
              >
                View transaction on BaseScan ↗
              </a>
            )}
            {submittedHash && payment.status === 'requires_payment' && (
              <button
                className="primary-button"
                disabled={busy}
                onClick={() => void submitForVerification(submittedHash)}
              >
                {busy
                  ? 'Checking transaction…'
                  : 'Retry transaction verification'}
              </button>
            )}
            {terminal && (
              <p className="notice">
                {STATUS_LABEL[payment.status] ?? payment.status}
              </p>
            )}
            <p className="expiry">
              Link expires {new Date(payment.expires_at).toLocaleString()}
            </p>
          </>
        ) : (
          <p className="notice">{error ?? 'Loading payment details…'}</p>
        )}
        {error && payment && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
      </section>
      <p className="checkout-footnote">
        Your wallet signs each transaction. PayRail never asks for a seed phrase
        or private key.
      </p>
    </main>
  );
}

function shortAddress(address: string) {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}
