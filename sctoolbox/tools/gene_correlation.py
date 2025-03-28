"""Tools for gene-gene correlation."""
import pandas as pd
import numpy as np
import scanpy as sc
from scipy.stats import spearmanr
from scipy.stats import norm
import statsmodels.api
from joblib import Parallel, delayed
from tqdm import tqdm

from beartype import beartype
from beartype.typing import Optional

from sctoolbox.utils.checker import check_columns
from sctoolbox.utils.adata import get_adata_subsets
from sctoolbox.plotting.embedding import umap_marker_overview
from sctoolbox._settings import settings
logger = settings.logger


@beartype
def correlate_conditions(adata: sc.AnnData,
                         gene: str,
                         condition_col: str,
                         condition_A: str,
                         condition_B: str) -> pd.DataFrame:
    """
    Calculate the correlation of a gene expression over two conditions and compares the two conditions.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated adata object.
    gene : str
        Gene of interest.
    condition_col : str
        Column in adata.obs containing conditions.
    condition_A : str
        Name of the first condition.
    condition_B : str
        Name of the second condition.

    Returns
    -------
    pd.DataFrame
        Dataframe containing the correlation of a gene expression over two conditions.

    Raises
    ------
    ValueError
        If one or both condition columns are not in adata.obs.
    """

    # Subset adata on conditions
    check_columns(adata.obs, columns=[condition_col], name="adata.obs")
    adata_subsets = get_adata_subsets(adata, groupby=condition_col)

    if not all(x in adata_subsets.keys() for x in [condition_A, condition_B]):
        raise ValueError(f"One or both conditions ({condition_A}, {condition_B}]) \
                         could not be found in adata.obs['{condition_col}']")

    # Calculate correlations
    corr_A_df = correlate_ref_vs_all(adata_subsets[condition_A], gene)
    corr_B_df = correlate_ref_vs_all(adata_subsets[condition_B], gene)

    # Compare correlations
    comparison = compare_two_conditons(corr_A_df, corr_B_df,
                                       adata_subsets[condition_A].shape[1],
                                       adata_subsets[condition_B].shape[1])
    return comparison


@beartype
def correlate_ref_vs_all(adata: sc.AnnData,
                         ref_gene: str,
                         correlation_threshold: float = 0.4,
                         save: Optional[str] = None) -> pd.DataFrame:
    """
    Calculate the correlation of the reference gene vs all other genes.

    Additionally, plots umap highlighting correlating gene expression.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix.
    ref_gene : str
        Reference gene.
    correlation_threshold : float, default 0.4
        Threshold for correlation value. Correlating genes with a correlation >= threshold will be plotted
        if plot parameter is set to True.
    save : str, default None
        Path to save the figure to.

    Returns
    -------
    pd.DataFrame
        Dataframe containing correlation of refrence gene to other genes.
    """

    def spearmanr_of_gene(ref, gene, gene_name):
        """Get tuple of gene and spearman correlation of gene to reference."""
        return (gene_name, spearmanr(ref, gene))

    def map_correlation_strength(x):
        """Map correlation to describing strings."""
        if 0 <= x < 0.2:
            return "very weak (0.00-0.19)"
        elif x < 0.4:
            return "weak (0.20-0.39)"
        elif x < 0.6:
            return "moderate (0.40-0.59)"
        elif x < 0.8:
            return "strong (0.60-0.79)"
        elif x <= 1:
            return "very strong (0.80-1.00)"
        elif np.isnan(x):
            return x
        else:
            raise ValueError("Invalid correlation value.")

    # Get expression values of reference gene
    ref = adata[:, ref_gene].to_df()[ref_gene]

    logger.info(f"Calculating the correlation to {ref_gene}")
    results = dict(Parallel(n_jobs=-1)(delayed(spearmanr_of_gene)(ref, adata[:, gene].to_df()[gene], gene) for gene in tqdm(adata.var.index.values.tolist())))
    corr_df = pd.DataFrame.from_dict(results, orient="index")
    corr_df.columns = ["correlation", "p-value"]

    # Adjust p-values
    corr_df["padj"] = statsmodels.stats.multitest.multipletests(corr_df["p-value"], method="bonferroni")[1]

    # Add interpretation columns
    corr_df["correlation_sign"] = np.where(corr_df['correlation'] < 0, "negative", "positive")
    corr_df['correlation_strength'] = corr_df['correlation'].apply(map_correlation_strength)
    corr_df["reject_0?"] = np.where(corr_df['padj'] < 0.05, True, False)

    # Clean up after nan values
    corr_df.loc[corr_df.isnull().any(axis=1), :] = np.nan

    if save:
        to_plot = corr_df[corr_df["correlation"] > correlation_threshold].index.to_list()
        _ = umap_marker_overview(adata, to_plot, ncols=4, save=save, cbar_label="Relative expr.")
    return corr_df


@beartype
def compare_two_conditons(df_cond_A: pd.DataFrame,
                          df_cond_B: pd.DataFrame,
                          n_cells_A: int,
                          n_cells_B: int) -> pd.DataFrame:
    """
    Compare two conditions.

    Parameters
    ----------
    df_cond_A : pd.DataFrame
        Dataframe containing correlation analysis from correlate_ref_vs_all
    df_cond_B : pd.DataFrame
        Dataframe containing correlation analysis from correlate_ref_vs_all
    n_cells_A : int
        Number of cells within condition A
    n_cells_B : int
        Number of cells within condition B

    Returns
    -------
    pd.DataFrame
        Dataframe containing single correlation and Fischer Z transformation
    """

    def independent_corr(gene_row, n_xy, n_ab):
        """z-transforms correlation coefficient xy (of n cells) andab (of n2 cells) and p-value of the difference."""
        if (1 - gene_row['correlation_A']) == 0 or (1 - gene_row['correlation_B']) == 0:
            return np.nan, np.nan
        # Fisher's r-to-Z Transformation
        xy_z = 0.5 * np.log((1 + gene_row['correlation_A']) / (1 - gene_row['correlation_A']))
        ab_z = 0.5 * np.log((1 + gene_row['correlation_B']) / (1 - gene_row['correlation_B']))
        # fisher1925 - denominator
        se_diff_r = np.sqrt(1 / (n_xy - 3) + 1 / (n_ab - 3))
        # fisher1925 - numerator
        diff = xy_z - ab_z
        # fisher1925 - significance test
        z = abs(diff / se_diff_r)
        # two-tailed p-value, therefore *2
        p = (1 - norm.cdf(z)) * 2
        return z, p

    # Join both correlation tables
    df_cond = df_cond_A.join(df_cond_B, lsuffix='_A', rsuffix='_B')

    # Compare both correlation coefficients
    df_cond['comparison z-score'], df_cond['comparison p-value'] = \
        zip(*df_cond.apply(independent_corr, args=(n_cells_A, n_cells_B), axis=1))

    return df_cond
