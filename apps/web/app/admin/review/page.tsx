"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  AdminApiError,
  type AdminSession,
  type ReviewQueue,
  type ReviewState,
  getAdminSession,
  getReviewQueue,
  loginAdmin,
  logoutAdmin,
} from "@/lib/admin";

const STATE_LABELS: Record<ReviewState, string> = {
  pending: "待审核",
  review_required: "需补充",
  publishable: "候选可公开",
  internal_only: "仅内部",
  blocked: "已阻止",
};

function LoginPanel({ onLogin }: { onLogin: (session: AdminSession) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      onLogin(await loginAdmin(username, password));
      setPassword("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "登录失败。请检查账号配置。 ");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="admin-shell admin-login-shell">
      <section className="admin-login-card">
        <p className="eyebrow">PRIVATE REVIEW ADMIN</p>
        <h1>审核管理入口</h1>
        <p>账号由运行环境配置。所有写入都会绑定当前登录身份，不接受浏览器自报 reviewer。</p>
        <form onSubmit={submit} className="admin-form-stack">
          <label>
            账号
            <input autoComplete="username" maxLength={64} onChange={(event) => setUsername(event.target.value)} required value={username} />
          </label>
          <label>
            密码
            <input autoComplete="current-password" maxLength={256} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
          </label>
          {error ? <p className="admin-error">{error}</p> : null}
          <button disabled={submitting} type="submit">{submitting ? "正在验证…" : "登录审核后台"}</button>
        </form>
      </section>
    </main>
  );
}

export default function ReviewQueuePage() {
  const [session, setSession] = useState<AdminSession | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [state, setState] = useState<ReviewState | "">("pending");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getAdminSession()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setAuthLoading(false));
  }, []);

  const loadQueue = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError("");
    try {
      setQueue(await getReviewQueue(state, offset));
    } catch (cause) {
      if (cause instanceof AdminApiError && cause.status === 401) setSession(null);
      setError(cause instanceof Error ? cause.message : "审核队列加载失败。");
    } finally {
      setLoading(false);
    }
  }, [offset, session, state]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  if (authLoading) return <main className="admin-shell"><p className="admin-loading">正在确认审核身份…</p></main>;
  if (!session) return <LoginPanel onLogin={setSession} />;

  async function signOut() {
    try {
      await logoutAdmin(session!.csrf_token);
    } finally {
      setSession(null);
      setQueue(null);
    }
  }

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div>
          <p className="eyebrow">CASE-LEVEL RIGHTS REVIEW</p>
          <h1>人工审核队列</h1>
          <p>逐案例查看完整 Prompt 与全部输出。没有自动授权、批量通过或来源角色静默提升。</p>
        </div>
        <div className="admin-identity">
          <span>{session.user.username}</span>
          <small>{session.user.role}</small>
          {session.user.role === "admin" ? <Link className="text-link" href="/admin/publication">发布控制台</Link> : null}
          <Link className="text-link" href="/admin/operations">运行状态</Link>
          <button className="button-secondary" onClick={signOut} type="button">退出</button>
        </div>
      </header>

      <section className="admin-stats">
        <div><strong>{queue?.subject_count ?? "—"}</strong><span>全部案例</span></div>
        <div><strong>{queue?.output_count ?? "—"}</strong><span>全部输出</span></div>
        <div><strong>{queue?.state_counts.pending ?? "—"}</strong><span>待审核</span></div>
        <div><strong>{queue?.state_counts.publishable ?? "—"}</strong><span>候选可公开</span></div>
        <div><strong>{queue?.state_counts.blocked ?? "—"}</strong><span>已阻止</span></div>
      </section>

      <section className="admin-toolbar">
        <label>
          审核状态
          <select
            onChange={(event) => {
              setOffset(0);
              setState(event.target.value as ReviewState | "");
            }}
            value={state}
          >
            <option value="">全部状态</option>
            {Object.entries(STATE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button className="button-secondary" disabled={loading} onClick={loadQueue} type="button">刷新</button>
      </section>

      {error ? <p className="admin-error">{error}</p> : null}
      <section className="admin-queue" aria-busy={loading}>
        {queue?.items.map((item) => (
          <article className="admin-queue-item" key={item.source_case_version_id}>
            <div className="admin-queue-meta">
              <span className={`review-state state-${item.state}`}>{STATE_LABELS[item.state]}</span>
              <span>{item.output_count} 张图</span>
              <span>{item.source_id}</span>
              {item.quality.verdict !== "eligible" ? <span>质量阻断：{item.quality.reason_code}</span> : null}
            </div>
            <p>{item.prompt_preview}</p>
            <small>{item.source_case_key}</small>
            <Link href={`/admin/review/${item.source_case_version_id}`}>打开完整审核单 →</Link>
          </article>
        ))}
        {!loading && queue?.items.length === 0 ? <p className="admin-empty">当前筛选条件下没有案例。</p> : null}
      </section>

      <nav className="admin-pagination" aria-label="审核队列分页">
        <button className="button-secondary" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 50))} type="button">上一页</button>
        <span>{offset + 1}–{Math.min(offset + 50, queue?.filtered_count ?? offset + 50)} / {queue?.filtered_count ?? "—"}</span>
        <button className="button-secondary" disabled={!queue || offset + queue.items.length >= queue.filtered_count || loading} onClick={() => setOffset(offset + 50)} type="button">下一页</button>
      </nav>
    </main>
  );
}
