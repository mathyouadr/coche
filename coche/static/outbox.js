/* Coche offline queue: completing, reopening and Quick Add keep working without the server.
   Each op is stored (localStorage "coche-outbox"), shown at once (applyLocal) and replayed in order when the
   server answers again. Every op carries a request id sent as X-Request-Id, so a replay after a lost answer
   never runs twice (the server remembers ids for 30 days). Plain script: window.CocheOutbox, or require() in node. */
(function (root) {
  "use strict";
  const KEY = "coche-outbox";
  const GONE = new Set([404, 409, 410]);

  const newRid = () => "op-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  const tempId = op => "tmp-" + op.rid;
  const isTemp = id => typeof id === "string" && id.startsWith("tmp-");

  function create(storage) {
    const read = () => { try { const v = JSON.parse(storage.getItem(KEY) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; } };
    const write = ops => { try { if (ops.length) storage.setItem(KEY, JSON.stringify(ops)); else storage.removeItem(KEY); } catch (e) { /* quota */ } };
    return {
      list: read,
      push(op) { const o = Object.assign({ rid: newRid(), at: Date.now() }, op); write(read().concat([o])); return o; },
      remove(rid) { write(read().filter(o => o.rid !== rid)); },
      cancel(rid) { const ops = read(), left = ops.filter(o => o.rid !== rid); write(left); return left.length !== ops.length; },
      // A temporary id became real: rewrite the ops that still point to it.
      resolve(tmp, real) { write(read().map(o => o.task_id === tmp ? Object.assign({}, o, { task_id: real }) : o)); },
      clear() { write([]); },
    };
  }

  function request(op) {
    switch (op.kind) {
      case "add": return ["POST", "/api/v1/tasks/quick", op.body];
      case "close": return ["POST", `/api/coche/tasks/${op.task_id}/close`, {}];
      case "reopen": return ["POST", `/api/v1/tasks/${op.task_id}/reopen`, {}];
      case "reminder": return ["POST", "/api/coche/reminders", Object.assign({}, op.body, { task_id: op.task_id })];
      default: return null;
    }
  }

  /* send(method, path, body, rid) resolves with the JSON answer; it throws an error with .offline (no answer)
     or .status (HTTP error). Stops at the first network failure; the rest waits for the next replay. */
  async function replay(box, send) {
    let done = 0, failed = 0;
    for (;;) {
      const op = box.list()[0];
      if (!op) break;
      const req = request(op);
      if (!req || isTemp(op.task_id)) { box.remove(op.rid); failed++; continue; }   // unknown op, or its add failed
      try {
        const out = await send(req[0], req[1], req[2], op.rid);
        if (op.kind === "add" && out && out.id) box.resolve(tempId(op), out.id);
        done++;
      } catch (e) {
        // no answer, or the server (or the proxy in front of it) is down / busy: keep everything for later
        if (!e || e.offline || !e.status || e.status >= 500 || e.status === 429) return { done, failed };
        if (!(GONE.has(e.status) && (op.kind === "close" || op.kind === "reopen"))) failed++; else done++;
        if (op.kind === "add") box.list().filter(o => o.task_id === tempId(op)).forEach(o => box.remove(o.rid));
      }
      box.remove(op.rid);
    }
    return { done, failed };
  }

  /* Show an op in the app state S before the server has it. Safe to apply twice. */
  function applyLocal(S, op) {
    if (op.kind === "add") {
      const id = tempId(op);
      if (S.tasks.some(x => x.id === id)) return;
      const b = op.body || {}, inbox = (S.projects || []).find(p => p.is_inbox_project) || (S.projects || [])[0] || {};
      const due = b.due_date ? { date: b.due_time ? `${b.due_date}T${b.due_time}:00` : b.due_date, string: b.due_date, is_recurring: false } : null;
      S.tasks.push({ id, content: b.text || "", description: b.description || "", project_id: b.project_id || inbox.id,
        section_id: b.section_id || null, parent_id: b.parent_id || null, priority: b.priority || 1, labels: b.labels || [],
        due, deadline: null, child_order: 1e9 + (op.at || 0) / 1e6, added_at: new Date(op.at || Date.now()).toISOString(),
        checked: false, is_deleted: false, comment_count: 0, pending: true });
    } else if (op.kind === "close") {
      const gone = new Set([op.task_id]); let grew = true;
      while (grew) { grew = false; for (const x of S.tasks) if (x.parent_id && gone.has(x.parent_id) && !gone.has(x.id)) { gone.add(x.id); grew = true; } }
      S.tasks = S.tasks.filter(x => !gone.has(x.id));
    }
  }

  const api = { KEY, create, replay, applyLocal, request, newRid, tempId, isTemp };
  root.CocheOutbox = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
