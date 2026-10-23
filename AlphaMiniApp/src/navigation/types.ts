import type { NavigatorScreenParams } from '@react-navigation/native';

export type TabParamList = {
  Home: undefined;
  QRScan: undefined;
  Chat: { focusMic?: boolean } | undefined;
  History: undefined;
};

export type RootStackParamList = {
  Onboarding: undefined;
  BLEProvisioning: undefined;
  Main: NavigatorScreenParams<TabParamList>;
  Settings: undefined;
};
