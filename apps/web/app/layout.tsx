import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Image2 Prompt Hub",
  description: "浏览 Publication v2 当前公开版本中的 GPT Image 提示词与对应效果图。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <a className="skip-link" href="#main-content">
          跳至主要内容
        </a>
        {children}
      </body>
    </html>
  );
}
