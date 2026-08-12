import Link from "next/link";

import { CopyPrompt } from "@/components/copy-prompt";
import { PublicOutputImage } from "@/components/public-output-image";
import { ApiV2Error, getCaseDetailV2 } from "@/lib/api-v2";

export default async function CaseDetailPage({ params }: { params: Promise<{ canonicalKey: string }> }) {
  const { canonicalKey } = await params;
  try {
    const detail = await getCaseDetailV2(canonicalKey);
    const item = detail.case;
    const outputs = item.generation_members.flatMap((member) => member.public_outputs);
    return <main className="page-shell" id="main-content" tabIndex={-1}>
      <nav aria-label="路径" className="breadcrumb"><Link href="/">公共目录</Link><span>/</span><span>案例详情</span></nav>
      <header className="detail-header"><p className="eyebrow">PUBLICATION V2 · {outputs.length} 张公开效果图</p><h1>完整原始 Prompt 与生成效果</h1><p>此页面只读取当前不可变公开快照，不补写 Prompt、不猜测模型、不展示隐藏输出。</p></header>
      <section className="prompt-panel"><div className="prompt-panel-heading"><div><p className="eyebrow">原始 Prompt</p><h2>完整未改写文本</h2></div><CopyPrompt rawText={item.prompt.raw_text} /></div><pre className="raw-prompt">{item.prompt.raw_text}</pre><p className="muted"><a href={item.prompt.source_url} rel="noreferrer" target="_blank">{item.prompt.source_path}</a></p></section>
      <section className="detail-section"><p className="eyebrow">生成输出</p><h2>全部公开效果图</h2><div className="asset-grid">{outputs.map((output, index) => <figure key={`${output.content_sha256}:${output.public_display_role}`}><PublicOutputImage alt={`效果图 ${index + 1}`} output={output} /><figcaption><span>{output.public_display_role}</span><a href={output.source_url} rel="noreferrer" target="_blank">原始来源</a></figcaption></figure>)}</div></section>
      <section className="detail-section"><p className="eyebrow">来源与权利</p><h2>可追溯证据</h2>{item.tags.length ? <ul className="tag-list">{item.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul> : null}<dl className="detail-metadata"><div><dt>来源</dt><dd>{item.source.source_id}</dd></div><div><dt>固定 Commit</dt><dd><code>{item.source.revision_sha}</code></dd></div><div><dt>作者/权利主体</dt><dd>{item.rights.author}</dd></div><div><dt>仓库许可</dt><dd>{item.rights.repository_license}</dd></div><div><dt>原始页面</dt><dd><a href={item.rights.original_url} rel="noreferrer" target="_blank">查看</a></dd></div><div><dt>审核证据</dt><dd><a href={item.rights.evidence_url} rel="noreferrer" target="_blank">查看</a></dd></div><div><dt>审核时间</dt><dd>{item.rights.reviewed_at}</dd></div><div><dt>参考输入</dt><dd>{item.generation_members.reduce((sum, member) => sum + member.reference_input_count, 0)} 个（仅公开数量，不公开私有输入）</dd></div></dl></section>
      <section className="detail-section"><p className="eyebrow">模型声明</p><h2>来源原始声明</h2>{item.generation_members.map((member) => <article key={member.generation_example_id}><h3>{member.generation_example_id}</h3><pre className="member-prompt">{JSON.stringify(member.source_claim, null, 2)}</pre>{member.hidden_output_count ? <p className="muted">另有 {member.hidden_output_count} 个隐藏输出，未进入公开快照。</p> : null}</article>)}</section>
    </main>;
  } catch (error) {
    const missing = error instanceof ApiV2Error && error.kind === "not_found";
    return <main className="page-shell"><section className="state-panel"><h1>{missing ? "找不到该案例" : "案例暂时不可用"}</h1><p>{missing ? "该稳定案例键不在当前 Publication v2 中，可能已下架或尚未公开。" : "当前公开快照无法安全读取。"}</p><Link href="/">返回公共目录</Link></section></main>;
  }
}
