import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, Keyboard, TouchableWithoutFeedback } from 'react-native';
import * as Location from 'expo-location';
import GradientBackground from '../components/GradientBackground';

export default function LoginScreen({ navigation }) {
  const [name, setName] = useState('');
  const [locationText, setLocationText] = useState('Fetching location...');
  const [coords, setCoords] = useState(null);
  const [loadingLocation, setLoadingLocation] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== 'granted') {
          setError('Location permission denied. You can still continue.');
          setLocationText('Location permission not granted');
          setLoadingLocation(false);
          return;
        }

        const loc = await Location.getCurrentPositionAsync({});
        setCoords({ latitude: loc.coords.latitude, longitude: loc.coords.longitude });
        setLocationText(`${loc.coords.latitude.toFixed(4)}, ${loc.coords.longitude.toFixed(4)}`);
      } catch (e) {
        setError('Unable to fetch location.');
        setLocationText('Location unavailable');
      } finally {
        setLoadingLocation(false);
      }
    })();
  }, []);

  const canContinue = name.trim().length > 1;

  const onContinue = () => {
    navigation.replace('PaymentMethod', {
      user: {
        name: name.trim(),
        location: {
          text: locationText,
          coords,
        },
      },
    });
  };

  return (
    <GradientBackground>
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <View style={styles.container}>
          <View style={styles.header}>
            <View style={styles.logoCircle}>
              <Text style={styles.logoText}>NP</Text>
            </View>
            <Text style={styles.brand}>Next Payments</Text>
            <Text style={styles.subtitle}>Sign in to secure your payments</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.label}>Name</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="Enter your full name"
              placeholderTextColor="#64748b"
            />

            <Text style={styles.label}>Location</Text>
            <View style={styles.locationRow}>
              {loadingLocation ? (
                <ActivityIndicator color="#38bdf8" size="small" />
              ) : (
                <Text style={styles.locationText}>{locationText}</Text>
              )}
            </View>
            {error ? <Text style={styles.errorText}>{error}</Text> : null}

            <TouchableOpacity
              style={[styles.button, !canContinue && styles.buttonDisabled]}
              disabled={!canContinue}
              onPress={onContinue}
              activeOpacity={0.9}
            >
              <Text style={styles.buttonText}>Continue</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Device location is used to score risk in real time.</Text>
          </View>
        </View>
      </TouchableWithoutFeedback>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    transform: [{ translateY: -30 }],
  },
  header: {
    marginBottom: 40,
    alignItems: 'center',
  },
  logoCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    marginBottom: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#020617',
    borderWidth: 1,
    borderColor: 'rgba(148,163,184,0.4)',
  },
  logoText: {
    fontSize: 22,
    fontWeight: '700',
    color: '#e5e7eb',
  },
  brand: {
    fontSize: 26,
    fontWeight: '700',
    color: '#e5e7eb',
  },
  subtitle: {
    marginTop: 4,
    fontSize: 13,
    color: '#9ca3af',
  },
  card: {
    backgroundColor: 'rgba(15,23,42,0.9)',
    borderRadius: 24,
    paddingVertical: 22,
    paddingHorizontal: 18,
    borderWidth: 1,
    borderColor: 'rgba(31,41,55,0.9)',
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 14 },
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#e5e7eb',
    marginBottom: 12,
  },
  label: {
    fontSize: 13,
    color: '#94a3b8',
    marginTop: 12,
    marginBottom: 4,
  },
  input: {
    backgroundColor: '#020617',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1f2937',
    color: '#e5e7eb',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  locationRow: {
    backgroundColor: '#020617',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1f2937',
    paddingHorizontal: 12,
    paddingVertical: 10,
    minHeight: 44,
    justifyContent: 'center',
  },
  locationText: {
    fontSize: 14,
    color: '#e5e7eb',
  },
  button: {
    marginTop: 24,
    borderRadius: 999,
    paddingVertical: 12,
    paddingHorizontal: 8,
    alignItems: 'center',
    backgroundColor: 'rgba(15,23,42,0.85)',
    borderWidth: 1,
    borderColor: 'rgba(148,202,255,0.45)',
    shadowColor: '#000',
    shadowOpacity: 0.6,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
  },
  buttonDisabled: {
    backgroundColor: 'rgba(15,23,42,0.6)',
    borderColor: 'rgba(75,85,99,0.7)',
  },
  buttonText: {
    color: '#e5f2ff',
    fontWeight: '600',
    fontSize: 15,
    letterSpacing: 0.3,
  },
  footer: {
    marginTop: 24,
  },
  footerText: {
    fontSize: 12,
    color: '#6b7280',
  },
  errorText: {
    marginTop: 6,
    fontSize: 12,
    color: '#f97373',
  },
});
