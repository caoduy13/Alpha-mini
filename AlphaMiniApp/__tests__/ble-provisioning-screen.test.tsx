import React from 'react';
import TestRenderer, {act} from 'react-test-renderer';
import {Pressable, Text, TextInput} from 'react-native';
import {type BleError, type Device, State} from 'react-native-ble-plx';
import {BLEProvisioningScreen} from '../src/screens/BLEProvisioningScreen';
import {getBleManager} from '../src/ble/manager';

jest.mock('../src/context/AppContext', () => ({
  useApp: () => ({
    lastSSID: '',
    setLastSSID: jest.fn(async () => {}),
    setOnboardingDone: jest.fn(async () => {}),
  }),
}));
jest.mock('../src/ble/permissions', () => ({
  requestBlePermissions: jest.fn(async () => ({ok: true, missing: []})),
}));
jest.mock('react-native-safe-area-context', () => ({
  SafeAreaView: require('react-native').View,
}));
jest.mock('react-native-vector-icons/MaterialCommunityIcons', () => 'Icon');

let tree: TestRenderer.ReactTestRenderer;
let scanCallback: (error: BleError | null, device: Device | null) => void;
const ble = getBleManager();

function button(label: string) {
  const node = tree.root
    .findAllByType(Pressable)
    .find(p => p.findAllByType(Text).some(t => t.props.children === label));
  if (!node) {
    throw new Error(`Missing button: ${label}`);
  }
  return node;
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  jest.spyOn(console, 'info').mockImplementation(() => {});
  (ble.onStateChange as jest.Mock).mockImplementation(callback => {
    callback(State.PoweredOn);
    return {remove: jest.fn()};
  });
  (ble.startDeviceScan as jest.Mock).mockImplementation(
    (_uuids, _options, callback) => {
      scanCallback = callback;
    },
  );
  (ble.connectToDevice as jest.Mock).mockRejectedValue(
    new Error('mock connection failure'),
  );
});
afterEach(async () => {
  if (tree) {
    await act(async () => {
      tree.unmount();
    });
  }
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.restoreAllMocks();
});

async function openScanner() {
  await act(async () => {
    tree = TestRenderer.create(
      <BLEProvisioningScreen
        navigation={{goBack: jest.fn(), reset: jest.fn()} as never}
        route={{key: 'ble', name: 'BLEProvisioning'} as never}
      />,
    );
  });
  await act(async () => {
    jest.advanceTimersByTime(450);
  });
  expect(ble.startDeviceScan).toHaveBeenCalledTimes(1);
}

it('the scan-again button starts exactly one scan', async () => {
  await openScanner();
  (ble.startDeviceScan as jest.Mock).mockClear();
  await act(async () => {
    button('Qu\u00e9t l\u1ea1i').props.onPress();
  });
  expect(ble.startDeviceScan).toHaveBeenCalledTimes(1);
});

it('retrying failed provisioning starts exactly one scan', async () => {
  await openScanner();
  await act(async () => {
    scanCallback(null, {id: 'robot-1', name: 'MINI_TEST', rssi: -40} as Device);
  });
  await act(async () => {
    button('MINI_TEST').props.onPress();
  });
  await act(async () => {
    tree.root.findAllByType(TextInput)[0].props.onChangeText('test-network');
  });
  await act(async () => {
    button('G\u1eedi cho robot').props.onPress();
  });
  (ble.startDeviceScan as jest.Mock).mockClear();
  await act(async () => {
    button('Th\u1eed l\u1ea1i').props.onPress();
  });
  expect(ble.startDeviceScan).toHaveBeenCalledTimes(1);
});

it('shows a scan error and keeps the existing scan-again action usable', async () => {
  await openScanner();
  await act(async () => {
    scanCallback(
      Object.assign(new Error('Bluetooth scan unavailable'), {
        errorCode: 102,
      }) as BleError,
      null,
    );
  });
  expect(
    tree.root
      .findAllByType(Text)
      .some(t => t.props.children === 'Bluetooth scan unavailable'),
  ).toBe(true);
  (ble.startDeviceScan as jest.Mock).mockClear();
  await act(async () => {
    button('Qu\u00e9t l\u1ea1i').props.onPress();
  });
  expect(ble.startDeviceScan).toHaveBeenCalledTimes(1);
  expect(
    tree.root
      .findAllByType(Text)
      .some(t => t.props.children === 'Bluetooth scan unavailable'),
  ).toBe(false);
});
