import React from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { robotTrigger } from '../api/endpoints';
import { colors, font, radius, spacing } from '../theme';

type Props = {
  visible: boolean;
  onClose: () => void;
};

const cmds: { cmd: string; label: string; icon: string }[] = [
  { cmd: 'forward', label: 'Tiến', icon: 'arrow-up-bold' },
  { cmd: 'left', label: 'Trái', icon: 'arrow-left-bold' },
  { cmd: 'right', label: 'Phải', icon: 'arrow-right-bold' },
  { cmd: 'stop', label: 'Dừng', icon: 'stop-circle' },
  { cmd: 'sit', label: 'Ngồi', icon: 'human-male-child' },
  { cmd: 'stand', label: 'Đứng', icon: 'human-handsup' },
  { cmd: 'greet', label: 'Chào', icon: 'hand-wave' },
];

export function ControlPanel({ visible, onClose }: Props) {
  async function fire(cmd: string) {
    try {
      await robotTrigger(cmd);
    } catch {
      /* Surface trong Chat / toast — giữ UI đơn giản */
    }
  }

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={e => e.stopPropagation()}>
          <Text style={styles.title}>Điều khiển nhanh</Text>
          <Text style={styles.hint}>
            Gửi GET /robot/trigger (cần token nếu server bật).
          </Text>
          <ScrollView contentContainerStyle={styles.grid}>
            {cmds.map(c => (
              <Pressable
                key={c.cmd}
                style={styles.btn}
                onPress={() => fire(c.cmd)}>
                <MaterialCommunityIcons
                  name={c.icon as never}
                  size={22}
                  color={colors.accent}
                />
                <Text style={styles.lbl}>{c.label}</Text>
              </Pressable>
            ))}
          </ScrollView>
          <Pressable style={styles.close} onPress={onClose}>
            <Text style={styles.closeTxt}>Đóng</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.card,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    maxHeight: '62%',
  },
  title: {
    color: colors.text,
    fontSize: font.h2,
    fontWeight: '700',
  },
  hint: { color: colors.textMuted, fontSize: font.small, marginTop: spacing.xs },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.md,
    justifyContent: 'center',
  },
  btn: {
    width: '30%',
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  lbl: { color: colors.text, fontSize: font.label, fontWeight: '600' },
  close: {
    marginTop: spacing.md,
    alignSelf: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    backgroundColor: colors.accentBg,
  },
  closeTxt: { color: colors.accent, fontWeight: '700' },
});
