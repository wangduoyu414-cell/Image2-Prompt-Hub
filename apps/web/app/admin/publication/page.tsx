"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  type AdminSession,
  type PublicationAdminStatus,
  activatePublicationV2,
  buildPublicationV2,
  getAdminSession,
  getPublicationV2Status,
  recordTakedownV2,
  rollbackPublicationV2,
} from "@/lib/admin";

export default function PublicationAdminPage() {
  const [session, setSession] = useState<AdminSession | null>(null);
  const [status, setStatus] = useState<PublicationAdminStatus | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [versionId, setVersionId] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [nextSession, nextStatus] = await Promise.all([getAdminSession(), getPublicationV2Status()]);
    setSession(nextSession); setStatus(nextStatus);
  }, []);
  useEffect(() => { refresh().catch((cause) => setError(cause instanceof Error ? cause.message : "读取失败")); }, [refresh]);

  async function run(action: () => Promise<Record<string, unknown>>) {
    if (!session) return;
    setBusy(true); setError(""); setMessage("");
    try { const result = await action(); setMessage(JSON.stringify(result)); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "操作失败"); }
    finally { setBusy(false); }
  }

  async function takedown(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    const data = new FormData(event.currentTarget);
    await run(() => recordTakedownV2({
      idempotency_key: String(data.get("idempotency_key")), scope_type: String(data.get("scope_type")),
      scope_key: String(data.get("scope_key")), action: String(data.get("action")),
      reason_code: String(data.get("reason_code")), evidence_url: String(data.get("evidence_url")), note: String(data.get("note")),
    }, session.csrf_token));
  }

  if (!session) return <main className="admin-shell"><section className="admin-login-card"><h1>需要先登录</h1><p>请从审核队列登录，再进入发布控制台。</p><Link href="/admin/review">前往登录</Link>{error ? <p className="admin-error">{error}</p> : null}</section></main>;
  if (session.user.role !== "admin") return <main className="admin-shell"><section className="admin-login-card"><h1>仅管理员可操作发布</h1><p>当前身份 {session.user.username} / {session.user.role} 仍可在审核队列完成权利审核，但不能构建、激活、回滚或下架。</p><Link href="/admin/review">返回审核队列</Link></section></main>;

  const current = status?.current ?? {};
  return <main className="admin-shell"><header className="admin-queue-header"><div><p className="eyebrow">PUBLICATION V2 CONTROL</p><h1>发布与下架控制台</h1><p>所有操作使用最新固定 revision、最新审核和当前下架时间线；不会修改历史版本或 v1 current。</p></div><div><strong>{session.user.username}</strong><span>ADMIN</span></div></header>
    <nav className="breadcrumb"><Link href="/admin/review">审核队列</Link><span>/</span><span>发布控制台</span></nav>
    <section className="admin-evidence-card"><h2>当前状态</h2><pre>{JSON.stringify(current, null, 2)}</pre><h3>构建使用的最新 Revision</h3><pre>{JSON.stringify(status?.revision_selection ?? {}, null, 2)}</pre></section>
    <section className="admin-review-authority"><h2>版本操作</h2><div className="admin-actions"><button disabled={busy} onClick={() => run(() => buildPublicationV2(`web-build-${crypto.randomUUID()}`, session.csrf_token))}>构建新 Publication v2</button><input min="1" onChange={(event) => setVersionId(event.target.value)} placeholder="版本 ID" type="number" value={versionId} /><button disabled={busy || !versionId} onClick={() => run(() => activatePublicationV2(Number(versionId), session.csrf_token))}>激活版本</button><button disabled={busy || !versionId} onClick={() => run(() => rollbackPublicationV2(Number(versionId), session.csrf_token))}>回滚到版本</button></div></section>
    <form className="admin-review-authority" onSubmit={takedown}><h2>下架 / 恢复</h2><p>case key 使用 source_id:source_case_key，Prompt key 使用 source_id:prompt_id，asset 使用 SHA-256。</p><div className="admin-form-grid"><label>幂等键<input name="idempotency_key" required /></label><label>范围<select name="scope_type"><option value="case">case</option><option value="asset">asset</option><option value="prompt">prompt</option><option value="source">source</option></select></label><label>动作<select name="action"><option value="remove">remove</option><option value="restore">restore</option></select></label><label>范围键<input name="scope_key" required /></label><label>原因码<input name="reason_code" required /></label><label>证据 URL<input name="evidence_url" required type="url" /></label></div><label>处理说明<textarea name="note" required rows={4} /></label><button disabled={busy} type="submit">记录不可变事件</button></form>
    <section className="admin-evidence-card"><h2>下架时间线（最近 100 条）</h2><pre>{JSON.stringify(status?.takedowns ?? {}, null, 2)}</pre></section>
    {message ? <p className="admin-success">{message}</p> : null}{error ? <p className="admin-error">{error}</p> : null}
  </main>;
}
