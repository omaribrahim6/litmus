"use client";

import { Fragment } from "react";
import { useEvidence } from "@/components/evidence/EvidenceProvider";

const CITE = /\[((?:evt|frm|ser|rdg|run):[^\]]+)\]/g;
const ids = (group: string) => group.split(/[,\s]+/).filter((t) => /^(evt|frm|ser|rdg|run):/.test(t));

/** Minimal markdown (paragraphs, bullets, bold) with evidence citations as numbered receipts. */
export function RichText({ text, citations }: { text: string; citations: string[] }) {
  const { open, setHighlighted } = useEvidence();
  const order = citations.length ? citations : [...text.matchAll(CITE)].flatMap((m) => ids(m[1]));

  const inline = (line: string, key: string) => {
    const parts: React.ReactNode[] = [];
    let last = 0;
    let pendingIds: string[] = [];
    const flush = (k: string) => {
      if (!pendingIds.length) return;
      const ids = pendingIds;
      pendingIds = [];
      parts.push(
        <button key={k} type="button" onClick={() => open(ids)} onMouseEnter={() => setHighlighted(ids)} onMouseLeave={() => setHighlighted([])}
          className="num ml-0.5 inline-flex -translate-y-[2px] items-center rounded border border-rule bg-surface px-1 text-[10px] leading-[14px] text-base hover:border-base"
          title="Show evidence">
          {ids.map((id) => order.indexOf(id) + 1 || "?").join(",")}
        </button>,
      );
    };
    for (const m of line.matchAll(CITE)) {
      const before = line.slice(last, m.index);
      if (before.trim()) {
        flush(`${key}-c${m.index}`);
        parts.push(<Fragment key={`${key}-t${m.index}`}>{bold(before)}</Fragment>);
      } else if (before) {
        parts.push(before);
      }
      pendingIds.push(...ids(m[1]));
      last = (m.index ?? 0) + m[0].length;
    }
    flush(`${key}-end`);
    const rest = line.slice(last);
    if (rest) parts.push(<Fragment key={`${key}-rest`}>{bold(rest)}</Fragment>);
    return parts;
  };

  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const lines = text.split("\n");
  const flushList = (k: number) => {
    if (!list.length) return;
    blocks.push(
      <ul key={`ul${k}`} className="my-1.5 space-y-1 pl-4">
        {list.map((l, i) => <li key={i} className="list-disc marker:text-ink-3">{inline(l, `li${k}-${i}`)}</li>)}
      </ul>,
    );
    list = [];
  };
  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      list.push(line.replace(/^\s*[-*]\s+/, ""));
      return;
    }
    flushList(i);
    if (!line.trim()) return;
    if (/^#{1,4}\s/.test(line)) {
      blocks.push(<p key={i} className="mt-2 font-semibold">{line.replace(/^#+\s/, "")}</p>);
      return;
    }
    blocks.push(<p key={i} className="my-1.5">{inline(line, `p${i}`)}</p>);
  });
  flushList(lines.length);
  return <div className="text-[14px] leading-relaxed">{blocks}</div>;
}

function bold(s: string): React.ReactNode {
  const out: React.ReactNode[] = [];
  s.split(/(\*\*[^*]+\*\*)/g).forEach((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) out.push(<strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>);
    else if (part) out.push(part);
  });
  return out;
}
