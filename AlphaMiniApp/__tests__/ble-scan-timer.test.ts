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

it('stopping a scan cancels its deadline before a second scan starts', async () => {
  const ble = new BleManager();
  const events: BleEvent[] = [];
  const client = new AlphaMiniBleClient(event => events.push(event), ble);
  const first = client.scan();
  jest.advanceTimersByTime(5000);
  client.stopScan();
  const second = client.scan();
  (ble.stopDeviceScan as jest.Mock).mockClear();
  jest.advanceTimersByTime(10000); // old deadline, second scan still has 5 seconds
  expect(ble.stopDeviceScan).not.toHaveBeenCalled();
  expect(events.filter(e => e.type === 'stage').at(-1)).toEqual({
    type: 'stage',
    stage: 'scanning',
  });
  jest.advanceTimersByTime(5000);
  expect(ble.stopDeviceScan).toHaveBeenCalledTimes(1);
  await Promise.all([first, second]);
});

it('starting a replacement scan cancels the previous scan deadline', async () => {
  const ble = new BleManager();
  const client = new AlphaMiniBleClient(() => {}, ble);
  const first = client.scan();
  jest.advanceTimersByTime(5000);
  const second = client.scan();
  (ble.stopDeviceScan as jest.Mock).mockClear();
  jest.advanceTimersByTime(10000);
  expect(ble.stopDeviceScan).not.toHaveBeenCalled();
  jest.advanceTimersByTime(5000);
  await Promise.all([first, second]);
});
