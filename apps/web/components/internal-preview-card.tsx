import { CopyPrompt } from "@/components/copy-prompt";
import type { InternalPreviewCase } from "@/lib/internal-preview";

export function InternalPreviewCard({ previewCase }: { previewCase: InternalPreviewCase }) {
  const visibleOutputs = previewCase.outputs.slice(0, 4);
  return (
    <article className="case-card internal-preview-card">
      <div className={`internal-preview-gallery gallery-count-${visibleOutputs.length}`}>
        {visibleOutputs.map((asset, index) => (
          <figure key={asset.asset_id}>
            <img
              alt={`效果图 ${index + 1}：${previewCase.prompt.slice(0, 80)}`}
              loading="lazy"
              src={`/internal-preview-api/assets/${asset.asset_id}`}
            />
          </figure>
        ))}
      </div>
      <div className="case-card-content">
        <div className="internal-preview-badges">
          <span>未审核 · 内部预览</span>
          <span>{previewCase.output_count} 张效果图</span>
          {previewCase.member_count > 1 ? <span>{previewCase.member_count} 条来源记录已合并</span> : null}
          {previewCase.excluded_member_count > 0 ? <span className="quality-blocked-badge">{previewCase.excluded_member_count} 条异常已隔离</span> : null}
        </div>
        <p className="prompt-preview internal-prompt-preview">{previewCase.prompt}</p>
        <dl className="compact-metadata internal-preview-metadata">
          <div>
            <dt>来源</dt>
            <dd>{previewCase.source_ids.join(" · ")}</dd>
          </div>
          <div>
            <dt>Prompt 权利</dt>
            <dd>{previewCase.prompt_rights_status}</dd>
          </div>
          <div>
            <dt>图片权利</dt>
            <dd>{previewCase.asset_rights_status}</dd>
          </div>
        </dl>
        <details className="internal-preview-details">
          <summary>查看完整 Prompt 与来源</summary>
          <pre className="raw-prompt">{previewCase.prompt}</pre>
          <p>
            {previewCase.members.map((member, index) => (
              <span key={member.case_id}>
                {index > 0 ? " · " : null}
                <a href={member.source_url} rel="noreferrer" target="_blank">{member.source_case_key}</a>
              </span>
            ))}
          </p>
          {previewCase.excluded_members.length > 0 ? (
            <div className="quality-exclusion-list">
              <strong>已隔离，不参与展示或发布：</strong>
              <ul>
                {previewCase.excluded_members.map((member) => (
                  <li key={member.case_id}>{member.source_case_key} · {member.quality_reason_code}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <CopyPrompt rawText={previewCase.prompt} />
        </details>
      </div>
    </article>
  );
}
