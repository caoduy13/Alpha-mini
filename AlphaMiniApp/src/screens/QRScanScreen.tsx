import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { launchImageLibrary } from 'react-native-image-picker';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import {
  postChat,
  postQrDecodeFile,
  postRobotQrFromCamera,
} from '../api/endpoints';
import { CameraPreview } from '../components/CameraPreview';
import { PhoneQRScanner } from '../components/PhoneQRScanner';
import { QRResultCard, QRResultVM } from '../components/QRResultCard';
import { useApp } from '../context/AppContext';
import { useSettings } from '../hooks/useSettings';
import type { CompositeNavigationProp } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import type { RootStackParamList, TabParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';

type TabKey = 'robot' | 'phone' | 'upload';
type Nav = CompositeNavigationProp<
  BottomTabNavigationProp<TabParamList, 'QRScan'>,
  NativeStackNavigationProp<RootStackParamList>
>;

export function QRScanScreen() {
  const navigation = useNavigation<Nav>();
  const { state } = useApp();
  const { prefs, persist } = useSettings();

  const [seg, setSeg] = useState<TabKey>('robot');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<QRResultVM | null>(null);

  const [uploadUri, setUploadUri] = useState<string | null>(null);

  const phoneActive = seg === 'phone' && !result;

  const scanRobot = useCallback(async () => {
    setBusy(true);
    setResult(null);
    try {
      const data = await postRobotQrFromCamera(prefs.autoChatGemini);
      if (!data.ok) {
        setResult({
          ok: false,
          message: data.reply || data.error || 'Quét thất bại',
        });
        return;
      }
      const text = data.qr_text || data.codes?.[0]?.text || '';
      setResult({
        ok: true,
        text,
        format: data.codes?.[0]?.format,
        reply: data.reply,
        fed_to_chat: data.fed_to_chat,
        duplicate: data.duplicate,
      });
    } catch (e) {
      setResult({
        ok: false,
        message: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }, [prefs.autoChatGemini]);

  const onPhoneCode = useCallback(
    async (text: string) => {
      try {
        if (prefs.autoChatGemini) {
          const res = await postChat(
            `QR Code: ${text}`,
            prefs.robotSpeakReplies,
          );
          setResult({
            ok: true,
            text,
            format: 'QR',
            reply: res.reply,
            fed_to_chat: true,
          });
        } else {
          setResult({ ok: true, text, format: 'QR' });
        }
      } catch (e) {
        setResult({
          ok: false,
          message: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [prefs.autoChatGemini, prefs.robotSpeakReplies],
  );

  const pickImage = useCallback(async () => {
    const r = await launchImageLibrary({ mediaType: 'photo', quality: 0.9 });
    const uri = r.assets?.[0]?.uri;
    if (uri) {
      setUploadUri(uri);
      setResult(null);
    }
  }, []);

  const decodeUpload = useCallback(async () => {
    if (!uploadUri) {
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const data = await postQrDecodeFile(uploadUri);
      if (!data.ok || !data.codes?.length) {
        setResult({
          ok: false,
          message: data.reply || 'Không thấy QR trong ảnh',
        });
        return;
      }
      const text = data.codes[0].text;
      if (prefs.autoChatGemini) {
        const res = await postChat(
          `QR Code: ${text}`,
          prefs.robotSpeakReplies,
        );
        setResult({
          ok: true,
          text,
          format: data.codes[0].format,
          reply: res.reply,
          fed_to_chat: true,
        });
      } else {
        setResult({
          ok: true,
          text,
          format: data.codes[0].format,
          reply: data.reply,
        });
      }
    } catch (e) {
      setResult({
        ok: false,
        message: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }, [uploadUri, prefs.autoChatGemini, prefs.robotSpeakReplies]);

  const segBtn = (key: TabKey, label: string, icon: string) => {
    const on = seg === key;
    return (
      <Pressable
        key={key}
        onPress={() => {
          setSeg(key);
          setResult(null);
        }}
        style={[styles.seg, on && styles.segOn]}>
        <MaterialCommunityIcons
          name={icon as never}
          size={18}
          color={on ? colors.accent : colors.textMuted}
        />
        <Text style={[styles.segTxt, on && styles.segTxtOn]}>{label}</Text>
      </Pressable>
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => navigation.navigate('Home')} hitSlop={12}>
          <MaterialCommunityIcons name="arrow-left" size={24} color={colors.text} />
        </Pressable>
        <Text style={styles.screenTitle}>Quét QR</Text>
        <Pressable onPress={() => navigation.navigate('History')} hitSlop={12}>
          <MaterialCommunityIcons name="history" size={22} color={colors.accent} />
        </Pressable>
      </View>

      <View style={styles.segRow}>
        {segBtn('robot', 'Robot', 'robot')}
        {segBtn('phone', 'Camera', 'cellphone')}
        {segBtn('upload', 'Upload', 'upload')}
      </View>

      <View style={styles.opts}>
        <Text style={styles.optLabel}>Auto-chat Gemini</Text>
        <Switch
          value={prefs.autoChatGemini}
          onValueChange={v => persist({ autoChatGemini: v })}
          thumbColor={colors.text}
          trackColor={{ false: colors.border, true: colors.accent }}
        />
        <Text style={styles.optLabel}>Robot TTS</Text>
        <Switch
          value={prefs.robotSpeakReplies}
          onValueChange={v => persist({ robotSpeakReplies: v })}
          thumbColor={colors.text}
          trackColor={{ false: colors.border, true: colors.success }}
        />
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        {seg === 'robot' ? (
          <>
            <CameraPreview robotOnline={state.robotOnline} pollMs={1500} height={260} />
            <Pressable
              style={[styles.primaryBtn, busy && styles.disabled]}
              disabled={busy}
              onPress={scanRobot}>
              {busy ? (
                <ActivityIndicator color={colors.text} />
              ) : (
                <Text style={styles.primaryTxt}>Quét QR từ camera robot</Text>
              )}
            </Pressable>
          </>
        ) : null}

        {seg === 'phone' ? (
          <>
            <PhoneQRScanner active={phoneActive} onCode={onPhoneCode} />
            {result ? (
              <Pressable
                style={styles.secondaryBtn}
                onPress={() => setResult(null)}>
                <Text style={styles.secondaryTxt}>Quét tiếp</Text>
              </Pressable>
            ) : null}
          </>
        ) : null}

        {seg === 'upload' ? (
          <>
            <Pressable style={styles.secondaryBtn} onPress={pickImage}>
              <Text style={styles.secondaryTxt}>Chọn ảnh</Text>
            </Pressable>
            {uploadUri ? (
              <Text style={styles.uriHint} numberOfLines={2}>
                {uploadUri}
              </Text>
            ) : null}
            <Pressable
              style={[styles.primaryBtn, (!uploadUri || busy) && styles.disabled]}
              disabled={!uploadUri || busy}
              onPress={decodeUpload}>
              {busy ? (
                <ActivityIndicator color={colors.text} />
              ) : (
                <Text style={styles.primaryTxt}>Decode</Text>
              )}
            </Pressable>
          </>
        ) : null}

        <QRResultCard result={result} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  screenTitle: { color: colors.text, fontSize: font.title, fontWeight: '700' },
  segRow: {
    flexDirection: 'row',
    marginHorizontal: spacing.md,
    gap: spacing.xs,
    backgroundColor: colors.card,
    padding: spacing.xs,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  seg: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  segOn: { backgroundColor: colors.surface },
  segTxt: { color: colors.textMuted, fontSize: font.label },
  segTxtOn: { color: colors.text, fontWeight: '600' },
  opts: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  optLabel: { color: colors.textMuted, fontSize: font.small },
  body: { padding: spacing.md, paddingBottom: spacing.xxl, gap: spacing.md },
  primaryBtn: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  primaryTxt: { color: colors.text, fontWeight: '700', fontSize: font.body },
  secondaryBtn: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accentBg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  secondaryTxt: { color: colors.accent, fontWeight: '600' },
  uriHint: { color: colors.textMuted, fontSize: font.small },
  disabled: { opacity: 0.5 },
});
