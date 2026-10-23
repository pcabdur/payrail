export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, '') ?? '';

export function getApiBase(): string {
  if (!API_BASE) {
    throw new Error(
      'Set NEXT_PUBLIC_API_URL to the API address for this deployment.',
    );
  }
  let parsed: URL;
  try {
    parsed = new URL(API_BASE);
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
  return API_BASE;
}

export async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();

  let data: { detail?: string };

  try {
    data = text ? (JSON.parse(text) as { detail?: string }) : {};
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(
      data.detail || `Request failed with HTTP ${response.status}`,
    );
  }

  return data as T;
}
