// node --test tests/  — offline queue (coche/static/outbox.js), no browser needed.
const test = require("node:test");
const assert = require("node:assert/strict");
const O = require("../coche/static/outbox.js");

function mem() { const m = new Map(); return { getItem: k => m.has(k) ? m.get(k) : null, setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) }; }
const offline = () => Object.assign(new Error("offline"), { offline: true });
const httpErr = s => Object.assign(new Error("HTTP " + s), { status: s });

test("ops persist in storage, in order", () => {
  const st = mem(), a = O.create(st);
  a.push({ kind: "close", task_id: "t1" }); a.push({ kind: "close", task_id: "t2" });
  const b = O.create(st);
  assert.deepEqual(b.list().map(o => o.task_id), ["t1", "t2"]);
  assert.ok(b.list().every(o => /^[A-Za-z0-9_-]{1,64}$/.test(o.rid)));
});

test("replay sends in order, one at a time, with the op's request id", async () => {
  const box = O.create(mem()), sent = [];
  const r1 = box.push({ kind: "close", task_id: "a" }).rid;
  box.push({ kind: "reopen", task_id: "b" });
  const res = await O.replay(box, async (m, p, b, rid) => { sent.push([m, p, rid]); return {}; });
  assert.equal(sent[0][1], "/api/coche/tasks/a/close"); assert.equal(sent[0][2], r1);
  assert.equal(sent[1][1], "/api/v1/tasks/b/reopen");
  assert.deepEqual(res, { done: 2, failed: 0 }); assert.equal(box.list().length, 0);
});

test("replay stops at the first network failure and resumes later", async () => {
  const box = O.create(mem());
  box.push({ kind: "close", task_id: "a" }); box.push({ kind: "close", task_id: "b" });
  let n = 0;
  const r1 = await O.replay(box, async () => { if (n++ === 1) throw offline(); return {}; });
  assert.deepEqual(r1, { done: 1, failed: 0 }); assert.deepEqual(box.list().map(o => o.task_id), ["b"]);
  const r2 = await O.replay(box, async () => ({}));
  assert.deepEqual(r2, { done: 1, failed: 0 }); assert.equal(box.list().length, 0);
});

test("a task added offline then completed offline: the close targets the real id", async () => {
  const box = O.create(mem()), paths = [];
  const add = box.push({ kind: "add", body: { text: "Pain" } });
  box.push({ kind: "close", task_id: O.tempId(add) });
  box.push({ kind: "reminder", task_id: O.tempId(add), body: { type: "relative", minute_offset: 30 } });
  await O.replay(box, async (m, p, b) => { paths.push([p, b]); return p.endsWith("/quick") ? { id: "REAL" } : {}; });
  assert.equal(paths[0][0], "/api/v1/tasks/quick"); assert.deepEqual(paths[0][1], { text: "Pain" });
  assert.equal(paths[1][0], "/api/coche/tasks/REAL/close");
  assert.deepEqual(paths[2], ["/api/coche/reminders", { type: "relative", minute_offset: 30, task_id: "REAL" }]);
});

test("closing a task already gone (404/409/410) counts as done; other errors are dropped and counted", async () => {
  const box = O.create(mem());
  box.push({ kind: "close", task_id: "gone" }); box.push({ kind: "add", body: { text: "" } }); box.push({ kind: "close", task_id: "ok" });
  const res = await O.replay(box, async (m, p) => { if (p.includes("gone")) throw httpErr(404); if (p.endsWith("/quick")) throw httpErr(400); return {}; });
  assert.deepEqual(res, { done: 2, failed: 1 }); assert.equal(box.list().length, 0);
});

test("cancel removes a queued op (undo while still offline)", () => {
  const box = O.create(mem()), op = box.push({ kind: "close", task_id: "a" });
  assert.equal(box.cancel(op.rid), true); assert.equal(box.list().length, 0);
});

test("applyLocal: an add shows a pending task, a close removes the task and its subtasks", () => {
  const S = { tasks: [{ id: "p" }, { id: "c", parent_id: "p" }, { id: "z" }], projects: [{ id: "inbox", is_inbox_project: true }] };
  const box = O.create(mem());
  const add = box.push({ kind: "add", body: { text: "Lait #courses", project_id: undefined, priority: 3, labels: ["x"] } });
  O.applyLocal(S, add);
  const tmp = S.tasks.find(x => x.id === O.tempId(add));
  assert.equal(tmp.content, "Lait #courses"); assert.equal(tmp.pending, true); assert.equal(tmp.project_id, "inbox"); assert.equal(tmp.priority, 3);
  O.applyLocal(S, add);                                         // idempotent (boot + load both overlay)
  assert.equal(S.tasks.filter(x => x.id === tmp.id).length, 1);
  O.applyLocal(S, box.push({ kind: "close", task_id: "p" }));
  assert.deepEqual(S.tasks.map(x => x.id).sort(), [tmp.id, "z"].sort());
});

test("server errors (5xx, 429) keep the queue: the app may be down behind the proxy", async () => {
  for (const st of [500, 502, 503, 504, 429]) {
    const box = O.create(mem());
    box.push({ kind: "close", task_id: "a" }); box.push({ kind: "add", body: { text: "x" } });
    const res = await O.replay(box, async () => { throw httpErr(st); });
    assert.deepEqual(res, { done: 0, failed: 0 }, String(st));
    assert.equal(box.list().length, 2, String(st));
  }
});
