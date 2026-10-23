import Clipboard from '@react-native-clipboard/clipboard';
import { useNavigation } from '@react-navigation/native';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { getRobotScan, postRobotReconnect } from '../api/endpoints';
import { useApp } from '../context/AppContext';
import { useSettings } from '../hooks/useSettings';
import { colors, font, radius, spacing } from '../theme';
import { StepRow } from './StepRow';

type Props = {
  compact?: boolean;
  autoRun?: boolean;
};

function shortUrl(raw: string): string {
  const t = raw.trim();
  if (!t) {
    return 'Chưa cấu hình';
  }
  try {
    const u = new URL(/^https?:\/\//i.test(t) ? t : `http://${t}`);
    return u.host;
  } catch {
    return t.length > 36 ? `${t.slice(0, 33)}…` : t;
  }
}

export function ConnectionPanel({ compact = false, autoRun = false }: Props) {
  const navigation = useNavigation();
  const { prefs } = useSettings();
  const {
    connection,
    connect,
    cancelConnect,
    disconnect,
    refreshConnection,
  } = useApp();

  const [expanded, setExpanded] = useState(!compact);
  const [techOpen, setTechOpen] = useState(false);
  const autoStarted = useRef(false);
  const connectionRef = useRef(connection);
  connectionRef.current = connection;

  useEffect(() => {
    if (!autoRun) {
      return;
    }
    if (!prefs.serverUrl?.trim()) {
      return;
    }
    const tid = setTimeout(() => {
      if (autoStarted.current) {
        return;
      }
      if (connectionRef.current.status === 'success') {
        autoStarted.current = true;
        return;
      }
      autoStarted.current = true;
      void connect();
    }, 450);
    return () => clearTimeout(tid);
  }, [autoRun, connect, prefs.serverUrl]);

  const serverLine = shortUrl(prefs.serverUrl);

  const failedStep = connection.steps.find(
    s => s.id === connection.failedStepId,
  );
  const userHint =
    failedStep?.error?.fixHint ?? failedStep?.error?.message ?? '';

  const onRescan = useCallback(async () => {
    try {
      await getRobotScan();
    } catch {
      /* ignore */
    }
    void connect();
  }, [connect]);

  const onReconnectOnly = useCallback(async () => {
    try {
      await postRobotReconnect();
    } catch {
      /* ignore */
    }
    void connect();
  }, [connect]);

  const copyTech = useCallback(() => {
    const lines: string[] = [];
    lines.push(`status=${connection.status}`);
    if (failedStep?.error) {
      lines.push(`kind=${failedStep.error.kind}`);
      lines.push(`message=${failedStep.error.message}`);
      lines.push(`detail=${failedStep.error.detail}`);
    }
    if (failedStep?.endpoint) {
      lines.push(`endpoint=${failedStep.endpoint}`);
    }
    void Clipboard.setString(lines.join('\n'));
  }, [connection.status, failedStep]);

  const summaryLine = (() => {
    const s = connection.summary;
    if (!s?.serverIp) {
      return '';
    }
    const pin =
      s.battery != null && !Number.isNaN(s.battery)
        ? ` · pin ${s.battery}%`
        : '';
    const mood = s.mood ? ` · ${s.mood}` : '';
    const rip = s.robotIp ? `Robot ${s.robotIp}` : '';
    return `${rip}${pin}${mood}`.trim();
  })();

  const compactSummary = (() => {
    if (connection.status === 'success' && connection.summary) {
      const pin =
        connection.summary.battery != null &&
        !Number.isNaN(connection.summary.battery)
          ? ` · pin ${connection.summary.battery}%`
          : '';
      const rip = connection.summary.robotIp
        ? `Robot ${connection.summary.robotIp}`
        : '';
      return `🟢 Sẵn sàng · ${rip}${pin}`.trim();
    }
    if (connection.status === 'running') {
      return '🟡 Đang kết nối…';
    }
    if (connection.status === 'failed') {
      return '🔴 Không kết nối được';
    }
    return '⚪ Chưa kết nối';
  })();

  if (compact && !expanded) {
    return (
      <Pressable
        style={styles.compactBar}
        onPress={() => setExpanded(true)}
        accessibilityRole="button">
        <Text style={styles.compactTxt} numberOfLines={2}>
          {compactSummary}
        </Text>
        <Pressable
          onPress={e => {
            e.stopPropagation?.();
            void refreshConnection();
          }}
          hitSlop={10}
          style={styles.refreshMini}>
          <Text style={styles.refreshMiniTxt}>Refresh</Text>
        </Pressable>
      </Pressable>
    );
  }

  const showRescan =
    connection.failedStepId === 'connectRobot' ||
    connection.failedStepId === 'robotRegistered';
  const showReconnectBtn =
    connection.failedStepId === 'robotState' ||
    connection.failedStepId === 'connectRobot';

  const body = (
    <View style={styles.card}>
      {connection.status === 'idle' ? (
        <>
          <Text style={styles.title}>Kết nối Alpha Mini</Text>
          <Text style={styles.sub}>Server: {serverLine}</Text>
          <Pressable
            style={styles.linkBtn}
            onPress={() => navigation.navigate('Settings' as never)}>
            <Text style={styles.linkTxt}>Đổi server</Text>
          </Pressable>
          <Pressable style={styles.btnPrimary} onPress={() => void connect()}>
            <Text style={styles.btnPrimaryTxt}>Kết nối</Text>
          </Pressable>
        </>
      ) : null}

      {connection.status === 'running' ? (
        <>
          <Text style={styles.title}>Đang kết nối…</Text>
          {connection.steps.map(st => (
            <StepRow key={st.id} step={st} />
          ))}
          <Pressable style={styles.btnOutline} onPress={cancelConnect}>
            <Text style={styles.btnOutlineTxt}>Huỷ</Text>
          </Pressable>
        </>
      ) : null}

      {connection.status === 'failed' ? (
        <>
          <Text style={styles.titleFail}>🔴 Không kết nối được</Text>
          {connection.steps.map(st => (
            <StepRow key={st.id} step={st} />
          ))}
          {userHint ? <Text style={styles.hint}>{userHint}</Text> : null}
          <View style={styles.rowBtns}>
            {showRescan ? (
              <Pressable style={styles.btnOutline} onPress={() => void onRescan()}>
                <Text style={styles.btnOutlineTxt}>Quét lại</Text>
              </Pressable>
            ) : null}
            {showReconnectBtn ? (
              <Pressable
                style={styles.btnOutline}
                onPress={() => void onReconnectOnly()}>
                <Text style={styles.btnOutlineTxt}>Reconnect</Text>
              </Pressable>
            ) : null}
            <Pressable style={styles.btnOutline} onPress={() => void connect()}>
              <Text style={styles.btnOutlineTxt}>Thử lại</Text>
            </Pressable>
          </View>
          <Pressable onPress={() => setTechOpen(t => !t)}>
            <Text style={styles.techToggle}>
              Chi tiết kỹ thuật {techOpen ? '▾' : '▸'}
            </Text>
          </Pressable>
          {techOpen && failedStep ? (
            <View style={styles.techBox}>
              <Text style={styles.mono} selectable>
                {failedStep.error?.kind ? `kind: ${failedStep.error.kind}\n` : ''}
                {failedStep.endpoint ? `URL: ${failedStep.endpoint}\n` : ''}
                {failedStep.error?.detail ?? ''}
              </Text>
              <Pressable style={styles.btnOutline} onPress={copyTech}>
                <Text style={styles.btnOutlineTxt}>Copy log</Text>
              </Pressable>
            </View>
          ) : null}
        </>
      ) : null}

      {connection.status === 'success' ? (
        <>
          <Text style={styles.titleOk}>🟢 Sẵn sàng</Text>
          {summaryLine ? (
            <Text style={styles.sub}>{summaryLine}</Text>
          ) : null}
          <View style={styles.rowBtns}>
            <Pressable style={styles.btnOutline} onPress={disconnect}>
              <Text style={styles.btnOutlineTxt}>Ngắt kết nối</Text>
            </Pressable>
            <Pressable
              style={styles.btnOutline}
              onPress={() => void refreshConnection()}>
              <Text style={styles.btnOutlineTxt}>Refresh</Text>
            </Pressable>
          </View>
          <Pressable onPress={() => setTechOpen(t => !t)}>
            <Text style={styles.techToggle}>Chi tiết {techOpen ? '▾' : '▸'}</Text>
          </Pressable>
          {techOpen ? (
            <View style={styles.techBox}>
              {connection.steps.map(st => (
                <StepRow key={st.id} step={st} />
              ))}
            </View>
          ) : null}
        </>
      ) : null}

      {compact ? (
        <Pressable onPress={() => setExpanded(false)}>
          <Text style={styles.collapseTxt}>Thu gọn</Text>
        </Pressable>
      ) : null}
    </View>
  );

  if (compact && expanded) {
    return <View style={styles.wrap}>{body}</View>;
  }

  return <View style={styles.wrap}>{body}</View>;
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  compactBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  compactTxt: { flex: 1, color: colors.text, fontSize: font.body, fontWeight: '600' },
  refreshMini: { paddingVertical: spacing.xs, paddingHorizontal: spacing.sm },
  refreshMiniTxt: { color: colors.accent, fontWeight: '700', fontSize: font.small },
  title: { color: colors.text, fontSize: font.title, fontWeight: '700' },
  titleOk: { color: colors.success, fontSize: font.title, fontWeight: '700' },
  titleFail: { color: colors.error, fontSize: font.title, fontWeight: '700' },
  sub: { color: colors.textMuted, fontSize: font.body },
  linkBtn: { alignSelf: 'flex-start' },
  linkTxt: { color: colors.accent, fontWeight: '600', fontSize: font.body },
  hint: { color: colors.textMuted, fontSize: font.body, lineHeight: 20 },
  rowBtns: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  btnPrimary: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  btnPrimaryTxt: { color: colors.text, fontWeight: '700', fontSize: font.body },
  btnOutline: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.accentBg,
  },
  btnOutlineTxt: { color: colors.accent, fontWeight: '600', fontSize: font.body },
  techToggle: { color: colors.textMuted, fontSize: font.small, marginTop: spacing.xs },
  techBox: { gap: spacing.sm, marginTop: spacing.xs },
  mono: {
    color: colors.textMuted,
    fontSize: font.small,
    fontFamily: 'monospace',
  },
  collapseTxt: {
    color: colors.textMuted,
    fontSize: font.small,
    textAlign: 'center',
    marginTop: spacing.xs,
  },
});
