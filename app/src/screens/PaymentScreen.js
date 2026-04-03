import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, Keyboard } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import GradientBackground from '../components/GradientBackground';
import { assessTransaction } from '../api/fraudClient';

export default function PaymentScreen({ route, navigation }) {
  const { user, cardType: initialCardType } = route.params || {};

  const [cardType, setCardType] = useState(initialCardType || 'debit');
  const [cardNumber, setCardNumber] = useState('');
  const [cardNumberError, setCardNumberError] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvv, setCvv] = useState('');
  const [cvvError, setCvvError] = useState('');
  const [amount, setAmount] = useState('');
  const [merchant, setMerchant] = useState('Midnight Bytes Store');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [awaitingOtp, setAwaitingOtp] = useState(false);
  const [otp, setOtp] = useState('');
  const [otpError, setOtpError] = useState('');
  const [generatedOtp, setGeneratedOtp] = useState('');

  const expiryDigits = expiry.replace(/\D/g, '');
  const cvvDigits = cvv.replace(/\D/g, '');

  const canPay =
    cardNumber.replace(/\D/g, '').length === 16 &&
    expiryDigits.length === 4 &&
    cvvDigits.length === 3 &&
    Number(amount) > 0 &&
    !processing;

  const onPay = async () => {
    try {
      setError('');
      setProcessing(true);

      const numericAmount = Number(amount);

      // For amounts greater than 1000, require a biometric (face/fingerprint) check before proceeding
      if (numericAmount > 1000) {
        const compatible = await LocalAuthentication.hasHardwareAsync();
        const enrolled = await LocalAuthentication.isEnrolledAsync();

        if (!compatible || !enrolled) {
          setError('Biometric authentication is required for high-value payments, but is not available on this device.');
          setProcessing(false);
          return;
        }

        const result = await LocalAuthentication.authenticateAsync({
          promptMessage: 'Confirm with Face ID / biometrics',
          fallbackLabel: 'Use device passcode',
        });

        if (!result.success) {
          setError('Biometric authentication failed or was cancelled.');
          setProcessing(false);
          return;
        }

        // Biometric passed – now move to OTP verification step before completing payment
        const code = String(Math.floor(100000 + Math.random() * 900000));
        setGeneratedOtp(code);
        setAwaitingOtp(true);
        setOtp('');
        setOtpError('');
        setProcessing(false);
        return;
      }
      // For amounts up to and including 1000, continue with normal fraud decision flow
      const decision = await assessTransaction({
        name: user?.name,
        location: user?.location,
        amount,
        cardType,
      });

      if (decision.decision === 'SAFE') {
        navigation.replace('Result', {
          status: 'success',
          title: 'Payment approved',
          message: 'Your bank marked this transaction as safe.',
          meta: {
            amount,
            merchant,
            cardType,
            risk: 'Safe',
            reason: decision.reason,
          },
        });
      } else if (decision.decision === 'MODERATE') {
        navigation.replace('RiskChallenge', {
          user,
          payment: { amount, merchant, cardType },
          decision,
        });
      } else {
        navigation.replace('Result', {
          status: 'blocked',
          title: 'Transaction blocked',
          message: 'Your bank flagged this payment as high risk. They will contact you shortly.',
          meta: {
            amount,
            merchant,
            cardType,
            risk: 'High',
            reason: decision.reason,
          },
        });
      }
    } catch (e) {
      setError('Something went wrong. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  const onConfirmOtp = async () => {
    const trimmedOtp = otp.trim();

    if (trimmedOtp.length !== 6 || trimmedOtp !== generatedOtp) {
      setOtpError('Enter the 6-digit OTP sent to you');
      return;
    }

    try {
      setError('');
      setOtpError('');
      setProcessing(true);

      const decision = await assessTransaction({
        name: user?.name,
        location: user?.location,
        amount,
        cardType,
      });

      if (decision.decision === 'SAFE' || decision.decision === 'MODERATE') {
        // After biometric + OTP, treat safe or moderate as approved after checks
        navigation.replace('Result', {
          status: 'success',
          title: 'Payment approved after checks',
          message: 'Biometric and OTP verification passed. Your payment is complete.',
          meta: {
            amount,
            merchant,
            cardType,
            risk: decision.decision === 'SAFE' ? 'Safe' : 'Moderate',
            reason: decision.reason,
          },
        });
      } else {
        navigation.replace('Result', {
          status: 'blocked',
          title: 'Transaction blocked',
          message: 'Your bank flagged this payment as high risk. They will contact you shortly.',
          meta: {
            amount,
            merchant,
            cardType,
            risk: 'High',
            reason: decision.reason,
          },
        });
      }
    } catch (e) {
      setError('Something went wrong while verifying the OTP. Please try again.');
    } finally {
      setProcessing(false);
      setAwaitingOtp(false);
    }
  };

  const maskedName = user?.name ? user.name.toUpperCase() : 'CARD HOLDER';

  return (
    <GradientBackground>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.container}>
          <View style={styles.cardPreview}>
            <Text style={styles.cardBrand}>{cardType === 'debit' ? 'Debit' : 'Credit'} • Midnight Bank</Text>
            <Text style={styles.cardNumber}>{cardNumber || '••••  ••••  ••••  ••••'}</Text>
            <View style={styles.cardRow}>
              <View>
                <Text style={styles.cardLabel}>Card holder</Text>
                <Text style={styles.cardValue}>{maskedName}</Text>
              </View>
              <View>
                <Text style={styles.cardLabel}>Expires</Text>
                <Text style={styles.cardValue}>{expiry || 'MM/YY'}</Text>
              </View>
            </View>
          </View>

          <View style={styles.form}>
            <Text style={styles.label}>Card number</Text>
            <TextInput
              style={styles.input}
              keyboardType="numeric"
              value={cardNumber}
              returnKeyType="done"
              onSubmitEditing={Keyboard.dismiss}
              onChangeText={(value) => {
                const digits = value.replace(/\D/g, '');
                const limited = digits.slice(0, 16);
                const formatted = limited.replace(/(.{4})/g, '$1 ').trim();

                setCardNumber(formatted);

                if (limited.length > 0 && limited.length < 16) {
                  setCardNumberError('Enter 16 digits');
                } else {
                  setCardNumberError('');
                }
              }}
              placeholder="1234 5678 9012 3456"
              placeholderTextColor="#64748b"
            />
            {cardNumberError ? <Text style={styles.errorText}>{cardNumberError}</Text> : null}

            <View style={styles.row}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Text style={styles.label}>Expiry</Text>
                <TextInput
                  style={styles.input}
                  value={expiry}
                  onChangeText={(value) => {
                    const digits = value.replace(/\D/g, '');
                    const limited = digits.slice(0, 4);
                    let formatted = limited;
                    if (limited.length > 2) {
                      formatted = `${limited.slice(0, 2)}/${limited.slice(2)}`;
                    }
                    setExpiry(formatted);
                  }}
                  keyboardType="numeric"
                  returnKeyType="done"
                  onSubmitEditing={Keyboard.dismiss}
                  placeholder="MM/YY"
                  placeholderTextColor="#64748b"
                />
              </View>
              <View style={{ width: 90 }}>
                <Text style={styles.label}>CVV</Text>
                <TextInput
                  style={styles.input}
                  value={cvv}
                  onChangeText={(value) => {
                    const digits = value.replace(/\D/g, '');
                    const limited = digits.slice(0, 3);
                    setCvv(limited);

                    if (limited.length > 0 && limited.length < 3) {
                      setCvvError('Enter 3 digits');
                    } else {
                      setCvvError('');
                    }
                  }}
                  keyboardType="numeric"
                  secureTextEntry
                  returnKeyType="done"
                  onSubmitEditing={Keyboard.dismiss}
                  placeholder="•••"
                  placeholderTextColor="#64748b"
                />
                {cvvError ? <Text style={styles.errorText}>{cvvError}</Text> : null}
              </View>
            </View>

            <Text style={styles.label}>Merchant</Text>
            <TextInput
              style={styles.input}
              value={merchant}
              onChangeText={setMerchant}
              placeholder="Where are you paying?"
              returnKeyType="done"
              onSubmitEditing={Keyboard.dismiss}
              placeholderTextColor="#64748b"
            />

            <Text style={styles.label}>Amount (₹)</Text>
            <TextInput
              style={styles.input}
              value={amount}
              onChangeText={setAmount}
              keyboardType="numeric"
              returnKeyType="done"
              onSubmitEditing={Keyboard.dismiss}
              placeholder="1500"
              placeholderTextColor="#64748b"
            />

            {error ? <Text style={styles.errorText}>{error}</Text> : null}

            {awaitingOtp ? (
              <>
                <Text style={styles.label}>Enter OTP</Text>
                <TextInput
                  style={styles.input}
                  value={otp}
                  onChangeText={(value) => {
                    const digits = value.replace(/\D/g, '');
                    setOtp(digits.slice(0, 6));
                    if (otpError) {
                      setOtpError('');
                    }
                  }}
                  keyboardType="numeric"
                  placeholder="••••••"
                  placeholderTextColor="#64748b"
                />
                {otpError ? <Text style={styles.errorText}>{otpError}</Text> : null}
                <Text style={styles.otpHint}>
                  For demo we "send" an SMS OTP here: {generatedOtp}
                </Text>

                <TouchableOpacity
                  style={[styles.button, processing && styles.buttonDisabled]}
                  onPress={onConfirmOtp}
                  disabled={processing}
                >
                  <Text style={styles.buttonText}>
                    {processing ? 'Verifying…' : 'Verify OTP & Pay'}
                  </Text>
                </TouchableOpacity>
              </>
            ) : (
              <TouchableOpacity
                style={[styles.button, !canPay && styles.buttonDisabled]}
                onPress={onPay}
                disabled={!canPay}
              >
                <Text style={styles.buttonText}>
                  {processing ? 'Checking with bank…' : `Pay ₹${amount || '0'}`}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 132,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  brand: {
    fontSize: 22,
    fontWeight: '700',
    color: '#e5e7eb',
  },
  subtitle: {
    fontSize: 13,
    color: '#9ca3af',
  },
  cardPreview: {
    backgroundColor: '#0f172a',
    borderRadius: 18,
    padding: 18,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: 'rgba(148,163,184,0.3)',
  },
  cardBrand: {
    color: '#93c5fd',
    fontSize: 13,
    marginBottom: 18,
  },
  cardNumber: {
    color: '#e5e7eb',
    fontSize: 18,
    letterSpacing: 2,
    marginBottom: 16,
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  cardLabel: {
    fontSize: 11,
    color: '#9ca3af',
    textTransform: 'uppercase',
  },
  cardValue: {
    marginTop: 4,
    color: '#e5e7eb',
    fontSize: 13,
  },
  form: {
    flex: 1,
  },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: '#020617',
    borderRadius: 999,
    padding: 3,
    marginBottom: 12,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 999,
    alignItems: 'center',
  },
  segmentActive: {
    backgroundColor: '#0ea5e9',
  },
  segmentText: {
    fontSize: 13,
    color: '#9ca3af',
    fontWeight: '500',
  },
  segmentTextActive: {
    color: '#f9fafb',
  },
  label: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 8,
    marginBottom: 4,
  },
  input: {
    backgroundColor: '#020617',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1f2937',
    color: '#e5e7eb',
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 14,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  button: {
    marginTop: 20,
    backgroundColor: '#22c55e',
    borderRadius: 999,
    paddingVertical: 12,
    alignItems: 'center',
  },
  buttonDisabled: {
    backgroundColor: '#16a34a55',
  },
  buttonText: {
    color: '#f9fafb',
    fontWeight: '600',
    fontSize: 15,
  },
  errorText: {
    marginTop: 8,
    fontSize: 12,
    color: '#f97373',
  },
  otpHint: {
    marginTop: 6,
    fontSize: 11,
    color: '#9ca3af',
  },
});
