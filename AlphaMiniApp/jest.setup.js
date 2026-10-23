import 'react-native-gesture-handler/jestSetup';
import { Buffer } from 'buffer';

global.Buffer = Buffer;

jest.mock('react-native-reanimated', () =>
  require('react-native-reanimated/mock'),
);

jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(() => Promise.resolve(null)),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
    getMany: jest.fn(async keys => {
      const o = {};
      for (const k of keys) {
        if (k === 'alphamini_onboarding_done') {
          o[k] = 'true';
        } else {
          o[k] = null;
        }
      }
      return o;
    }),
    setMany: jest.fn(() => Promise.resolve()),
    clear: jest.fn(() => Promise.resolve()),
    getAllKeys: jest.fn(() => Promise.resolve([])),
  },
}));

jest.mock('@react-native-clipboard/clipboard', () => ({
  __esModule: true,
  default: {
    setString: jest.fn(() => Promise.resolve()),
    getString: jest.fn(() => Promise.resolve('')),
    hasString: jest.fn(() => Promise.resolve(false)),
  },
}));

jest.mock('react-native-screens', () => {
  const { View } = require('react-native');
  return {
    enableScreens: jest.fn(),
    Screen: View,
    ScreenContainer: View,
    NativeScreen: View,
    ScreenStack: View,
    ScreenStackHeaderConfig: View,
    ScreenStackHeaderSubview: View,
    ScreenStackHeaderLeftView: View,
    ScreenStackHeaderRightView: View,
    ScreenStackHeaderCenterView: View,
    ScreenStackHeaderSearchBarView: View,
    FullWindowOverlay: View,
    SearchBar: View,
    useTransitionProgress: () => ({ progress: { value: 0 } }),
  };
});

jest.mock('react-native-vision-camera', () => {
  const { View } = require('react-native');
  return {
    Camera: View,
    useCameraDevice: jest.fn(() => ({ id: 'back', formats: [] })),
    useCameraPermission: jest.fn(() => ({
      hasPermission: true,
      requestPermission: jest.fn(),
    })),
    usePreviewOutput: jest.fn(() => ({})),
    useObjectOutput: jest.fn(() => ({})),
    isScannedCode: jest.fn(() => false),
  };
});

jest.mock('react-native-audio-recorder-player', () => ({
  __esModule: true,
  default: jest.fn().mockImplementation(() => ({
    startRecorder: jest.fn(() => Promise.resolve()),
    stopRecorder: jest.fn(() => Promise.resolve('file:///mock.wav')),
    startPlayer: jest.fn(),
    stopPlayer: jest.fn(),
  })),
}));

jest.mock('react-native-ble-plx', () => {
  class Subscription {
    remove() {}
  }
  return {
    BleManager: jest.fn().mockImplementation(() => ({
      startDeviceScan: jest.fn(),
      stopDeviceScan: jest.fn(),
      connectToDevice: jest.fn(() =>
        Promise.reject(new Error('mock BLE — no device')),
      ),
      state: jest.fn(() => Promise.resolve('PoweredOn')),
      onStateChange: jest.fn(() => new Subscription()),
    })),
    State: { PoweredOn: 'PoweredOn' },
  };
});
