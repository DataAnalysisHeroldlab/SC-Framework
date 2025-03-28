"""Test receptor-ligand functions."""

import pytest
import os
import pandas as pd
import numpy as np
import scanpy as sc
import random
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import sctoolbox.tools.receptor_ligand as rl


# ------------------------------ FIXTURES -------------------------------- #


# Prevent figures from being shown, we just check that they are created
plt.switch_backend("Agg")


@pytest.fixture
def adata():
    """Load and returns an anndata object."""
    f = os.path.join(os.path.dirname(__file__), '..', 'data', "adata.h5ad")

    obj = sc.read_h5ad(f)

    # add cluster column
    def repeat_items(list, count):
        """
        Repeat list until size reached.

        https://stackoverflow.com/a/54864336/19870975
        """
        return list * (count // len(list)) + list[:(count % len(list))]

    obj.obs["cluster"] = repeat_items([f"cluster {i}" for i in range(10)], len(obj))

    return obj


@pytest.fixture
def db_file():
    """Path to receptor-ligand database."""
    return os.path.join(os.path.dirname(__file__), '..', 'data', 'receptor-ligand', 'mouse_lr_pair.tsv')


@pytest.fixture
def adata_db(adata, db_file):
    """Add interaction db to adata."""
    return rl.download_db(adata=adata,
                          db_path=db_file,
                          ligand_column='ligand_gene_symbol',
                          receptor_column='receptor_gene_symbol',
                          inplace=False,
                          overwrite=False)


@pytest.fixture
def adata_inter(adata_db):
    """Add interaction scores to adata."""
    obj = adata_db.copy()

    # replace with random interactions
    obj.uns["receptor-ligand"]["database"] = pd.DataFrame({
        "ligand_gene_symbol": random.sample(obj.var["gene"].tolist(), k=len(obj.var) // 2),
        "receptor_gene_symbol": random.sample(obj.var["gene"].tolist(), k=len(obj.var) // 2)
    })

    return rl.calculate_interaction_table(adata=obj,
                                          cluster_column="cluster",
                                          gene_index="gene",
                                          normalize=1000,
                                          inplace=False,
                                          overwrite=False)


# ------------------------------ TESTS -------------------------------- #


# ----- test setup functions ----- #

@pytest.mark.parametrize('db_path,ligand_column,receptor_column',
                         [(None, 'ligand_gene_symbol', 'receptor_gene_symbol'),
                          ('consensus', 'ligand', 'receptor')]
                         )
def test_download_db(adata, db_path, ligand_column, receptor_column, db_file):
    """Assert rl database is added into anndata."""
    obj = adata.copy()

    # adata does not have database
    assert "receptor-ligand" not in obj.uns

    # add database
    rl.download_db(adata=obj,
                   db_path=db_path if db_path else db_file,
                   ligand_column=ligand_column,
                   receptor_column=receptor_column,
                   inplace=True,
                   overwrite=False)

    # adata contains database
    assert "receptor-ligand" in obj.uns
    assert "database" in obj.uns["receptor-ligand"]


@pytest.mark.parametrize('db_path,ligand_column,receptor_column',
                         [(None, 'INVALID', 'receptor_gene_symbol'),
                          (None, 'ligand_gene_symbol', 'INVALID'),
                          ('INVALID', 'ligand', 'receptor')]
                         )
def test_download_db_fail(adata, db_path, ligand_column, receptor_column, db_file):
    """Assert ValueErrors."""
    obj = adata.copy()

    # adata does not have database
    assert "receptor-ligand" not in obj.uns

    with pytest.raises(ValueError):
        rl.download_db(adata=obj,
                       db_path=db_path if db_path else db_file,
                       ligand_column=ligand_column,
                       receptor_column=receptor_column,
                       inplace=True,
                       overwrite=False)

    # adata does not have database
    assert "receptor-ligand" not in obj.uns


def test_interaction_table(adata_db):
    """Assert interaction are computed/ added into anndata."""
    obj = adata_db.copy()

    # adata has db but no scores
    assert "receptor-ligand" in obj.uns
    assert "database" in obj.uns["receptor-ligand"]
    assert "interactions" not in obj.uns["receptor-ligand"]

    # compute rl scores
    with pytest.raises(Exception):
        # raises error because no interactions are found
        rl.calculate_interaction_table(adata=obj,
                                       cluster_column="cluster",
                                       gene_index="gene",
                                       normalize=1000,
                                       inplace=True,
                                       overwrite=False)

    # replace with random interactions
    obj.uns["receptor-ligand"]["database"] = pd.DataFrame({
        "ligand_gene_symbol": random.sample(obj.var["gene"].tolist(), k=len(obj.var) // 2),
        "receptor_gene_symbol": random.sample(obj.var["gene"].tolist(), k=len(obj.var) // 2)
    })

    rl.calculate_interaction_table(adata=obj,
                                   cluster_column="cluster",
                                   gene_index="gene",
                                   normalize=1000,
                                   inplace=True,
                                   overwrite=False)

    # adata contains scores
    assert "interactions" in obj.uns["receptor-ligand"]


# ----- test helpers ----- #

def test_get_interactions(adata_inter):
    """Assert that interactions can be received."""
    interactions_table = rl.get_interactions(adata_inter)

    # output is a pandas table
    assert isinstance(interactions_table, pd.DataFrame)


def test_check_interactions(adata, adata_db, adata_inter):
    """Assert that interaction test is properly checked."""
    # raise error without rl info
    with pytest.raises(ValueError):
        rl._check_interactions(adata)

    # raise error with incomplete rl info
    with pytest.raises(ValueError):
        rl._check_interactions(adata_db)

    # accept
    rl._check_interactions(adata_inter)


# ----- test plotting ----- #

def test_violin(adata_inter):
    """Violin plot is functional."""
    plot = rl.interaction_violin_plot(adata_inter,
                                      min_perc=0,
                                      save=None,
                                      figsize=(5, 30),
                                      dpi=100)

    assert isinstance(plot, np.ndarray)


def test_hairball(adata_inter):
    """Hairball network plot is functional."""
    plot = rl.hairball(adata_inter,
                       min_perc=0,
                       interaction_score=0,
                       interaction_perc=90,
                       save=None,
                       title=None,
                       color_min=0,
                       color_max=None,
                       restrict_to=[],
                       show_count=True)

    assert isinstance(plot, np.ndarray)


def test_cyclone(adata_inter):
    """Cyclone network plot is functional."""
    plot = rl.cyclone(adata=adata_inter,
                      min_perc=70,
                      interaction_score=0,
                      directional=True,
                      sector_size_is_cluster_size=True,
                      show_genes=True,
                      title="Test Title")

    assert isinstance(plot, Figure)


def test_connectionPlot(adata_inter):
    """Test if connectionPlot is working."""
    plot = rl.connectionPlot(adata=adata_inter,
                             restrict_to=None,
                             figsize=(5, 10),
                             dpi=100,
                             connection_alpha="interaction_score",
                             save=None,
                             title=None,
                             receptor_cluster_col="receptor_cluster",
                             receptor_col="receptor_gene",
                             receptor_hue="receptor_score",
                             receptor_size="receptor_percent",
                             ligand_cluster_col="ligand_cluster",
                             ligand_col="ligand_gene",
                             ligand_hue="ligand_score",
                             ligand_size="ligand_percent",
                             filter="receptor_score > 0 & ligand_score > 0 & interaction_score > 0",
                             lw_multiplier=2,
                             wspace=0.4,
                             line_colors="rainbow")

    assert isinstance(plot, np.ndarray)
