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
        </div>
        <p className="prompt-preview internal-prompt-preview">{previewCase.prompt}</p>
        <dl className="compact-metadata internal-preview-metadata">
          <div>
            <dt>来源</dt>
            <dd>{previewCase.source_id}</dd>
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
            <a href={previewCase.source_url} rel="noreferrer" target="_blank">
              查看固定来源记录
            </a>
          </p>
          <CopyPrompt rawText={previewCase.prompt} />
        </details>
      </div>
    </article>
  );
}

