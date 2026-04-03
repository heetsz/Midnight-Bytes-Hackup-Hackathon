// Simple mock client you can later replace with real backend calls

export async function assessTransaction({
  name,
  location,
  amount,
  cardType,
}) {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 800));

  // Very simple rule-based stub for now
  const amt = Number(amount) || 0;

  if (amt <= 1000) {
    return { decision: 'SAFE', reason: 'Low amount, typical behavior' };
  }

  if (amt <= 5000) {
    return {
      decision: 'MODERATE',
      reason: 'Medium amount, extra verification suggested',
    };
  }

  return {
    decision: 'HIGH',
    reason: 'High amount, transaction looks risky',
  };
}
