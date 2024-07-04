"""Test functions to assemble adata objects."""

import os
import re
import anndata
import pytest
import sctoolbox.utils.assemblers as assemblers
import scanpy as sc


@pytest.fixture
def named_var_adata():
    """Return a adata object with a prefix attached to the .var index."""

    f = os.path.join(os.path.dirname(__file__), '../data', 'atac', 'mm10_atac_named_var.h5ad')

    return sc.read(f)


@pytest.fixture
def atac_adata():
    """Return a adata object from ATAC-seq."""

    f = os.path.join(os.path.dirname(__file__), '../data', 'atac', 'mm10_atac.h5ad')

    return sc.read(f)


@pytest.fixture
def adata_atac_emptyvar(atac_adata):
    """Create adata with empty adata.var."""
    adata = atac_adata.copy()
    adata.var = adata.var.drop(columns=adata.var.columns)
    return adata


@pytest.fixture
def adata_atac_invalid(atac_adata):
    """Create adata with invalid index."""
    adata = atac_adata.copy()
    adata.var.iloc[0, 1] = 500  # start
    adata.var.iloc[0, 2] = 100  # end
    adata.var.reset_index(inplace=True, drop=True)  # remove chromosome-start-stop index
    return adata


@pytest.fixture
def adata_rna():
    """Load rna adata."""
    adata_f = os.path.join(os.path.dirname(__file__), '../data', 'adata.h5ad')
    return sc.read_h5ad(adata_f)


@pytest.mark.parametrize("fixture, expected, coordinate_cols",
                         [("atac_adata", True, ["chr", "start", "stop"]),  # expects var tables to be unchanged
                          ("adata_atac_emptyvar", KeyError, ["chr", "start", "stop"]),
                          # expects var tables to be changed
                          ("adata_rna", KeyError, ["chr", "start", "stop"]),
                          # expects a valueerror due to missing columns
                          ("adata_atac_invalid", False, ["chr", "start", "stop"]),
                          ("named_var_adata", True, 'coordinate_col')])  # expects a valueerror due to format of columns
def test_prepare_atac_anndata(fixture, expected, coordinate_cols, request):
    """Test prepare_atac_anndata success."""

    adata_orig = request.getfixturevalue(fixture)  # fix for using fixtures in parametrize
    adata_cp = adata_orig.copy()  # make a copy to avoid changing the fixture

    expected_coordinates = ['chr', 'start', 'stop']
    index_pattern = r"^(chr[0-9XYM]+)[\_\:\-]+[0-9]+[\_\:\-]+[0-9]+$"

    if isinstance(expected, type):
        with pytest.raises(expected):
            assemblers.prepare_atac_anndata(adata_cp, coordinate_cols=coordinate_cols)

    else:
        assemblers.prepare_atac_anndata(adata_cp, coordinate_cols=coordinate_cols)
        # check for the existance of the coordinate columns ['chr','start','stop'] in the var table
        assert all(item in adata_cp.var.columns for item in expected_coordinates)

        # check if the first var index is in the correct format
        assert bool(re.fullmatch(index_pattern, adata_cp.var.index[0])) is True


def test_from_single_starsolo():
    """Test from_single_starsolo success."""

    SOLO_DIR = os.path.join(os.path.dirname(__file__), '../data', 'solo')
    adata = assemblers.from_single_starsolo(SOLO_DIR, dtype="filtered", header=None)

    assert isinstance(adata, anndata.AnnData)


def test_from_mtx():
    """Test from_mtx success."""

    # With variable file
    adata = assemblers.from_mtx(os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered'))
    adata2 = assemblers.from_mtx(os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered'),
                                 variables="*notfound.tsv",
                                 var_error=False)

    assert isinstance(adata, anndata.AnnData)
    assert isinstance(adata2, anndata.AnnData)


def test_from_mtx_fail():
    """Test from_mtx fail."""

    with pytest.raises(ValueError):
        assemblers.from_mtx(os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered'),
                            variables="*notfound.tsv")

    with pytest.raises(ValueError):
        assemblers.from_mtx(os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered'),
                            barcodes="*notfound.tsv")

    with pytest.raises(ValueError):
        assemblers.from_mtx("./notfound/")


def test_from_single_mtx():
    """Test from_single_mtx success."""

    MTX_FILENAME = os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered', 'matrix.mtx')
    BARCODES_FILENAME = os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered', 'barcodes.tsv')
    GENES_FILENAME = os.path.join(os.path.dirname(__file__), '../data', 'solo', 'Gene', 'filtered', 'genes.tsv')

    # test full adata (matrix, barcodes, genes)
    adata = assemblers.from_single_mtx(MTX_FILENAME, BARCODES_FILENAME, GENES_FILENAME, header=None)
    assert isinstance(adata, anndata.AnnData)

    # test partial adata (matrix, barcodes)
    adata = assemblers.from_single_mtx(MTX_FILENAME, BARCODES_FILENAME, header=None)
    assert isinstance(adata, anndata.AnnData)
