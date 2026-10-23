import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, font, radius, spacing } from '../theme';

type Action = {
  key: string;
  label: string;
  sub: string;
  icon: string;
  bg: string;
  onPress: () => void;
};

export function QuickActionGrid({ actions }: { actions: Action[] }) {
  return (
    <View style={styles.grid}>
      {actions.map(a => (
        <Pressable
          key={a.key}
          onPress={a.onPress}
          style={({ pressed }) => [
            styles.cell,
            { backgroundColor: a.bg },
            pressed && styles.pressed,
          ]}>
          <MaterialCommunityIcons
            name={a.icon as never}
            size={26}
            color={colors.accent}
          />
          <Text style={styles.label}>{a.label}</Text>
          <Text style={styles.sub}>{a.sub}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  cell: {
    width: '48%',
    flexGrow: 1,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  pressed: { opacity: 0.85 },
  label: {
    color: colors.text,
    fontWeight: '700',
    fontSize: font.title,
  },
  sub: { color: colors.textMuted, fontSize: font.small },
});
