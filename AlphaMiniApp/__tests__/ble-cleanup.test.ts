import {BleManager} from 'react-native-ble-plx';
import {AlphaMiniBleClient} from '../src/ble/manager';

it('continues indication and connection cleanup when the disconnect observer throws', async () => {
  const log = jest.spyOn(console, 'info').mockImplementation(() => {});
  const disconnectionRemove = jest.fn(() => {throw new Error('observer removal failed');});
  const indicationRemove = jest.fn();
  const cancelConnection = jest.fn().mockResolvedValue(undefined);
  const client = new AlphaMiniBleClient(() => {}, new BleManager());
  Object.assign(client, {
    disconnectionSub: {remove: disconnectionRemove},
    indicationSub: {remove: indicationRemove},
    device: {id: 'cleanup-device', cancelConnection},
  });
  try {
    await client.disconnect();
    expect(disconnectionRemove).toHaveBeenCalledTimes(1);
    expect({indication: indicationRemove.mock.calls.length, connection: cancelConnection.mock.calls.length})
      .toEqual({indication: 1, connection: 1});
  } finally {
    log.mockRestore();
  }
});
