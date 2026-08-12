"use client";

import { useState } from "react";

import type { PublicOutputV2 } from "@/lib/api-v2";

export function PublicOutputImage({ output, alt, className = "asset-image" }: { output: PublicOutputV2; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (output.display_policy === "link_only" || failed) {
    return <div className={`${className} asset-placeholder`}><span>{output.display_policy === "link_only" ? "仅提供来源链接" : "图片暂不可用"}</span><a href={output.source_url} rel="noreferrer" target="_blank">在原始来源中查看</a></div>;
  }
  return <img alt={alt} className={className} onError={() => setFailed(true)} src={`/backend-v2/assets/${output.content_sha256}`} />;
}
