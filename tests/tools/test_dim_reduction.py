"""Test tools/dim_reduction.py functions."""

import pytest
import sctoolbox.tools.dim_reduction as std

import scanpy as sc
import numpy as np
import os


# ----------------------------- FIXTURES ------------------------------- #


@pytest.fixture(scope="session")
def adata_no_pca():
    """Create an anndata object without PCA."""
    return sc.datasets.pbmc3k()


@pytest.fixture(scope="session")
def adata_pca():
    """Create an anndata object with precalculated PCA."""
    return sc.datasets.pbmc3k_processed()


@pytest.fixture
def adata():
    """Fixture for an AnnData object."""
    adata = sc.read_h5ad(os.path.join(os.path.dirname(__file__), '../data', 'atac', 'anndata_2.h5ad'))
    return adata


# ------------------------------ TESTS --------------------------------- #


# ------------------------------------ lsi ------------------------------------

def test_lsi(adata):
    """Test lsi success."""
    adata_ori = adata.copy()

    std.lsi(adata_ori, use_highly_variable=True)
    assert "X_lsi" in adata_ori.obsm and "lsi" in adata_ori.uns and "LSI" in adata_ori.varm
    assert np.sum(adata_ori.varm['LSI'][~adata_ori.var['highly_variable']]) == 0
    assert np.sum(adata_ori.varm['LSI'][adata_ori.var['highly_variable']]) != 0

    std.lsi(data=adata, use_highly_variable=False)

    assert np.sum(adata.varm['LSI'][~adata.var['highly_variable']]) != 0
    assert np.sum(adata.varm['LSI'][adata.var['highly_variable']]) != 0


# --------------------------------- define_PC ---------------------------------


def test_define_PC(adata_pca):
    """Test if threshold is returned."""
    assert isinstance(std.define_PC(adata_pca), int)


def test_define_PC_error(adata_no_pca):
    """Test if error without PCA."""
    with pytest.raises(ValueError, match="PCA not found! Please make sure to compute PCA before running this function."):
        std.define_PC(adata_no_pca)


# -------------------------------- propose_pcs --------------------------------


def test_propose_pcs_failure(adata_no_pca):
    """Test the propose_pcs function fails without precomputed PCA."""
    with pytest.raises(ValueError):
        std.propose_pcs(anndata=adata_no_pca)


def test_propose_pcs_succsess(adata_pca):
    """Test propose_pcs success."""
    # test knee finding option
    assert [1, 3, 4, 5, 6] == std.propose_pcs(anndata=adata_pca,
                                              how=["variance", "cumulative variance", "correlation"],
                                              var_method="knee")

    # test percentile finding option
    assert [1, 3, 4, 5, 6] == std.propose_pcs(anndata=adata_pca,
                                              how=["variance", "cumulative variance", "correlation"],
                                              var_method="percent",
                                              perc_thresh=10)


# -------------------------------- subset_pca --------------------------------


def test_subset_PCA(adata_pca):
    """Test whether number of PCA coordinate dimensions was reduced."""
    adata_copy = adata_pca.copy()

    # test range selection, not inplace
    res_adata = std.subset_PCA(adata=adata_copy,
                               n_pcs=5,
                               start=2,
                               inplace=False)

    # test inplace
    assert adata_pca.obsm["X_pca"].shape[1] == adata_copy.obsm["X_pca"].shape[1]
    assert res_adata.obsm["X_pca"].shape[1] != adata_copy.obsm["X_pca"].shape[1]
    # test PC amount
    assert res_adata.obsm["X_pca"].shape[1] == 3

    # test custom selection, inplace
    select = [2, 4, 6, 8]
    cstm_res_adata = std.subset_PCA(adata=adata_copy,
                                    select=select,
                                    inplace=True)

    assert cstm_res_adata is None
    assert adata_copy.obsm["X_pca"].shape[1] == len(select)
    assert adata_copy.obsm["X_pca"].shape[1] != adata_pca.obsm["X_pca"].shape[1]
