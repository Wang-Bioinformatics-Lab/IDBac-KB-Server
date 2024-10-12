from ete3 import NCBITaxa
from ete3 import Tree, TreeStyle
import numpy as np
import pandas as pd
import requests
import xmltodict
from time import sleep
import hashlib
import os

def get_taxonomy_lineage_genbank(genbank_accession):
    """Gets the taxonomic lineage string using a genbank accession. Each genbank
    accession is mapped to a nuccore id, which is then used to get the taxonomy
    information. Each function call is a HTTP request to the NCBI API.

    This function calls sleep(0.5) twice to space out eutils requests. The API-key free rate limit
    is 3 hits/second

    Args:
        genbank_accession (str): The genbank accession number

    Returns:
        str: The taxonomic lineage string
    """    
    # Updating the URL
    mapping_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=nucleotide&db=nucleotide&id={}&rettype=gb&retmode=xml".format(genbank_accession)

    r = requests.get(mapping_url, timeout=10)
    sleep(0.5)

    result_dictionary = xmltodict.parse(r.text)

    try:
        nuccore_id = result_dictionary["eLinkResult"]["LinkSet"][0]["IdList"]["Id"]
    except:
        nuccore_id = result_dictionary["eLinkResult"]["LinkSet"]["IdList"]["Id"]

    # here we will use an API to get the information
    xml_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&retmode=xml".format(nuccore_id)

    r = requests.get(xml_url, timeout=10)
    sleep(0.5)
    result_dictionary = xmltodict.parse(r.text)

    # Getting taxonomy
    taxonomy = result_dictionary["GBSet"]["GBSeq"]["GBSeq_taxonomy"]
    organism = result_dictionary["GBSet"]["GBSeq"]["GBSeq_organism"]

    sourced_taxid = ""
    # Find <GBQualifier_value>taxon:156453</GBQualifier_value> in text (not going to parse that)
    try:
        sourced_taxid = r.text.split("<GBQualifier_value>taxon:")[1].split("</GBQualifier_value>")[0]
    except:
        pass

    return taxonomy + "; " + organism, sourced_taxid


def get_taxonomy_lineage_ncbi(taxid, ncbi_taxa):
    """Gets the taxonomic lineage string using a taxid. Each taxid is used to get
    the full lineage of the organism. The lineage is then translated to get the
    scientific names of each taxid. The lineage is then joined with semicolons.
    This function uses the cached ncbi taxonomy database.

    Args:
        taxid (str): The taxid of the organism
        ncbi_taxa (NCBITaxa): The ncbi taxonomy database

    Returns:
        str: The taxonomic lineage string
    """
    # Get the full lineage of the taxid
    lineage = ncbi_taxa.get_lineage(taxid)
    # Translate the lineage to get scientific names
    names = ncbi_taxa.get_taxid_translator(lineage)
    # Get ranks for each taxid in the lineage
    ranks = ncbi_taxa.get_rank(lineage)
    # Define the primary seven taxonomic levels
    main_ranks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
    # Extract the taxonomic levels of interest
    lineage_str = []
    for rank in main_ranks:
        # Find the taxid corresponding to the current rank
        taxid_at_rank = next((tid for tid, r in ranks.items() if r == rank), None)
        if taxid_at_rank:
            lineage_str.append(names[taxid_at_rank])
        else:
            lineage_str.append("")
    # Join the lineage components with semicolons
    return ";".join(lineage_str)

def get_taxonomy(spectra_entry, ncbi_taxa):
    """Gets the taxonomic lineage string for a spectra entry. First uses the genbank
    accession to get the lineage. If the genbank accession is not available, the
    NCBI taxid is used as a fallback. If both are unavailable, an empty string is

    Args:
        spectra_entry (dict): The spectra database entry.
        ncbi_taxa (NCBITaxa): The ncbi taxonomy database

    Returns:
        str: The taxonomic lineage string. Empty string if there is an error.
    """
    genbank_accession = spectra_entry.get("Genbank accession", "")

    ncbi_taxid = spectra_entry.get("NCBI taxid", "")

    taxonomy = ""
    sourced_ncbi_taxid = ""
    if genbank_accession != "":
        # Prioritize genbank accession
        try:
            taxonomy, sourced_ncbi_taxid = get_taxonomy_lineage_genbank(genbank_accession)
        except Exception as e:
            print("Exception while getting taxonomy for Genbank accession", genbank_accession, flush=True)
            print(e, flush=True)

        if taxonomy != "":
            return taxonomy, sourced_ncbi_taxid

    if ncbi_taxid != "":
        # Use the NCBI taxid as a fallback
        try:
            ncbi_taxid = int(ncbi_taxid)
            taxonomy = get_taxonomy_lineage_ncbi(ncbi_taxid, ncbi_taxa)
        except Exception as e:
            print("Exception while getting taxonomy for NCBI taxid", ncbi_taxid, flush=True)
            print(e, flush=True)

        if taxonomy != "":
            return taxonomy, ncbi_taxid
        
    # Final fallback to 16S Taxonomy
    if "16S Taxonomy" in spectra_entry:
        if spectra_entry["16S Taxonomy"] is not None and spectra_entry["16S Taxonomy"] != "":
            taxonomy = spectra_entry["16S Taxonomy"].strip() + " (User Submitted 16S)"

    return taxonomy, ""
        
def populate_taxonomies(spectra_list):
    """Populates the FullTaxonomy field in each spectra entry in the spectra list.
    This function uses the NCBI taxonomy database to get the taxonomic lineage
    for each entry.

    Args:
        spectra_list (list): The list of spectra entries.

    Returns:
        list: The list of spectra entries with the FullTaxonomy field populated.
    """
    ncbi_taxa = NCBITaxa()                  # Initialize a database of NCBITaxa (Downloads all files over HTTP)
    ncbi_taxa.update_taxonomy_database()    # Check for updates (no-op if the files are up-to-date)

    for spectra_entry in spectra_list:
        try:
            taxonomy_string, ncbi_tax_id = get_taxonomy(spectra_entry, ncbi_taxa)
            sleep(0.2)

            spectra_entry["FullTaxonomy"] = taxonomy_string
            if spectra_entry['NCBI taxid'] == "" or pd.isna(spectra_entry['NCBI taxid']):
                if ncbi_tax_id != "":
                    spectra_entry['NCBI taxid'] = ncbi_tax_id
        except:
            pass

    return spectra_list

def generate_tree(taxid_list):
    os.environ['QT_QPA_PLATFORM']='offscreen'
    from PyQt5 import QtGui

    taxid_list = list(set(taxid_list))
    _taxid_list = []
    for taxid in taxid_list:
        if taxid is None:
            continue
        if taxid == "":
            continue
        try:
            _taxid_list.append(int(taxid))
        except:
            pass
    taxid_list = _taxid_list     

    svg_path = "/app/assets/tree.svg"
    png_path = "/app/assets/tree.png"

    # Initialize NCBI Taxa database
    ncbi = NCBITaxa()

    # Fetch the tree topology based on these taxids
    tree = ncbi.get_topology(taxid_list)

    # Make it a circular tree
    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.show_branch_support = False
    ts.show_scale = False
    ts.mode = "c"

    all_taxids = [int(node.name) for node in tree.traverse() if node.is_leaf()]

    # Get a mapping of TaxIDs to their taxonomic names
    taxid2name = ncbi.get_taxid_translator(all_taxids)

    for node in tree.traverse():
        if node.is_leaf():
            taxid = int(node.name)
            if taxid in taxid2name:
                node.name = ""  # Clear the original name
                node.name = " " + taxid2name[taxid]  # Set to taxonomic name

    tree.render(svg_path, w=1200, units="px", tree_style=ts)
    tree.render(png_path, w=1200, units="px", tree_style=ts)

def calculate_checksum(file_path, algorithm='sha256', chunk_size=65536):
    """
    Calculate the checksum of a file.

    Args:
        file_path (str): The path to the file.
        algorithm (str): The hashing algorithm to use. Defaults to 'sha256'.
        chunk_size (int): The size of the chunks to read from the file. Defaults to 65536.
    
    Returns:
        str: The checksum of the file
    """
    hash_function = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as file:
        while chunk := file.read(chunk_size):
            hash_function.update(chunk)
    
    return hash_function.hexdigest()