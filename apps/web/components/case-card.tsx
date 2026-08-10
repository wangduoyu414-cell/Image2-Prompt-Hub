"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import type { Asset, CaseMember, CaseSummary, DisplayPolicy } from "@/lib/api";

function canRequestAsset(asset: Asset | undefined, policy: DisplayPolicy | undefined): asset is Asset {
  return Boolean(
    asset &&
      policy &&
      (policy === "mirror_allowed" || policy === "attribution_required") &&
      asset.media_type.startsWith("image/") &&
      /^[0-9a-f]{64}$/.test(asset.content_sha256),
  );
}

function sourceLink(asset: Asset | undefined): string | undefined {
  return asset?.source_url && /^https?:\/\//.test(asset.source_url) ? asset.source_url : undefined;
}

export function AuthorizedAssetImage({
  asset,
  policy,
  alt,
  className = "asset-image",
}: {
  asset: Asset | undefined;
  policy: DisplayPolicy | undefined;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const imageRef = useRef<HTMLImageElement>(null);
  const mirrorable = canRequestAsset(asset, policy);
  const original = sourceLink(asset);

  useEffect(() => {
    setFailed(false);
    const image = imageRef.current;
    if (image?.complete && image.naturalWidth === 0) {
      setFailed(true);
    }
  }, [asset?.content_sha256, policy]);

  if (!mirrorable || failed) {
    return (
      <div className={`${className} asset-placeholder`} data-testid="asset-placeholder">
        <span>{policy === "link_only" ? "仅提供来源链接" : "图片暂不可用"}</span>
        {original ? (
          <a href={original} rel="noreferrer" target="_blank">
            在原始来源中查看
          </a>
        ) : null}
      </div>
    );
  }

  return (
    <img
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
      ref={imageRef}
      src={`/backend/assets/${asset.content_sha256}`}
    />
  );
}

export function CaseCard({ summary, representative }: { summary: CaseSummary; representative?: CaseMember }) {
  const policy = representative?.rights.display_policy;
  const primaryOutput = representative?.outputs.find((asset) => asset.role === "output_primary") ?? representative?.outputs[0];

  return (
    <article className="case-card">
      <AuthorizedAssetImage
        alt={`案例图片：${summary.prompt_preview}`}
        asset={primaryOutput}
        className="case-card-image"
        policy={policy}
      />
      <div className="case-card-content">
        <p className="eyebrow">{summary.member_count} 个公开成员</p>
        <h2>
          <Link href={`/cases/${summary.canonical_key}`}>{summary.prompt_preview || "查看原始 Prompt"}</Link>
        </h2>
        <p className="prompt-preview">{summary.prompt_preview || "此案例的原始 Prompt 可在详情中查看。"}</p>
        <dl className="compact-metadata">
          <div>
            <dt>来源</dt>
            <dd>{summary.source_ids.join(" · ") || "未提供"}</dd>
          </div>
          <div>
            <dt>展示策略</dt>
            <dd>{summary.display_policies.join(" · ") || "未提供"}</dd>
          </div>
          <div>
            <dt>参考输入</dt>
            <dd>{summary.has_reference ? "有" : "无"}</dd>
          </div>
        </dl>
        {summary.tags.length > 0 ? (
          <ul aria-label="分类标签" className="tag-list">
            {summary.tags.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        ) : null}
        {representative?.model.warning ? <p className="model-warning">模型声明：{representative.model.warning}</p> : null}
        <Link className="text-link" href={`/cases/${summary.canonical_key}`}>
          查看案例详情<span aria-hidden="true"> →</span>
        </Link>
      </div>
    </article>
  );
}
