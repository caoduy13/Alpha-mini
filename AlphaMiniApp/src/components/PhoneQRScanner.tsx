import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import {
  Camera,
  isScannedCode,
  useCameraDevice,
  useCameraPermission,
  useObjectOutput,
  usePreviewOutput,
} from 'react-native-vision-camera';
import { colors, font, radius, spacing } from '../theme';

type Props = {
  active: boolean;
  onCode: (text: string) => void;
};

export function PhoneQRScanner({ active, onCode }: Props) {
  const device = useCameraDevice('back');
  const { hasPermission, requestPermission } = useCameraPermission();
  const preview = usePreviewOutput();
  const lastFire = useRef(0);
  const fired = useRef(false);

  const objectOutput = useObjectOutput({
    types: ['qr'],
    onObjectsScanned: useCallback(
      (objects: unknown[]) => {
        if (!active || fired.current) {
          return;
        }
        const now = Date.now();
        if (now - lastFire.current < 900) {
          return;
        }
        for (const o of objects) {
          if (isScannedCode(o as never) && (o as { value?: string }).value) {
            lastFire.current = now;
            fired.current = true;
            onCode(String((o as { value?: string }).value));
            break;
          }
        }
      },
      [active, onCode],
    ),
  });

  useEffect(() => {
    if (!hasPermission) {
      requestPermission();
    }
  }, [hasPermission, requestPermission]);

  useEffect(() => {
    if (active) {
      fired.current = false;
    }
  }, [active]);

  const pulse = useSharedValue(1);
  useEffect(() => {
    pulse.value = withRepeat(withTiming(1.06, { duration: 700 }), -1, true);
  }, [pulse]);

  const pulseStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pulse.value }],
    opacity: 0.35 + (0.35 * (pulse.value - 1)) / 0.06,
  }));

  const outputs = useMemo(
    () => [preview, objectOutput],
    [preview, objectOutput],
  );

  if (!hasPermission) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.ph}>Cần quyền camera để quét QR.</Text>
        <Pressable style={styles.btn} onPress={requestPermission}>
          <Text style={styles.btnTxt}>Cấp quyền</Text>
        </Pressable>
      </View>
    );
  }

  if (!device) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.ph}>Không tìm thấy camera sau.</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <Camera
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={active}
        outputs={outputs}
      />
      <Animated.View style={[styles.frame, pulseStyle]} pointerEvents="none">
        <View style={[styles.corner, styles.tl]} />
        <View style={[styles.corner, styles.tr]} />
        <View style={[styles.corner, styles.bl]} />
        <View style={[styles.corner, styles.br]} />
      </Animated.View>
    </View>
  );
}

const cornerBase = {
  position: 'absolute' as const,
  width: 28,
  height: 28,
  borderColor: colors.success,
};
const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    borderRadius: radius.lg,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    minHeight: 260,
  },
  placeholder: {
    flex: 1,
    minHeight: 260,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.md,
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  ph: { color: colors.textMuted, textAlign: 'center', fontSize: font.body },
  btn: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accentBg,
  },
  btnTxt: { color: colors.accent, fontWeight: '700' },
  frame: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  corner: {
    ...cornerBase,
    borderWidth: 3,
  },
  tl: {
    top: '22%',
    left: '12%',
    borderRightWidth: 0,
    borderBottomWidth: 0,
    borderTopLeftRadius: radius.md,
  },
  tr: {
    top: '22%',
    right: '12%',
    borderLeftWidth: 0,
    borderBottomWidth: 0,
    borderTopRightRadius: radius.md,
  },
  bl: {
    bottom: '22%',
    left: '12%',
    borderRightWidth: 0,
    borderTopWidth: 0,
    borderBottomLeftRadius: radius.md,
  },
  br: {
    bottom: '22%',
    right: '12%',
    borderLeftWidth: 0,
    borderTopWidth: 0,
    borderBottomRightRadius: radius.md,
  },
});
