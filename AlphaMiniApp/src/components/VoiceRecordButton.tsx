import React, { useCallback, useMemo, useState } from 'react';
import {
  PermissionsAndroid,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import AudioRecorderPlayer from 'react-native-audio-recorder-player';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, font, radius, spacing } from '../theme';

type Props = {
  disabled?: boolean;
  onRecorded: (uri: string) => Promise<void> | void;
};

async function ensureMic(): Promise<boolean> {
  if (Platform.OS !== 'android') {
    return true;
  }
  const res = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
  );
  return res === PermissionsAndroid.RESULTS.GRANTED;
}

export function VoiceRecordButton({ disabled, onRecorded }: Props) {
  const player = useMemo(() => new AudioRecorderPlayer(), []);
  const [recording, setRecording] = useState(false);

  const start = useCallback(async () => {
    if (disabled || recording) {
      return;
    }
    const ok = await ensureMic();
    if (!ok) {
      return;
    }
    setRecording(true);
    await player.startRecorder(undefined);
  }, [disabled, recording, player]);

  const stop = useCallback(async () => {
    if (!recording) {
      return;
    }
    setRecording(false);
    try {
      const uri = await player.stopRecorder();
      if (uri) {
        const normalized = uri.startsWith('file://') ? uri : `file://${uri}`;
        await onRecorded(normalized);
      }
    } catch (e) {
      console.warn('voice record stop', e);
    }
  }, [recording, onRecorded, player]);

  return (
    <Pressable
      disabled={disabled}
      onPressIn={start}
      onPressOut={stop}
      style={({ pressed }) => [
        styles.circle,
        recording && styles.active,
        pressed && styles.pressed,
      ]}>
      <MaterialCommunityIcons
        name={recording ? 'microphone' : 'microphone-outline'}
        size={26}
        color={recording ? colors.success : colors.text}
      />
      <Text style={styles.hint}>{recording ? 'Thả để gửi' : 'Giữ để nói'}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  circle: {
    width: 72,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  active: {
    borderColor: colors.success,
    backgroundColor: colors.successBg,
  },
  pressed: { opacity: 0.9 },
  hint: {
    marginTop: 2,
    fontSize: font.small,
    color: colors.textMuted,
    textAlign: 'center',
  },
});
