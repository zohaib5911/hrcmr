/**
 * The prices the public site shows. Display only: what is charged is the Stripe price behind
 * STRIPE_PRICE_ANNUAL / STRIPE_PRICE_TEN_YEAR (plan 8.16). Change a price here and in Stripe together.
 */
export const PRICING = {
  annual: { amount: 50, years: 1 },
  tenYear: { amount: 240, years: 10 },
  /** Days in which a paid plan is refunded in full, automatically. */
  refundDays: 14,
} as const;

const WHOLE_POUNDS = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

export const pounds = (amount: number): string => WHOLE_POUNDS.format(amount);
