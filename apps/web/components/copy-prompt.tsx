"use client";

import { useState } from "react";

export type ClipboardWrite = (text: string) => Promise<void>;

export async function copyRawPrompt(rawText: string, writeText: ClipboardWrite | undefined): Promise<void> {
  if (!writeText) {
    throw new Error("Clipboard access is unavailable.");
  }
  await writeText(rawText);
}

export function CopyPrompt({ rawText }: { rawText: string }) {
  const [message, setMessage] = useState("");

  async function handleCopy() {
    try {
      const clipboard = window.navigator.clipboard;
      await copyRawPrompt(rawText, clipboard?.writeText.bind(clipboard));
      setMessage("已复制原始 Prompt。");
    } catch {
      setMessage("无法复制原始 Prompt。请手动选择并复制。");
    }
  }

  return (
    <div className="copy-prompt">
      <button onClick={handleCopy} type="button">
        复制原始 Prompt
      </button>
      <p aria-live="polite" className="copy-feedback" role="status">
        {message}
      </p>
    </div>
  );
}
