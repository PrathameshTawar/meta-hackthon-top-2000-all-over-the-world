// Standard Bluetooth Heart Rate Service (0x180D) / Measurement (0x2A37)
export function parseHeartRate(value: DataView): number {
  const flags = value.getUint8(0);
  return flags & 0x01 ? value.getUint16(1, /* littleEndian */ true) : value.getUint8(1);
}

export function isWebBluetoothAvailable(): boolean {
  return typeof navigator !== "undefined" && "bluetooth" in navigator && typeof window !== "undefined" && window.isSecureContext;
}

export async function connectHeartRate(
  onReading: (bpm: number) => void,
  onDisconnect: () => void,
): Promise<{ deviceName: string; disconnect: () => void }> {
  const device = await (navigator as any).bluetooth.requestDevice({
    filters: [{ services: ["heart_rate"] }],
  });
  device.addEventListener("gattserverdisconnected", onDisconnect);
  const server = await device.gatt.connect();
  const service = await server.getPrimaryService("heart_rate");
  const characteristic = await service.getCharacteristic("heart_rate_measurement");
  characteristic.addEventListener("characteristicvaluechanged", (e: Event) => {
    const dv = (e.target as any).value as DataView;
    onReading(parseHeartRate(dv));
  });
  await characteristic.startNotifications();
  return { deviceName: device.name ?? "Watch", disconnect: () => device.gatt.disconnect() };
}
