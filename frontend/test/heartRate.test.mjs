import test from "node:test";
import assert from "node:assert/strict";
import { parseHeartRate, isWebBluetoothAvailable } from "../src/lib/heartRate.ts";

const view = (...bytes) => new DataView(new Uint8Array(bytes).buffer);

test("parseHeartRate reads the 8-bit format when flag bit 0 is clear", () => {
  assert.equal(parseHeartRate(view(0x00, 72)), 72);
});

test("parseHeartRate reads the 16-bit little-endian format when flag bit 0 is set", () => {
  // 0x012C little-endian = 300
  assert.equal(parseHeartRate(view(0x01, 0x2c, 0x01)), 300);
});

test("parseHeartRate ignores other flag bits (sensor contact, energy expended)", () => {
  // 0x06 = sensor contact bits set, bit 0 clear -> still 8-bit
  assert.equal(parseHeartRate(view(0x06, 95)), 95);
  // 0x17 = bit 0 set plus other bits -> 16-bit
  assert.equal(parseHeartRate(view(0x17, 0x50, 0x00)), 80);
});

test("parseHeartRate handles the 8-bit boundary values", () => {
  assert.equal(parseHeartRate(view(0x00, 0)), 0);
  assert.equal(parseHeartRate(view(0x00, 255)), 255);
});

test("parseHeartRate throws on a truncated 16-bit packet", () => {
  assert.throws(() => parseHeartRate(view(0x01, 0x2c)), RangeError);
});

test("isWebBluetoothAvailable is false outside a browser", () => {
  assert.equal(isWebBluetoothAvailable(), false);
});
