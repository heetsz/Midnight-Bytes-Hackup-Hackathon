// Real client that talks to the FastAPI backend so
// mobile payments appear in the web dashboard live feed.

// NOTE: When running on a real device, 'localhost' points to the phone.
// Use the same host IP that Expo shows in the Metro log (exp://IP:port).
// For your current session, Metro is using 172.20.10.5, so we point the
// backend base URL at that IP on port 8000.
const API_BASE_URL = 'http://172.20.10.5:8000';

function buildUserKey(name) {
  const base = (name || 'mobile_user')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 32);
  return base || 'mobile-user';
}

async function ensureUserExists({ name }) {
  const userKey = buildUserKey(name);

  try {
    const res = await fetch(`${API_BASE_URL}/api/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_key: userKey,
        name: name || userKey,
        email: `${userKey}@demo.local`,
        phone_no: '0000000000',
        device_centroid: [],
      }),
    });

    if (!res.ok && res.status !== 409) {
      throw new Error(`User create failed: ${res.status}`);
    }
  } catch (err) {
    // For the demo, log and continue; backend will 404 if this fails.
    console.warn('ensureUserExists error', err);
  }

  return userKey;
}

export async function assessTransaction({
  name,
  location,
  amount,
  cardType,
  merchant,
}) {
  const numericAmount = Number(amount) || 0;
  const userKey = await ensureUserExists({ name });

  const payload = {
    user_key: userKey,
    frontend_payload: {
      transaction_amt: numericAmount,
      client_ip: '0.0.0.0',
      merchant_name: merchant || 'Mobile Merchant',
      location: location?.text || 'Mobile User',
    },
    fingerprint: {
      id_31_idx: 0,
      id_33_idx: 0,
      DeviceType_idx: 0,
      DeviceInfo_idx: 0,
      os_browser_idx: 0,
      screen_width: 390,
      screen_height: 844,
      hardware_concurrency: 6,
    },
    card1: cardType === 'credit' ? 1 : 0,
    d1: null,
    d2: null,
    d3: null,
    v_cols: [],
    c_cols: [],
    m_cols: [],
  };

  const res = await fetch(`${API_BASE_URL}/api/transactions/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Transaction assess failed: ${res.status}`);
  }

  const data = await res.json();
  const backendDecision = data.decision || 'approve';
  const why = data.why_flagged || 'Scored by backend model.';

  let mappedDecision = 'SAFE';
  if (backendDecision === 'mfa') mappedDecision = 'MODERATE';
  if (backendDecision === 'block') mappedDecision = 'HIGH';

  return { decision: mappedDecision, reason: why };
}
