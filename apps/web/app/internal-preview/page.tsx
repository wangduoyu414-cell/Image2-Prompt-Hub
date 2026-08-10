import Link from "next/link";
import type { Metadata } from "next";

import { InternalPreviewCard } from "@/components/internal-preview-card";
import {
  type InternalPreviewFilters,
  type InternalPreviewList,
  getInternalPreviewCases,
} from "@/lib/internal-preview";

type SearchParams = Record<string, string | string[] | undefined>;

export const metadata: Metadata = {
  title: "Image2 真实数据内部预览",
  description: "六个固定来源中尚待权利审核的真实提示词与对应效果图，仅供本机内部浏览。",
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function filtersFromParams(params: SearchParams): InternalPreviewFilters {
  const page = Number(first(params.page) ?? "1");
  return {
    q: first(params.q)?.trim() || undefined,
    source: first(params.source)?.trim() || undefined,
    page: Number.isInteger(page) && page > 0 ? page : 1,
  };
}

function pageHref(filters: InternalPreviewFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.source) params.set("source", filters.source);
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/internal-preview?${query}` : "/internal-preview";
}

function PreviewError() {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <header className="site-header">
        <Link className="site-mark" href="/internal-preview">
          Image2 <span>真实数据内部预览</span>
        </Link>
      </header>
      <section className="state-panel error-panel">
        <h1>内部预览暂时不可用</h1>
        <p>固定 Commit 数据索引可能仍在构建，或本机预览 API 尚未启动。稍后刷新即可。</p>
        <Link className="text-link" href="/internal-preview">
          重新加载
        </Link>
      </section>
    </main>
  );
}

function Header({ listing }: { listing: InternalPreviewList }) {
  return (
    <header className="site-header internal-preview-header">
      <Link className="site-mark" href="/internal-preview">
        Image2 <span>真实数据内部预览</span>
      </Link>
      <p className="internal-warning">{listing.disclaimer}</p>
      <dl className="publication-summary">
        <div>
          <dt>真实提示词案例</dt>
          <dd>{listing.case_count}</dd>
        </div>
        <div>
          <dt>对应效果图</dt>
          <dd>{listing.output_count}</dd>
        </div>
        <div>
          <dt>固定来源</dt>
          <dd>{listing.sources.length}</dd>
        </div>
      </dl>
      <p>
        <Link href="/">返回正式公共目录</Link>
      </p>
    </header>
  );
}

export default async function InternalPreviewPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const filters = filtersFromParams(await searchParams);
  let listing: InternalPreviewList;
  try {
    listing = await getInternalPreviewCases(filters);
  } catch {
    return <PreviewError />;
  }
  const pageCount = Math.max(1, Math.ceil(listing.total / listing.page_size));
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <Header listing={listing} />
      <form action="/internal-preview" className="filters internal-preview-filters" method="get">
        <label className="search-field" htmlFor="internal-preview-search">
          搜索 Prompt、来源或案例 ID
          <input
            defaultValue={filters.q ?? ""}
            id="internal-preview-search"
            name="q"
            placeholder="例如：cinematic portrait"
            type="search"
          />
        </label>
        <label>
          固定来源
          <select defaultValue={filters.source ?? ""} name="source">
            <option value="">全部六个来源</option>
            {listing.sources.map((source) => (
              <option key={source.value} value={source.value}>
                {source.value} ({source.count})
              </option>
            ))}
          </select>
        </label>
        <div className="filter-actions">
          <button type="submit">应用筛选</button>
          <Link href="/internal-preview">清除筛选</Link>
        </div>
      </form>
      <section aria-labelledby="internal-preview-title" className="catalog-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">固定 Commit · review_required</p>
            <h1 id="internal-preview-title">真实提示词与对应效果图</h1>
          </div>
          <p className="result-count">
            共 {listing.total} 个案例，第 {listing.page} / {pageCount} 页
          </p>
        </div>
        {listing.cases.length === 0 ? (
          <section className="state-panel">
            <h2>没有匹配的内部案例</h2>
            <Link href="/internal-preview">清除筛选</Link>
          </section>
        ) : (
          <>
            <div className="case-grid internal-preview-grid">
              {listing.cases.map((previewCase) => (
                <InternalPreviewCard key={previewCase.case_id} previewCase={previewCase} />
              ))}
            </div>
            <nav aria-label="内部预览分页" className="pagination">
              {listing.page > 1 ? <Link href={pageHref(filters, listing.page - 1)}>上一页</Link> : <span aria-disabled="true">上一页</span>}
              <span>第 {listing.page} 页，共 {pageCount} 页</span>
              {listing.page < pageCount ? <Link href={pageHref(filters, listing.page + 1)}>下一页</Link> : <span aria-disabled="true">下一页</span>}
            </nav>
          </>
        )}
      </section>
    </main>
  );
}
