"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import {
  AdminApiError,
  type AdminSession,
  type ReviewOutput,
  type ReviewSubmissionPayload,
  type ReviewSubject,
  getAdminSession,
  getCandidatePreview,
  getReviewSubject,
  submitReview,
} from "@/lib/admin";

type Decision = ReviewSubmissionPayload["output_decisions"][number];

function initialDecision(output: ReviewOutput): Decision {
  return {
    generation_output_id: output.generation_output_id,
    asset_rights: "unknown",
    display_policy: "internal_only",
    public_display_role: "hidden",
    decision_note: "",
  };
}

export default function ReviewSubjectPage() {
  const params = useParams<{ sourceCaseVersionId: string }>();
  const sourceCaseVersionId = Number(params.sourceCaseVersionId);
  const [session, setSession] = useState<AdminSession | null>(null);
  const [subject, setSubject] = useState<ReviewSubject | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [repositoryLicense, setRepositoryLicense] = useState("");
  const [promptRights, setPromptRights] = useState<ReviewSubmissionPayload["prompt_rights"]>("unknown");
  const [author, setAuthor] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [candidate, setCandidate] = useState<Record<string, unknown> | null>(null);
  const [idempotencyKey] = useState(() => `admin-review-${crypto.randomUUID()}`);

  const outputs = useMemo(() => subject?.case_facts.generations.flatMap((generation) => generation.outputs) ?? [], [subject]);

  useEffect(() => {
    if (!Number.isInteger(sourceCaseVersionId) || sourceCaseVersionId <= 0) {
      setError("审核单编号无效。");
      return;
    }
    Promise.all([getAdminSession(), getReviewSubject(sourceCaseVersionId)])
      .then(([activeSession, activeSubject]) => {
        setSession(activeSession);
        setSubject(activeSubject);
        setRepositoryLicense(activeSubject.review_defaults.repository_license ?? "");
        setAuthor(activeSubject.review_defaults.author ?? "");
        setOriginalUrl(activeSubject.review_defaults.original_url);
        setEvidenceUrl(activeSubject.review_defaults.evidence_url);
        setDecisions(activeSubject.case_facts.generations.flatMap((generation) => generation.outputs).map(initialDecision));
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "审核单加载失败。"));
  }, [sourceCaseVersionId]);

  function updateDecision(outputId: number, patch: Partial<Decision>) {
    setDecisions((current) => current.map((item) => item.generation_output_id === outputId ? { ...item, ...patch } : item));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !subject) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const latestBatch = subject.latest_review?.rights_review_batch_id;
      const payload: ReviewSubmissionPayload = {
        source_case_version_id: sourceCaseVersionId,
        idempotency_key: idempotencyKey,
        expected_latest_batch_id: typeof latestBatch === "number" ? latestBatch : null,
        repository_license: repositoryLicense,
        prompt_rights: promptRights,
        author,
        original_url: originalUrl,
        evidence_url: evidenceUrl,
        output_decisions: decisions,
        review_note: reviewNote,
      };
      const result = await submitReview(payload, session.csrf_token);
      setNotice(`审核已写入：${String(result.status ?? "recorded")}`);
      const refreshed = await getReviewSubject(sourceCaseVersionId);
      setSubject(refreshed);
      setCandidate(await getCandidatePreview(sourceCaseVersionId));
    } catch (cause) {
      if (cause instanceof AdminApiError && cause.status === 409) {
        setError("该案例已被其他审核提交更新，请刷新后重新确认全部决定。");
      } else {
        setError(cause instanceof Error ? cause.message : "审核提交失败。");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !subject) {
    return <main className="admin-shell"><p className="admin-error">{error}</p><Link href="/admin/review">返回审核队列</Link></main>;
  }
  if (!subject || !session) return <main className="admin-shell"><p className="admin-loading">正在读取完整审核证据…</p></main>;

  const canSubmit = session.user.role === "reviewer" || session.user.role === "admin";
  const primaryCount = decisions.filter((item) => item.public_display_role === "public_primary").length;

  return (
    <main className="admin-shell admin-subject-shell">
      <header className="admin-header admin-subject-header">
        <div>
          <Link href="/admin/review">← 返回审核队列</Link>
          <p className="eyebrow">SOURCE CASE VERSION {sourceCaseVersionId}</p>
          <h1>完整案例审核单</h1>
          <p>{subject.case_facts.source.source_id} · {outputs.length} 个输出 · 当前状态 {subject.state}</p>
        </div>
        <div className="admin-identity"><span>{session.user.username}</span><small>{session.user.role}</small></div>
      </header>

      <section className="admin-evidence-grid">
        <article className="admin-evidence-panel admin-prompt-panel">
          <h2>完整 Prompt</h2>
          <pre>{subject.case_facts.prompt.raw_text}</pre>
          <dl>
            <div><dt>来源路径</dt><dd>{subject.case_facts.prompt.source_path}</dd></div>
            <div><dt>Revision</dt><dd>{subject.case_facts.source.revision_sha}</dd></div>
          </dl>
          <a href={subject.case_facts.prompt.source_url} rel="noreferrer" target="_blank">打开固定来源记录</a>
        </article>
        <article className="admin-evidence-panel">
          <h2>现有不可变权利证据</h2>
          <pre>{JSON.stringify(subject.case_facts.existing_rights_evidence, null, 2)}</pre>
          <p>这些是来源事实，不会自动推导公开许可。最终决定必须由当前登录审核人显式提交。</p>
        </article>
      </section>

      <section className="admin-output-grid">
        {outputs.map((output, index) => {
          const decision = decisions.find((item) => item.generation_output_id === output.generation_output_id);
          if (!decision) return null;
          return (
            <article className="admin-output-card" key={output.generation_output_id}>
              <img alt={`待审效果图 ${index + 1}`} src={`/admin-backend/review-assets/${output.generation_output_id}`} />
              <div className="admin-output-facts">
                <strong>输出 {index + 1}</strong><span>{output.source_role}</span><small>{output.source_path}</small>
              </div>
              <div className="admin-output-decisions">
                <label>图片权利
                  <select onChange={(event) => updateDecision(output.generation_output_id, { asset_rights: event.target.value as Decision["asset_rights"] })} value={decision.asset_rights}>
                    <option value="unknown">unknown</option><option value="approved">approved</option><option value="internal_only">internal_only</option><option value="blocked">blocked</option>
                  </select>
                </label>
                <label>展示策略
                  <select onChange={(event) => updateDecision(output.generation_output_id, { display_policy: event.target.value as Decision["display_policy"] })} value={decision.display_policy}>
                    <option value="internal_only">internal_only</option><option value="blocked">blocked</option><option value="mirror_allowed">mirror_allowed</option><option value="attribution_required">attribution_required</option><option value="link_only">link_only</option>
                  </select>
                </label>
                <label>公开角色
                  <select onChange={(event) => updateDecision(output.generation_output_id, { public_display_role: event.target.value as Decision["public_display_role"] })} value={decision.public_display_role}>
                    <option value="hidden">hidden</option><option value="public_primary">public_primary</option><option value="public_gallery">public_gallery</option>
                  </select>
                </label>
                <label>逐图决定说明
                  <textarea maxLength={2000} onChange={(event) => updateDecision(output.generation_output_id, { decision_note: event.target.value })} required value={decision.decision_note} />
                </label>
              </div>
            </article>
          );
        })}
      </section>

      <form className="admin-review-form" onSubmit={submit}>
        <h2>审核权威与案例结论</h2>
        <div className="admin-form-grid">
          <label>Repository license<input maxLength={500} onChange={(event) => setRepositoryLicense(event.target.value)} required value={repositoryLicense} /></label>
          <label>Prompt rights
            <select onChange={(event) => setPromptRights(event.target.value as ReviewSubmissionPayload["prompt_rights"])} value={promptRights}>
              <option value="unknown">unknown</option><option value="approved">approved</option><option value="internal_only">internal_only</option><option value="blocked">blocked</option>
            </select>
          </label>
          <label>作者/权利主体<input maxLength={500} onChange={(event) => setAuthor(event.target.value)} placeholder="必须由审核人明确填写" required value={author} /></label>
          <label>原始页面 URL<input maxLength={2000} onChange={(event) => setOriginalUrl(event.target.value)} required type="url" value={originalUrl} /></label>
          <label>证据 URL<input maxLength={2000} onChange={(event) => setEvidenceUrl(event.target.value)} required type="url" value={evidenceUrl} /></label>
          <label className="admin-form-wide">案例审核说明<textarea maxLength={5000} onChange={(event) => setReviewNote(event.target.value)} required value={reviewNote} /></label>
        </div>
        <div className={`admin-primary-warning ${primaryCount > 1 ? "invalid" : ""}`}>当前选择 {primaryCount} 张 public_primary；可公开候选必须恰好 1 张，且所有公开图都需 approved + 公开展示策略。</div>
        {error ? <p className="admin-error">{error}</p> : null}
        {notice ? <p className="admin-success">{notice}</p> : null}
        <button disabled={!canSubmit || submitting} type="submit">{canSubmit ? (submitting ? "正在原子写入…" : "提交完整审核批次") : "当前账号仅可查看"}</button>
      </form>

      {candidate ? <section className="admin-candidate"><h2>Candidate v2 预览</h2><pre>{JSON.stringify(candidate, null, 2)}</pre></section> : null}
    </main>
  );
}
