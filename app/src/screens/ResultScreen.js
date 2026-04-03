import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import GradientBackground from '../components/GradientBackground';

export default function ResultScreen({ route, navigation }) {
  const { status, title, message, meta } = route.params || {};

  const isSuccess = status === 'success';

  const onNewPayment = () => {
    navigation.reset({
      index: 0,
      routes: [{ name: 'Login' }],
    });
  };

  return (
    <GradientBackground>
      <View style={styles.container}>
        <View style={[styles.statusIcon, isSuccess ? styles.statusIconSuccess : styles.statusIconBlocked]}>
          <Text style={styles.statusEmoji}>{isSuccess ? '✅' : '🚫'}</Text>
        </View>

        <Text style={styles.title}>{title}</Text>
        <Text style={styles.message}>{message}</Text>

        {meta && (
          <View style={styles.metaCard}>
            <Text style={styles.metaLine}>Amount: ₹{meta.amount}</Text>
            <Text style={styles.metaLine}>Merchant: {meta.merchant}</Text>
            <Text style={styles.metaLine}>Method: {meta.cardType === 'credit' ? 'Credit card' : 'Debit card'}</Text>
            <Text style={styles.metaLine}>Risk: {meta.risk}</Text>
            {meta.reason ? <Text style={styles.metaReason}>Why: {meta.reason}</Text> : null}
          </View>
        )}

        <TouchableOpacity
          style={[styles.button, isSuccess ? styles.buttonPrimary : styles.buttonSecondary]}
          onPress={onNewPayment}
        >
          <Text style={styles.buttonText}>Make another payment</Text>
        </TouchableOpacity>
      </View>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusIcon: {
    width: 82,
    height: 82,
    borderRadius: 999,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 18,
  },
  statusIconSuccess: {
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.6)',
  },
  statusIconBlocked: {
    backgroundColor: 'rgba(248,113,113,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(248,113,113,0.6)',
  },
  statusEmoji: {
    fontSize: 36,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#e5e7eb',
    marginBottom: 6,
    textAlign: 'center',
  },
  message: {
    fontSize: 13,
    color: '#9ca3af',
    textAlign: 'center',
    paddingHorizontal: 24,
    marginBottom: 20,
  },
  metaCard: {
    backgroundColor: '#020617',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(148,163,184,0.4)',
    width: '100%',
    maxWidth: 360,
    marginBottom: 18,
  },
  metaLine: {
    fontSize: 13,
    color: '#e5e7eb',
  },
  metaReason: {
    marginTop: 8,
    fontSize: 12,
    color: '#9ca3af',
  },
  button: {
    borderRadius: 999,
    paddingVertical: 12,
    paddingHorizontal: 26,
  },
  buttonPrimary: {
    backgroundColor: '#22c55e',
  },
  buttonSecondary: {
    backgroundColor: '#f97373',
  },
  buttonText: {
    color: '#f9fafb',
    fontWeight: '600',
    fontSize: 15,
  },
});
