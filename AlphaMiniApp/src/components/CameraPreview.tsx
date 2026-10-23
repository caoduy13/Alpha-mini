import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { getRobotCameraFrameB64 } from '../api/endpoints';
import { colors, font, radius, spacing } from '../theme';

type Props = {
  robotOnline: boolean;
  pollMs?: number;
  height?: number;
};

export function CameraPreview({
  robotOnline,
  pollMs = 2000,
  height = 220,
}: Props) {
  const [uri, setUri] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;

    async function snap() {
      if (!robotOnline) {
        setUri(null);
        setErr(null);
        return;
      }
      try {
        const j = await getRobotCameraFrameB64();
        if (cancelled || !j.ok || !j.image_b64) {
          throw new Error('no_frame');
        }
        setUri(`data:image/jpeg;base64,${j.image_b64}`);
        setErr(null);
      } catch {
        if (!cancelled) {
          setUri(null);
          setErr('Không tải được khung hình');
        }
      }
    }

    snap();
    timer = setInterval(snap, pollMs);
    return () => {
      cancelled = true;
      if (timer) {
        clearInterval(timer);
      }
    };
  }, [robotOnline, pollMs]);

  return (
    <View style={[styles.box, { height }]}>
      {!robotOnline ? (
        <View style={styles.placeholder}>
          <MaterialCommunityIcons
            name="robot-off"
            size={40}
            color={colors.textMuted}
          />
          <Text style={styles.phText}>Robot offline</Text>
        </View>
      ) : uri ? (
        <>
          <Image source={{ uri }} style={styles.img} resizeMode="cover" />
          <View style={styles.live}>
            <Text style={styles.liveTxt}>LIVE</Text>
          </View>
        </>
      ) : err ? (
        <View style={styles.placeholder}>
          <Text style={styles.err}>{err}</Text>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
        <View style={styles.placeholder}>
          <ActivityIndicator color={colors.accent} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    borderRadius: radius.lg,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    position: 'relative',
  },
  img: { width: '100%', height: '100%' },
  placeholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    padding: spacing.md,
  },
  phText: { color: colors.textMuted, fontSize: font.body },
  err: { color: colors.error, fontSize: font.label, textAlign: 'center' },
  live: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.errorBg,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  liveTxt: {
    color: colors.error,
    fontSize: font.small,
    fontWeight: '700',
  },
});
