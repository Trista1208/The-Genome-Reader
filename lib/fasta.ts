export type FastaSummary = {
  bases: number;
  contigs: number;
  gcContent: number;
};

const MAX_FILE_BYTES = 10 * 1024 * 1024;

export async function validateFasta(file: File): Promise<FastaSummary> {
  if (file.size > MAX_FILE_BYTES) throw new Error("File exceeds the 10 MB prototype limit.");
  if (!/\.(fa|fasta|fna)$/i.test(file.name)) {
    throw new Error("Choose a .fa, .fasta, or .fna sequence file.");
  }

  const text = await file.text();
  const lines = text.split(/\r?\n/);
  const headers = lines.filter((line) => line.trim().startsWith(">"));
  if (headers.length === 0) throw new Error("No FASTA header found. The first record must begin with ‘>’. ");

  const sequence = lines
    .filter((line) => !line.trim().startsWith(">"))
    .join("")
    .replace(/\s/g, "")
    .toUpperCase();

  if (sequence.length < 20) throw new Error("The sequence is too short to analyze.");
  if (/[^ACGTUN-]/.test(sequence)) throw new Error("The sequence contains unsupported nucleotide symbols.");

  const bases = sequence.replace(/[-N]/g, "").length;
  const gc = (sequence.match(/[GC]/g) ?? []).length;
  return {
    bases,
    contigs: headers.length,
    gcContent: bases ? (gc / bases) * 100 : 0,
  };
}

export function formatBases(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)} Mbp`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)} kbp`;
  return `${value} bp`;
}

export function makeDemoFasta() {
  const motif = "ATGCGTACGTTAGCGGATCCGATGCTAGCTAGGCTAACCGTTGACCTGATCG";
  const sequence = motif.repeat(130);
  const body = sequence.match(/.{1,72}/g)?.join("\n") ?? sequence;
  return new File([`>demo_ecoli_contig_01 research_sample\n${body}\n`], "demo_ecoli.fasta", {
    type: "text/plain",
  });
}
