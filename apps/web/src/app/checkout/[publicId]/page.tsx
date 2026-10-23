import { Checkout } from './checkout';

export default async function CheckoutPage({
  params,
}: {
  params: Promise<{ publicId: string }>;
}) {
  const { publicId } = await params;
  return <Checkout publicId={publicId} />;
}
