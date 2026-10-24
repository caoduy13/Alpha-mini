import {BleManager} from 'react-native-ble-plx';
import {AlphaMiniBleClient, type BleEvent} from '../src/ble/manager';

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  jest.spyOn(console, 'info').mockImplementation(() => {});
});

afterEach(() => {
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.restoreAllMocks();
});

it.each([
  ['MINI_EAA014UBT00012017', null],
  ['Mini_EAA014UBT00012017', null],
  [null, 'Mini_EAA014UBT00012017'],
])('discovers robot advertisement name=%s localName=%s', async (name, localName) => {
  const ble = new BleManager();
  const events: BleEvent[] = [];
  const client = new AlphaMiniBleClient(event => events.push(event), ble);
  const scanning = client.scan();
  const callback = (ble.startDeviceScan as jest.Mock).mock.calls[0][2];
  callback(null, {id: '48:A2:48:9D:5D:60', name, localName, rssi: -54});
  client.stopScan();
  await scanning;
  expect(events.filter(event => event.type === 'device-found')).toEqual([{
    type: 'device-found',
    device: {id: '48:A2:48:9D:5D:60', name: name ?? localName, rssi: -54},
  }]);
});

it('continues rejecting unrelated names and names without the MINI_ separator', async () => {
  const ble = new BleManager();
  const events: BleEvent[] = [];
  const client = new AlphaMiniBleClient(event => events.push(event), ble);
  const scanning = client.scan();
  const callback = (ble.startDeviceScan as jest.Mock).mock.calls[0][2];
  for (const name of ['MiniSpeaker', 'OTHER_EAA014UBT00012017']) {
    callback(null, {id: 'other-device', name, rssi: -54});
  }
  client.stopScan();
  await scanning;
  expect(events.filter(event => event.type === 'device-found')).toEqual([]);
});
