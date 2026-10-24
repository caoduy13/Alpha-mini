import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import type { BleStage } from '../ble/manager';
import { colors, font, spacing } from '../theme';

const ROWS: { stage: BleStage; label: string }[] = [
  { stage: 'connecting', label: 'Kết nối BLE...' },
  { stage: 'discovering', label: 'Thỏa thuận MTU & khám phá GATT...' },
  { stage: 'enabling-indication', label: 'Bật indication...' },
  { stage: 'handshaking', label: 'Bắt tay với robot...' },
  { stage: 'sending-wifi', label: 'Gửi cấu hình WiFi...' },
  { stage: 'waiting-response', label: 'Đợi robot vào WiFi...' },
];

function rowIndex(stage: BleStage): number {
  const i = ROWS.findIndex(r => r.stage === stage);
  return i >= 0 ? i : -1;
}

type Props = {
  currentStage: BleStage;
  lastErrorStage: BleStage | null;
};

export function BleStageList({ currentStage, lastErrorStage }: Props) {
  const active = rowIndex(currentStage);
  const failIdx =
    currentStage === 'failed' && lastErrorStage
      ? rowIndex(lastErrorStage)
      : -1;

  return (
    <View style={styles.wrap}>
      {ROWS.map((row, idx) => {
        let iconName: 'check-circle' | 'close-circle' | 'progress-clock' | 'circle-outline' =
          'circle-outline';
        let color = colors.textMuted;

        if (currentStage === 'success') {
          iconName = 'check-circle';
          color = colors.success;
        } else if (failIdx >= 0) {
          if (idx < failIdx) {
            iconName = 'check-circle';
            color = colors.success;
          } else if (idx === failIdx) {
            iconName = 'close-circle';
            color = colors.error;
          }
        } else if (active >= 0) {
          if (idx < active) {
            iconName = 'check-circle';
            color = colors.success;
          } else if (idx === active) {
            iconName = 'progress-clock';
            color = colors.accent;
          }
        }

        return (
          <View key={row.stage} style={styles.row}>
            <MaterialCommunityIcons name={iconName} size={18} color={color} />
            <Text style={[styles.label, { color }]}>{row.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  label: { flex: 1, fontSize: font.body },
});
