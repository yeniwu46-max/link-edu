import test from 'node:test';
import assert from 'node:assert/strict';
import { MotionTaskClient } from '../src/services/motionTaskClient.js';

test('a superseded initialization cannot terminate the new worker', async () => {
  const workers = [], statuses = [];
  const client = new MotionTaskClient(() => {
    const worker = { postMessage() {}, terminate() { this.terminated = true; } };
    workers.push(worker); return worker;
  }, status => statuses.push(status));
  const first = client.start(), second = client.start();
  workers[1].onmessage({data: {type: 'ready'}});
  await Promise.all([first, second]);
  assert.equal(client.ready, true);
  assert.equal(workers[1].terminated, undefined);
  assert.equal(statuses.at(-1), 'ready');
  client.stop();
});

test('pending frames time out and stop releases the active request', async () => {
  const client = new MotionTaskClient(() => ({ postMessage() {}, terminate() {} }), () => {});
  client.worker = client.factory();
  await assert.rejects(client.request({time: 1}, [], 5), /timed out/);
  const request = client.request({time: 2});
  client.stop();
  await assert.rejects(request, /stopped/);
  assert.equal(client.worker, null);
});

test('worker construction failure reports unavailable instead of loading forever', async () => {
  const statuses = [];
  const client = new MotionTaskClient(() => { throw new Error('blocked'); }, s => statuses.push(s));
  await client.start();
  assert.equal(client.ready, false);
  assert.equal(statuses.at(-1), 'failed');
});
