import test from "node:test";
import assert from "node:assert/strict";

function parseHeartRate(value) {
  const flags = value.getUint8(0);
  return flags & 0x01 ? value.getUint16(1, /* littleEndian */ true) : value.getUint8(1);
}

test("parseHeartRate parses 8-bit heart rate format", () => {
  const buffer = new Uint8Array([0x00, 72]).buffer;
  const view = new DataView(buffer);
  assert.equal(parseHeartRate(view), 72);
});

test("parseHeartRate parses 16-bit heart rate format", () => {
  // 0x01 flag indicates 16-bit format, 0x012C in little-endian is [0x2C, 0x01] = 300
  const buffer = new Uint8Array([0x01, 0x2C, 0x01]).buffer;
  const view = new DataView(buffer);
  assert.equal(parseHeartRate(view), 300);
});
