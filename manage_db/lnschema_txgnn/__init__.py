"""Custom LaminDB registries for the TxGNN biomedical knowledge graph.

Install and mount in a LaminDB instance::

    lamin init --storage ./mydb --modules bionty,lnschema_txgnn

Import and create records::

    import lnschema_txgnn as txs
    paper = txs.Paper(pmid="12345678", title="TxGNN paper").save()

Registries:

.. autosummary::
   :toctree: .

   Gene
   Molecule
   Pathway
   Tissue
   CellType
   Paper
   Transcript
   Protein
   Disease
   Enhancer
   Dataset
   Mutation

"""

__version__ = "0.1.0"

from lamindb_setup import _check_instance_setup

_check_instance_setup(from_module="lnschema_txgnn")

from .models import CellType, Dataset, Disease, Enhancer, Gene, Molecule, Mutation, Paper, Pathway, Protein, Tissue, Transcript

__all__ = [
    "CellType",
    "Dataset",
    "Disease",
    "Enhancer",
    "Gene",
    "Molecule",
    "Mutation",
    "Paper",
    "Pathway",
    "Protein",
    "Tissue",
    "Transcript",
]
