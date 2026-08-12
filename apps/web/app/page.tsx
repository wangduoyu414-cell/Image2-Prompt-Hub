import Link from "next/link";

import { PublicOutputImage } from "@/components/public-output-image";
import { ApiV2Error, filtersV2, getCaseListV2 } from "@/lib/api-v2";

type SearchParams = Record<string, string | string[] | undefined>;

function href(filters: ReturnType<typeof filtersV2>, page: number): string {
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.source) query.set("source", filters.source);
  if (filters.tag) query.set("tag", filters.tag);
  if (filters.displayPolicy) query.set("display_policy", filters.displayPolicy);
  if (filters.hasReference !== undefined) query.set("has_reference", String(filters.hasReference));
  if (page > 1) query.set("page", String(page));
  return query.size ? `/?${query}` : "/";
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const filters = filtersV2(await searchParams);
  try {
    const listing = await getCaseListV2(filters);
    const pageCount = Math.max(1, Math.ceil(listing.total / listing.page_size));
    return (
      <main className="page-shell" id="main-content" tabIndex={-1}>
        <header className="site-header">
          <Link className="site-mark" href="/">Image2 <span>Prompt Hub</span></Link>
          <p>只展示 Publication v2 当前不可变快照中经过明确人工审核的案例；未审核内容不会出现。</p>
          <dl className="publication-summary"><div><dt>公开版本</dt><dd>{listing.publication.publication ? <code>{listing.publication.publication.content_digest}</code> : "当前没有激活版本"}</dd></div><div><dt>公开案例</dt><dd>{listing.publication.case_count}</dd></div></dl>
        </header>
        <form action="/" aria-label="筛选案例" className="filters" method="get">
          <label className="search-field">搜索原始 Prompt 或来源<input defaultValue={filters.q ?? ""} name="q" placeholder="例如：glass sculpture" type="search" /></label>
          <label>来源<select defaultValue={filters.source ?? ""} name="source"><option value="">所有来源</option>{listing.facets.sources.map((item) => <option key={item.value} value={item.value}>{item.value} ({item.count})</option>)}</select></label>
          <label>展示策略<select defaultValue={filters.displayPolicy ?? ""} name="display_policy"><option value="">所有策略</option>{listing.facets.display_policies.map((item) => <option key={item.value} value={item.value}>{item.value} ({item.count})</option>)}</select></label>
          <label>分类<select defaultValue={filters.tag ?? ""} name="tag"><option value="">所有分类</option>{listing.facets.tags.map((item) => <option key={item.value} value={item.value}>{item.value} ({item.count})</option>)}</select></label>
          <label>参考输入<select defaultValue={filters.hasReference === undefined ? "" : String(filters.hasReference)} name="has_reference"><option value="">不限</option><option value="true">需要</option><option value="false">不需要</option></select></label>
          <div className="filter-actions"><button type="submit">应用筛选</button><Link href="/">清除筛选</Link></div>
        </form>
        <section className="catalog-section" aria-labelledby="catalog-title">
          <div className="section-heading"><div><p className="eyebrow">PUBLICATION V2</p><h1 id="catalog-title">可复用的原始 Prompt 与效果图</h1></div><p className="result-count">共 {listing.total} 个案例，第 {listing.page} / {pageCount} 页</p></div>
          {listing.total === 0 ? <section className="state-panel"><h2>尚无可公开案例</h2><p>{listing.publication.state === "no_current" ? "当前没有激活的 Publication v2。" : "当前筛选没有匹配案例；没有真实审核批准时，空目录是正确状态。"}</p></section> : <>
            <div className="case-grid">{listing.cases.map((item) => <article className="case-card" key={item.public_case_key}><PublicOutputImage alt={`效果图：${item.prompt_preview}`} className="case-card-image" output={item.primary_output} /><div className="case-card-content"><p className="eyebrow">{item.public_output_count} 张公开效果图</p><h2><Link href={`/cases/${item.public_case_key}`}>{item.prompt_preview}</Link></h2><p className="prompt-preview">{item.prompt_preview}</p><dl className="compact-metadata"><div><dt>来源</dt><dd>{item.source_id}</dd></div><div><dt>参考图</dt><dd>{item.has_reference ? "需要" : "不需要"}</dd></div><div><dt>策略</dt><dd>{item.display_policies.join(" · ")}</dd></div></dl>{item.tags.length ? <ul className="tag-list">{item.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul> : null}<Link className="text-link" href={`/cases/${item.public_case_key}`}>查看完整 Prompt 与全部效果图 →</Link></div></article>)}</div>
            <nav aria-label="案例分页" className="pagination">{listing.page > 1 ? <Link href={href(filters, listing.page - 1)}>上一页</Link> : <span aria-disabled="true">上一页</span>}<span>第 {listing.page} 页，共 {pageCount} 页</span>{listing.page < pageCount ? <Link href={href(filters, listing.page + 1)}>下一页</Link> : <span aria-disabled="true">下一页</span>}</nav>
          </>}
        </section>
      </main>
    );
  } catch (error) {
    if (!(error instanceof ApiV2Error)) throw error;
    return <main className="page-shell"><section className="state-panel error-panel"><h1>公共目录暂时不可用</h1><p>无法读取当前 Publication v2；页面不会回退到内部库存或旧版快照。</p><Link href="/">重试</Link></section></main>;
  }
}
