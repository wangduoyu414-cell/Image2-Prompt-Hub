import Link from "next/link";

import { CaseCard } from "@/components/case-card";
import {
  ApiError,
  type CaseDetailResponse,
  type CaseFilters,
  type CaseListResponse,
  filtersFromSearchParams,
  getCaseDetail,
  getCaseList,
} from "@/lib/api";

type SearchParams = Record<string, string | string[] | undefined>;

function listingHref(filters: CaseFilters, page = 1): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.source) params.set("source", filters.source);
  if (filters.displayPolicy) params.set("display_policy", filters.displayPolicy);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.hasReferenceInput !== undefined) params.set("has_reference_input", String(filters.hasReferenceInput));
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/?${query}` : "/";
}

function facetOptions(values: Array<{ value: string; count: number }>, selected: string | undefined): Array<{ value: string; count: number }> {
  const indexed = new Map(values.map((value) => [value.value, value]));
  if (selected && !indexed.has(selected)) {
    indexed.set(selected, { value: selected, count: 0 });
  }
  return [...indexed.values()];
}

function DirectoryHeader({ listing }: { listing: CaseListResponse }) {
  const publication = listing.publication.publication;
  return (
    <header className="site-header">
      <Link className="site-mark" href="/">
        Image2 <span>公共目录</span>
      </Link>
      <p>只展示当前不可变公开版本中的案例；来源、权利和模型声明均以 API 返回为准。</p>
      <dl className="publication-summary">
        <div>
          <dt>公开版本</dt>
          <dd>{publication ? <code>{publication.content_digest}</code> : "当前没有激活版本"}</dd>
        </div>
        <div>
          <dt>唯一案例</dt>
          <dd>{listing.publication.case_count}</dd>
        </div>
      </dl>
    </header>
  );
}

function Filters({ filters, listing }: { filters: CaseFilters; listing: CaseListResponse }) {
  const sourceOptions = facetOptions(listing.facets.sources, filters.source);
  const policyOptions = facetOptions(listing.facets.display_policies, filters.displayPolicy);
  const tagOptions = facetOptions(listing.facets.tags, filters.tag);
  return (
    <form action="/" aria-label="筛选案例" className="filters" method="get">
      <label className="search-field" htmlFor="case-search">
        搜索原始 Prompt、来源或标签
        <input defaultValue={filters.q ?? ""} id="case-search" name="q" placeholder="例如：glass sculpture" type="search" />
      </label>
      <label>
        来源
        <select defaultValue={filters.source ?? ""} name="source">
          <option value="">所有来源</option>
          {sourceOptions.map((facet) => (
            <option key={facet.value} value={facet.value}>
              {facet.value} ({facet.count})
            </option>
          ))}
        </select>
      </label>
      <label>
        展示策略
        <select defaultValue={filters.displayPolicy ?? ""} name="display_policy">
          <option value="">所有策略</option>
          {policyOptions.map((facet) => (
            <option key={facet.value} value={facet.value}>
              {facet.value} ({facet.count})
            </option>
          ))}
        </select>
      </label>
      <label>
        标签
        <select defaultValue={filters.tag ?? ""} name="tag">
          <option value="">所有标签</option>
          {tagOptions.map((facet) => (
            <option key={facet.value} value={facet.value}>
              {facet.value} ({facet.count})
            </option>
          ))}
        </select>
      </label>
      <label>
        参考输入
        <select defaultValue={filters.hasReferenceInput === undefined ? "" : String(filters.hasReferenceInput)} name="has_reference_input">
          <option value="">不限</option>
          <option value="true">有参考输入</option>
          <option value="false">无参考输入</option>
        </select>
      </label>
      <div className="filter-actions">
        <button type="submit">应用筛选</button>
        <Link href="/">清除筛选</Link>
      </div>
    </form>
  );
}

function EmptyState({ noCurrent }: { noCurrent: boolean }) {
  return (
    <section aria-labelledby="empty-title" className="state-panel">
      <p className="eyebrow">公共目录</p>
      <h2 id="empty-title">尚无可公开案例</h2>
      <p>{noCurrent ? "当前没有激活的公开版本。没有人工公开审核时，空目录是正确的安全状态。" : "当前筛选没有匹配的公开案例。可清除筛选后再试。"}</p>
      {!noCurrent ? <Link className="text-link" href="/">清除筛选</Link> : null}
    </section>
  );
}

function DirectoryError() {
  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <header className="site-header">
        <Link className="site-mark" href="/">
          Image2 <span>公共目录</span>
        </Link>
      </header>
      <section aria-labelledby="directory-error-title" className="state-panel error-panel">
        <p className="eyebrow">暂时不可用</p>
        <h1 id="directory-error-title">目录暂时不可用</h1>
        <p>暂时无法读取当前公开版本。请稍后重试；此页面不会显示内部服务信息。</p>
        <Link className="text-link" href="/">重试</Link>
      </section>
    </main>
  );
}

async function representatives(listing: CaseListResponse): Promise<Map<string, CaseDetailResponse>> {
  const results = await Promise.all(
    listing.cases.map(async (summary) => {
      try {
        return [summary.canonical_key, await getCaseDetail(summary.canonical_key)] as const;
      } catch {
        return null;
      }
    }),
  );
  return new Map(results.filter((result): result is readonly [string, CaseDetailResponse] => result !== null));
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const filters = filtersFromSearchParams(await searchParams);
  let listing: CaseListResponse;
  try {
    listing = await getCaseList(filters);
  } catch (error) {
    if (error instanceof ApiError) {
      return <DirectoryError />;
    }
    return <DirectoryError />;
  }

  const detailByKey = listing.total > 0 ? await representatives(listing) : new Map<string, CaseDetailResponse>();
  const pageCount = Math.max(1, Math.ceil(listing.total / listing.page_size));

  return (
    <main className="page-shell" id="main-content" tabIndex={-1}>
      <DirectoryHeader listing={listing} />
      <Filters filters={filters} listing={listing} />
      <section aria-labelledby="catalog-title" className="catalog-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">当前公开版本</p>
            <h1 id="catalog-title">可浏览的原始 Prompt 案例</h1>
          </div>
          <p aria-live="polite" className="result-count">
            共 {listing.total} 个唯一案例，第 {listing.page} / {pageCount} 页
          </p>
        </div>
        {listing.total === 0 ? (
          <EmptyState noCurrent={listing.publication.state === "no_current"} />
        ) : (
          <>
            <div className="case-grid">
              {listing.cases.map((summary) => (
                <CaseCard
                  key={summary.canonical_key}
                  representative={detailByKey.get(summary.canonical_key)?.representative}
                  summary={summary}
                />
              ))}
            </div>
            <nav aria-label="案例分页" className="pagination">
              {listing.page > 1 ? <Link href={listingHref(filters, listing.page - 1)}>上一页</Link> : <span aria-disabled="true">上一页</span>}
              <span>第 {listing.page} 页，共 {pageCount} 页</span>
              {listing.page < pageCount ? <Link href={listingHref(filters, listing.page + 1)}>下一页</Link> : <span aria-disabled="true">下一页</span>}
            </nav>
          </>
        )}
      </section>
    </main>
  );
}
