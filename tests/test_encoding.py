from src.genome_reader.amrfinder import AMRAnnotation
from src.genome_reader.encoding import build_catalog, encode_annotations


def annotation(genome_id: str, name: str):
    return AMRAnnotation(genome_id, name, "gene", "", "", "", "", "", "", {})


def test_catalog_is_fit_on_training_genomes_only():
    annotations = {
        "train": [annotation("train", "gene::blaTEM")],
        "test": [annotation("test", "gene::held_out_only")],
    }
    catalog = build_catalog(annotations, {"train"})
    assert catalog == ["gene::blaTEM"]
    assert encode_annotations(annotations, ["train", "test"], catalog).toarray().tolist() == [[1], [0]]
