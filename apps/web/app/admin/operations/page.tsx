"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { type AdminSession, type OperationsStatus, getAdminSession, getOperationsStatus } from "@/lib/admin";

function when(value: string | null): string {
  if (!value) return "尚无";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN");
}

export default function OperationsPage() {
  const [session, setSession] = useState<AdminSession | null>(null);
  const [status, setStatus] = useState<OperationsStatus | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const [identity, operations] = await Promise.all([getAdminSession(), getOperationsStatus()]);
    setSession(identity); setStatus(operations); setError("");
  }, []);
  useEffect(() => { refresh().catch((cause) => setError(cause instanceof Error ? cause.message : "运行状态读取失败")); }, [refresh]);

  if (!session) return <main className="admin-shell"><section className="admin-login-card"><h1>需要先登录</h1><p>运行状态只向审核后台账号开放。</p><Link href="/admin/review">前往登录</Link>{error ? <p className="admin-error">{error}</p> : null}</section></main>;
  return <main className="admin-shell">
    <header className="admin-queue-header"><div><p className="eyebrow">SOURCE OPERATIONS</p><h1>来源与同步运行状态</h1><p>注册表是生命周期权威；这里只读展示当前远端候选、已入库状态、调度周期与告警。</p></div><div><strong>{session.user.username}</strong><span>{session.user.role.toUpperCase()}</span></div></header>
    <nav className="breadcrumb"><Link href="/admin/review">审核队列</Link><span>/</span><span>运行状态</span></nav>
    <section className="admin-stats"><div><strong>{status?.sources.length ?? "—"}</strong><span>登记来源</span></div><div><strong>{status?.eligible_source_count ?? "—"}</strong><span>持续调度</span></div><div><strong>{status?.review_queue.subject_count ?? "—"}</strong><span>待审核案例</span></div><div><strong>{status?.open_alerts.length ?? "—"}</strong><span>未解决告警</span></div><div><strong>{String(status?.scheduler_runtime?.last_status ?? "尚无")}</strong><span>调度器心跳</span></div><div><strong>{String(status?.latest_cycle?.state ?? "尚无")}</strong><span>最近周期</span></div></section>
    <section className="admin-toolbar"><button className="button-secondary" onClick={() => refresh().catch((cause) => setError(cause instanceof Error ? cause.message : "刷新失败"))} type="button">刷新状态</button><small>Registry {status?.registry_sha256.slice(0, 12) ?? "—"}</small></section>
    {error ? <p className="admin-error">{error}</p> : null}
    <section className="admin-queue">
      {status?.sources.map((source) => <article className="admin-queue-item" key={source.source_id}>
        <div className="admin-queue-meta"><span className={`review-state ${source.eligible ? "state-publishable" : "state-internal_only"}`}>{source.eligible ? "持续调度" : source.ingestion_mode}</span><span>{source.status}</span><span>{source.cadence_seconds / 3600}h + {source.jitter_seconds / 60}m jitter</span></div>
        <h2>{source.source_id}</h2><p>最近同步：{source.latest_sync_state ?? "尚无"} · {when(source.latest_sync_updated_at)}</p><small>登记 {source.registered_revision_sha.slice(0, 12)} · 候选 {source.latest_candidate_revision_sha?.slice(0, 12) ?? "尚无"}</small>
        {source.latest_sync_reason_code || source.latest_sync_error_code ? <p className="admin-error">{source.latest_sync_reason_code ?? source.latest_sync_error_code}</p> : null}
      </article>)}
    </section>
    <section className="admin-evidence-card"><h2>未解决告警</h2><pre>{JSON.stringify(status?.open_alerts ?? [], null, 2)}</pre></section>
  </main>;
}
