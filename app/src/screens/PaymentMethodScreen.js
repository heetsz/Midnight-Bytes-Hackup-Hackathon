import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import GradientBackground from '../components/GradientBackground';

const PaymentOption = ({ label, description, selected, onPress }) => {
  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={onPress}
      style={[styles.option, selected && styles.optionSelected]}
    >
      <View style={styles.optionLeft}>
        <View style={styles.iconCircle}>
          <View style={styles.iconChip} />
        </View>
        <View>
          <Text style={styles.optionLabel}>{label}</Text>
          <Text style={styles.optionDescription}>{description}</Text>
        </View>
      </View>
      <View style={[styles.radioOuter, selected && styles.radioOuterSelected]}
      >
        {selected && <View style={styles.radioInner} />}
      </View>
    </TouchableOpacity>
  );
};

const PaymentMethodScreen = () => {
  const route = useRoute();
  const navigation = useNavigation();
  const { user } = route.params || {};

  const [selectedType, setSelectedType] = useState('debit');

  const handleContinue = () => {
    if (!selectedType) return;
    navigation.replace('Payment', {
      user,
      cardType: selectedType,
    });
  };

  return (
    <GradientBackground>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Payment Method</Text>
          <Text style={styles.subtitle}>Choose how you want to pay</Text>
        </View>

        <View style={styles.card}>
          <PaymentOption
            label="Debit Card"
            description="Pay instantly from your bank account"
            selected={selectedType === 'debit'}
            onPress={() => setSelectedType('debit')}
          />

          <PaymentOption
            label="Credit Card"
            description="Use your credit limit securely"
            selected={selectedType === 'credit'}
            onPress={() => setSelectedType('credit')}
          />
        </View>

        <TouchableOpacity
          activeOpacity={0.9}
          onPress={handleContinue}
          style={[styles.continueButton, !selectedType && styles.continueButtonDisabled]}
        >
          <Text style={styles.continueText}>Continue</Text>
        </TouchableOpacity>
      </View>
    </GradientBackground>
  );
};

export default PaymentMethodScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.5,
  },
  subtitle: {
    marginTop: 8,
    fontSize: 14,
    color: 'rgba(248, 250, 252, 0.7)',
  },
  card: {
    backgroundColor: 'rgba(15, 23, 42, 0.9)',
    borderRadius: 24,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.4)',
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 16,
    paddingHorizontal: 12,
    borderRadius: 18,
    marginBottom: 8,
    backgroundColor: 'rgba(15, 23, 42, 0.7)',
  },
  optionSelected: {
    backgroundColor: 'rgba(8, 47, 73, 0.9)',
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.9)',
    shadowColor: '#38bdf8',
    shadowOpacity: 0.35,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
  },
  optionLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(15, 23, 42, 1)',
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconChip: {
    width: 20,
    height: 14,
    borderRadius: 4,
    backgroundColor: 'rgba(148, 163, 184, 0.9)',
  },
  optionLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#e5e7eb',
  },
  optionDescription: {
    marginTop: 2,
    fontSize: 12,
    color: 'rgba(148, 163, 184, 0.9)',
  },
  radioOuter: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: 'rgba(148, 163, 184, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioOuterSelected: {
    borderColor: '#38bdf8',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#38bdf8',
  },
  continueButton: {
    marginTop: 24,
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderWidth: 1,
    borderColor: '#38bdf8',
    shadowColor: '#38bdf8',
    shadowOpacity: 0.4,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 12 },
  },
  continueButtonDisabled: {
    opacity: 0.5,
  },
  continueText: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.5,
    color: '#e0f2fe',
  },
});
