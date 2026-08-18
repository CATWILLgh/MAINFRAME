import { mkdir, mkdtemp, readFile, readdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

export type NavigationScenario = "single-line" | "split-record";

export interface GoldControl {
  id: string;
  evidence: string;
}

export interface SyntheticCorpus {
  root: string;
  approximateWords: number;
  files: number;
  gold: GoldControl[];
  scenario: NavigationScenario;
}

export interface IndexedLine {
  path: string;
  line: number;
  text: string;
}

export interface CorpusIndex {
  files: string[];
  lines: IndexedLine[];
}

const FILLER = "ordinary operational reference material describes ownership timing recovery audit visibility and safe processing";

function controlId(index: number): string {
  return `CTL-${String(10_000 + ((index * 7919) % 89_989)).padStart(5, "0")}`;
}

export async function generateSyntheticCorpus(
  approximateWords: number,
  scenario: NavigationScenario = "single-line",
): Promise<SyntheticCorpus> {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-navigation-"));
  const fileCount = Math.max(84, Math.ceil(approximateWords / 1_750));
  const goldIndexes = Array.from({ length: 12 }, (_, index) =>
    Math.min(fileCount - 1, Math.floor(((index + 0.55) / 12) * fileCount)),
  );
  const gold: GoldControl[] = [];
  let actualWords = 0;

  for (let fileIndex = 0; fileIndex < fileCount; fileIndex += 1) {
    const section = `section-${String(Math.floor(fileIndex / 50)).padStart(2, "0")}`;
    const directory = path.join(root, "docs", section);
    await mkdir(directory, { recursive: true });
    const relative = path.posix.join("docs", section, `record-${String(fileIndex).padStart(4, "0")}.md`);
    const lines: string[] = [`# Operational record ${fileIndex}`];
    for (let lineIndex = 1; lineIndex <= 58; lineIndex += 1) {
      lines.push(`${FILLER} record ${fileIndex} line ${lineIndex}. ${FILLER}.`);
    }

    if (scenario === "split-record" || fileIndex < 72) {
      const id = controlId(fileIndex);
      const state = fileIndex % 2 === 0 ? "active" : "retired";
      const classification = fileIndex % 2 === 0 ? "advisory" : "binding";
      if (scenario === "split-record") {
        lines[3] = `CONTROL ${id} | state=${state} | owner=operations.`;
        lines[4] = `CONTROL ${id} | classification=${classification} | distractor only.`;
      } else {
        lines[4] = `CONTROL ${id} | state=${state} | owner=operations | classification=${classification} | distractor only.`;
      }
    }
    const goldPosition = goldIndexes.indexOf(fileIndex);
    if (goldPosition >= 0) {
      const id = controlId(1_000 + goldPosition);
      const line = 11 + (goldPosition % 31);
      if (scenario === "split-record") {
        lines[line - 1] = `CONTROL ${id} | state=active | owner=fulfilment.`;
        lines[line] = `CONTROL ${id} | classification=binding | enforce a verified terminal outcome.`;
      } else {
        lines[line - 1] = goldPosition % 2 === 0
          ? `CONTROL ${id} | state=active | owner=fulfilment | classification=binding | enforce duplicate-safe recovery.`
          : `CONTROL ${id} | classification=binding | escalation=manual | state=active | preserve an auditable terminal outcome.`;
      }
      gold.push({ id, evidence: `${relative}:${line}` });
    }
    const content = `${lines.join("\n")}\n`;
    actualWords += content.split(/\s+/u).filter(Boolean).length;
    await writeFile(path.join(root, relative), content);
  }
  return { root, approximateWords: actualWords, files: fileCount, gold, scenario };
}

async function collectFiles(root: string, current = root, output: string[] = []): Promise<string[]> {
  const entries = await readdir(current, { withFileTypes: true });
  entries.sort((left, right) => left.name.localeCompare(right.name));
  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue;
    const absolute = path.join(current, entry.name);
    if (entry.isDirectory()) await collectFiles(root, absolute, output);
    else if (entry.isFile()) output.push(path.relative(root, absolute).split(path.sep).join("/"));
  }
  return output;
}

export async function buildCorpusIndex(root: string): Promise<CorpusIndex> {
  const files = await collectFiles(root);
  const lines: IndexedLine[] = [];
  for (const relative of files) {
    const content = await readFile(path.join(root, relative), "utf8");
    for (const [index, text] of content.split("\n").entries()) {
      lines.push({ path: relative, line: index + 1, text });
    }
  }
  return { files, lines };
}

export function searchIndex(index: CorpusIndex, terms: string[]): IndexedLine[] {
  const normalized = terms.map((term) => term.toLowerCase());
  return index.lines.filter(({ text }) => {
    const candidate = text.toLowerCase();
    return normalized.every((term) => candidate.includes(term));
  });
}
