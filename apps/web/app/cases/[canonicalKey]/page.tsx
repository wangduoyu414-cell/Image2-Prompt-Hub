import Link from "next/link";
import type { ReactNode } from "react";

import { AuthorizedAssetImage } from "@/components/case-card";
import { CopyPrompt } from "@/components/copy-prompt";
import { ApiError, type Asset, type CaseMember, getCaseDetail } from "@/lib/api";

function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} rel="noreferrer" target="_blank">
      {children}
    </a>
  );
}

function AssetGroup({ assets, policy, title }: { assets: Asset[]; policy: CaseMember["rights"]["display_policy"]; title: string }) {
  if (assets.length === 0) {
    return (
      <section className="asset-section">
        <h3>{title}</h3>
        <p className="muted">没有公开的{title}。</p>
      </section>
    );
  }
  return (
    <section className="asset-section">
      <h3>{title}</h3>
      <div className="asset-grid">
        {assets.map((asset) => (
          <figure key={`${asset.content_sha256}:${asset.ordinal}:${asset.role}`}>
            <AuthorizedAssetImage alt={`${title} ${asset.ordinal + 1}`} asset={asset} policy={policy} />
            <figcaption>
              <span>{asset.role}</span>
              <SourceLink href={asset.source_url}>原始来源</SourceLink>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

function Provenance({ member }: { member: CaseMember }) {
  return (
    <dl className="detail-metadata">
      <div>
        <dt>来源</dt>
        <dd>{member.source.source_id}</dd>
      </div>
      <div>
        <dt>仓库</dt>
        <dd>{member.source.repository_id}</dd>
      </div>
      <div>
        <dt>固定提交</dt>
        <dd>
          <code>{member.source.revision_sha}</code>
        </dd>
      </div>
      <div>
        <dt>来源文件</dt>
        <dd>{member.source.source_path}</dd>
      </div>
      <div>
        <dt>来源地址</dt>
        <dd>
          <SourceLink href={member.source.source_url}>打开原始来源</SourceLink>
        </dd>
      </div>
      <div>
        <dt>展示策略</dt>
        <dd>{member.rights.display_policy}</dd>
      </div>
      <div>
        <dt>提示词权利</dt>
        <dd>{member.rights.prompt_rights}</dd>
      </div>
      <div>
        <dt>资产权利</dt>
        <dd>{member.rights.asset_rights}</dd>
      </div>
      <div>
        <dt>署名</dt>
        <dd>{member.rights.author}</dd>
      </div>
      <div>
        <dt>原始作品</dt>
        <dd>
          <SourceLink href={member.rights.original_url}>查看原始作品</SourceLink>
        </dd>
      </div>
      <div>
        <dt>权利证据</dt>
        <dd>
          <SourceLink href={member.rights.evidence_url}>查看权利证据</SourceLink>
        </dd>
      </div>
    </dl>
  );
}

function CaseMissing() {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <section aria-labelledby="missing-title" className="state-panel">
        <p className="eyebrow">404</p>
        <h1 id="missing-title">找不到该案例</h1>
        <p>该案例不在当前公开版本中，或链接已过期。</p>
        <Link className="text-link" href="/">返回公共目录</Link>
      </section>
    </main>
  );
}

function CaseUnavailable() {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <section aria-labelledby="detail-error-title" className="state-panel error-panel">
        <p className="eyebrow">暂时不可用</p>
        <h1 id="detail-error-title">案例暂时不可用</h1>
        <p>暂时无法读取此案例。请稍后重试；此页面不会显示内部服务信息。</p>
        <Link className="text-link" href="/">返回公共目录</Link>
      </section>
    </main>
  );
}

export default async function CaseDetailPage({ params }: { params: Promise<{ canonicalKey: string }> }) {
  const { canonicalKey } = await params;
  let detail;
  try {
    detail = await getCaseDetail(canonicalKey);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "not_found") {
      return <CaseMissing />;
    }
    return <CaseUnavailable />;
  }

  const representative = detail.representative;
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <nav aria-label="路径" className="breadcrumb">
        <Link href="/">公共目录</Link>
        <span aria-hidden="true">/</span>
        <span>案例详情</span>
      </nav>
      <header className="detail-header">
        <p className="eyebrow">当前公开版本 · {detail.member_count} 个公开成员</p>
        <h1>原始 Prompt 与案例证据</h1>
        <p>以下内容直接来自当前不可变公开快照；网页不会补全、翻译或改写 Prompt。</p>
      </header>
      <section aria-labelledby="raw-prompt-title" className="prompt-panel">
        <div className="prompt-panel-heading">
          <div>
            <p className="eyebrow">原始 Prompt</p>
            <h2 id="raw-prompt-title">完整未改写文本</h2>
          </div>
          <CopyPrompt rawText={representative.prompt.raw_text} />
        </div>
        <pre aria-label="原始 Prompt" className="raw-prompt">{representative.prompt.raw_text}</pre>
        <p className="muted">
          Prompt 来源：<SourceLink href={representative.prompt.provenance.source_url}>{representative.prompt.provenance.source_path}</SourceLink>
        </p>
      </section>
      <section aria-labelledby="evidence-title" className="detail-section">
        <p className="eyebrow">输入与输出</p>
        <h2 id="evidence-title">公开案例资产</h2>
        <AssetGroup assets={representative.inputs} policy={representative.rights.display_policy} title="参考输入" />
        <AssetGroup assets={representative.outputs} policy={representative.rights.display_policy} title="输出资产" />
      </section>
      <section aria-labelledby="provenance-title" className="detail-section">
        <p className="eyebrow">来源与权利</p>
        <h2 id="provenance-title">代表成员的来源记录</h2>
        <Provenance member={representative} />
      </section>
      <section aria-labelledby="model-title" className="detail-section">
        <p className="eyebrow">模型声明</p>
        <h2 id="model-title">来源原始声明与警告</h2>
        <dl className="detail-metadata">
          <div>
            <dt>声明状态</dt>
            <dd>{representative.model.source_claim.evidence_status}</dd>
          </div>
          <div>
            <dt>模型原文</dt>
            <dd>{representative.model.source_claim.model_raw ?? "来源未提供"}</dd>
          </div>
          <div>
            <dt>警告</dt>
            <dd className="model-warning">{representative.model.warning}</dd>
          </div>
        </dl>
        <h3>分类</h3>
        {representative.taxonomy.length > 0 ? (
          <ul className="tag-list">
            {representative.taxonomy.map((tag) => (
              <li key={`${tag.taxonomy_version}:${tag.tag_value}`}>
                {tag.tag_value} <span>（{tag.tag_source}，{tag.confidence}）</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">当前快照没有公开分类。</p>
        )}
      </section>
      <section aria-labelledby="members-title" className="detail-section">
        <p className="eyebrow">公共成员</p>
        <h2 id="members-title">全部 {detail.member_count} 个公开来源</h2>
        <ol className="member-list">
          {detail.members.map((member, index) => (
            <li key={`${member.source.source_id}:${member.source.revision_sha}:${member.source.source_path}`}>
              <h3>成员 {index + 1} · {member.source.source_id}</h3>
              <Provenance member={member} />
              <details>
                <summary>查看此成员的原始 Prompt</summary>
                <pre className="member-prompt">{member.prompt.raw_text}</pre>
              </details>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
