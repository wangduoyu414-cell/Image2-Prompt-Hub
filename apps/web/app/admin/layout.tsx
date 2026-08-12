import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "审核管理 · Image2 Prompt Hub",
  description: "带身份与权限控制的案例级人工审核入口。",
  robots: { index: false, follow: false, nocache: true },
};

export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
