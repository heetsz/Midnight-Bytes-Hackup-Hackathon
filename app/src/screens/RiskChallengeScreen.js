import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import GradientBackground from '../components/GradientBackground';

const DELAY_SECONDS = 30; // between 30-60s, kept short for demo

export default function RiskChallengeScreen({ route, navigation }) {
  const { user, payment, decision } = route.params || {};

  const [countdown, setCountdown] = useState(DELAY_SECONDS);
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let timer;
    if (waiting && countdown > 0) {
      timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    }
    if (waiting && countdown === 0) {
      completeSuccess('Delay challenge passed.');
    }
    return () => timer && clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting, countdown]);

  const completeSuccess = (reason) => {
    navigation.replace('Result', {
      status: 'success',
      title: 'Payment approved after checks',
      message: 'Extra security checks passed. Your payment is complete.',
      meta: {
        amount: payment?.amount,
        merchant: payment?.merchant,
        cardType: payment?.cardType,
        risk: 'Moderate',
        reason: reason || decision?.reason,
      },
    });
  };

  const startDelay = () => {
    setError('');
    setWaiting(true);
  };

  const handleBiometric = async () => {
    try {
      setError('');
      const compatible = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();

      if (!compatible || !enrolled) {
        setError('Biometric auth not available on this device. Use the delay option instead.');
        return;
      }

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Confirm it is really you',
        fallbackLabel: 'Use PIN',
      });

      if (result.success) {
        completeSuccess('Biometric challenge passed.');
      } else {
        setError('Biometric authentication failed or was cancelled.');
      }
    } catch (e) {
      setError('Unable to start biometric verification.');
    }
  };

  return (
    <GradientBackground>
      <View style={styles.container}>
        <Text style={styles.title}>Extra security check</Text>
        <Text style={styles.subtitle}>
          Your bank marked this transaction as moderate risk. Complete one of the challenges below to continue.
        </Text>

        <View style={styles.challengeCard}>
          <Text style={styles.sectionTitle}>Biometric check</Text>
          <Text style={styles.bodyText}>
            Use your phone's fingerprint or face unlock to confirm it's really you.
          </Text>
          <TouchableOpacity style={styles.primaryButton} onPress={handleBiometric}>
            <Text style={styles.primaryButtonText}>Verify with biometrics</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.challengeCard}>
          <Text style={styles.sectionTitle}>Smart delay</Text>
          <Text style={styles.bodyText}>
            Or wait for a short {DELAY_SECONDS}-second delay. Fraud bots hate waiting, but humans are fine with it.
          </Text>

          <TouchableOpacity
            style={[styles.secondaryButton, waiting && styles.secondaryButtonDisabled]}
            onPress={startDelay}
            disabled={waiting}
          >
            <Text style={styles.secondaryButtonText}>
              {waiting ? `Waiting… ${countdown}s` : 'Start delay challenge'}
            </Text>
          </TouchableOpacity>
        </View>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <View style={styles.paymentMeta}>
          <Text style={styles.metaLine}>Paying {payment?.merchant}</Text>
          <Text style={styles.metaLine}>
            {payment?.cardType === 'credit' ? 'Credit card' : 'Debit card'} • ₹{payment?.amount}
          </Text>
        </View>
      </View>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#e5e7eb',
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 13,
    color: '#9ca3af',
    marginBottom: 18,
  },
  challengeCard: {
    backgroundColor: '#020617',
    borderRadius: 18,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: 'rgba(148,163,184,0.4)',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#e5e7eb',
    marginBottom: 6,
  },
  bodyText: {
    fontSize: 13,
    color: '#9ca3af',
    marginBottom: 10,
  },
  primaryButton: {
    marginTop: 4,
    backgroundColor: '#0ea5e9',
    borderRadius: 999,
    paddingVertical: 10,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#f9fafb',
    fontWeight: '600',
    fontSize: 14,
  },
  secondaryButton: {
    marginTop: 6,
    backgroundColor: '#111827',
    borderRadius: 999,
    paddingVertical: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#4b5563',
  },
  secondaryButtonDisabled: {
    opacity: 0.8,
  },
  secondaryButtonText: {
    color: '#e5e7eb',
    fontWeight: '500',
    fontSize: 14,
  },
  errorText: {
    marginTop: 6,
    fontSize: 12,
    color: '#f97373',
  },
  paymentMeta: {
    marginTop: 16,
  },
  metaLine: {
    fontSize: 12,
    color: '#9ca3af',
  },
});
