import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { useApp } from '../context/AppContext';
import type { RootStackParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Onboarding'>;

export function OnboardingScreen({ navigation }: Props) {
  const { setOnboardingDone } = useApp();

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={styles.center}>
        <View style={styles.avatar}>
          <MaterialCommunityIcons name="robot" size={48} color={colors.accent} />
        </View>
        <Text style={styles.title}>Chào mừng đến với Alpha Mini</Text>
        <Text style={styles.sub}>Robot của bạn ở trạng thái nào?</Text>

        <Pressable
          style={[styles.btn, styles.primary]}
          onPress={() => navigation.navigate('BLEProvisioning')}>
          <Text style={styles.primaryTxt}>Robot mới — cần cấu hình WiFi</Text>
        </Pressable>

        <Pressable
          style={[styles.btn, styles.secondary]}
          onPress={async () => {
            await setOnboardingDone(true);
            navigation.reset({
              index: 1,
              routes: [{ name: 'Main' }, { name: 'Settings' }],
            });
          }}>
          <Text style={styles.secondaryTxt}>Robot đã có WiFi — cấu hình server</Text>
        </Pressable>

        <Pressable
          style={styles.skip}
          onPress={async () => {
            await setOnboardingDone(true);
            navigation.reset({ index: 0, routes: [{ name: 'Main' }] });
          }}>
          <Text style={styles.skipTxt}>Bỏ qua, vào app luôn</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    justifyContent: 'center',
    gap: spacing.md,
  },
  avatar: {
    alignSelf: 'center',
    width: 96,
    height: 96,
    borderRadius: radius.full,
    backgroundColor: colors.accentBg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  title: {
    fontSize: font.h1,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
  },
  sub: {
    fontSize: font.body,
    color: colors.textMuted,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  btn: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  primary: { backgroundColor: colors.accentBg, borderColor: colors.accent },
  primaryTxt: {
    color: colors.accent,
    fontSize: font.title,
    fontWeight: '600',
    textAlign: 'center',
  },
  secondary: { backgroundColor: colors.card },
  secondaryTxt: {
    color: colors.text,
    fontSize: font.title,
    textAlign: 'center',
  },
  skip: { alignSelf: 'center', padding: spacing.sm },
  skipTxt: { color: colors.textMuted, fontSize: font.body },
});
