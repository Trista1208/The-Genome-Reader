from pathlib import Path

from src.genome_reader.fasta import iter_fasta, validate_fasta


def test_multicontig_fasta_is_one_genome(tmp_path: Path):
    fasta = tmp_path / "562.1.fna"
    fasta.write_text(">contig_1\nACGTNN\n>contig_2 description\nGGCC\n", encoding="ascii")
    assert list(iter_fasta(fasta)) == [("contig_1", "ACGTNN"), ("contig_2 description", "GGCC")]
    stats = validate_fasta(fasta)
    assert stats.records == 2
    assert stats.bases == 10
    assert stats.invalid_characters == ()


def test_invalid_dna_character_is_reported(tmp_path: Path):
    fasta = tmp_path / "bad.fna"
    fasta.write_text(">contig\nACGTZ\n", encoding="ascii")
    assert validate_fasta(fasta).invalid_characters == ("Z",)
