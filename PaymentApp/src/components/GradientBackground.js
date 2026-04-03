import React, { useEffect, useRef } from 'react';
import { StyleSheet, View, Animated } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function GradientBackground({ children }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 4500,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 4500,
          useNativeDriver: true,
        }),
      ])
    );

    animation.start();

    return () => {
      animation.stop();
    };
  }, [pulse]);

  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.25],
  });

  const opacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.25, 0.7],
  });

  const primaryTranslateX = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [-12, 12],
  });

  const primaryTranslateY = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [8, -8],
  });

  const secondaryTranslateX = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [10, -10],
  });

  const secondaryTranslateY = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [-6, 6],
  });

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={["#020202", "#050816", "#020617"]}
        start={{ x: 0.1, y: 0 }}
        end={{ x: 0.9, y: 1 }}
        style={styles.gradient}
      />
      <Animated.View
        pointerEvents="none"
        style={[
          styles.orb,
          {
            transform: [
              { scale },
              { translateX: primaryTranslateX },
              { translateY: primaryTranslateY },
            ],
            opacity,
          },
        ]}
      />
      <Animated.View
        pointerEvents="none"
        style={[
          styles.orbSecondary,
          {
            transform: [
              { scale },
              { translateX: secondaryTranslateX },
              { translateY: secondaryTranslateY },
            ],
            opacity: opacity.interpolate({
              inputRange: [0, 1],
              outputRange: [0.15, 0.5],
            }),
          },
        ]}
      />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#020202",
  },
  gradient: {
    ...StyleSheet.absoluteFillObject,
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 40,
    paddingBottom: 32,
  },
  orb: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: 'rgba(255,255,255,0.06)',
    top: -60,
    right: -50,
  },
  orbSecondary: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: 'rgba(148,163,184,0.12)',
    bottom: -70,
    left: -40,
  },
});
