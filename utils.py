from io import BytesIO
from ete3 import NCBITaxa
from ete3 import Tree, TreeStyle
import numpy as np
import pandas as pd
import requests
import json
from requests_cache import Path
from psims.mzml.writer import MzMLWriter
import xmltodict
from time import time, sleep
import hashlib
import os
import traceback
import sys
import pytest
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

# Caching for HTTP requests
if dev_mode:
    CACHE_DIR = "./database/http_cache"
else:
    CACHE_DIR = "/app/database/http_cache"
# Ensure the cache directory exists
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)
EXPIRATION_SECONDS = 7 * 24 * 60 * 60  # One week
JITTER = 0.2  # 20% jitter
"""
Summary of caching behavior:
1. Use the cache if it's fresh.
2. Attempt to re-fetch the content if the cache is stale or missing and cache fresh response to disk.
3. Fallback to stale cache if re-fetching fails (e.g. due to network issues).
"""

def url_to_cache_path(url):
    """Generate a filesystem-safe path for the URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.json")

def is_expired(cache_entry):
    """Check if the cache entry is expired."""
    now = time()
    return now > cache_entry.get("expires_at", 0)

def load_cache(url):
    path = url_to_cache_path(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f, strict=False)
    except Exception:
        return None

def save_cache(url, content):
    path = url_to_cache_path(url)
    expires_at = time() + EXPIRATION_SECONDS * (1 + random.uniform(-JITTER, JITTER))
    data = {
        "url": url,
        "expires_at": expires_at,
        "content": content
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

@retry(
    stop=stop_after_attempt(7),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.RequestException,
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
    )),
    reraise=True,
)
def fetch_with_retry(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text

def cached_fetch(url):
    cache = load_cache(url)
    if cache and not is_expired(cache):
        # print(f"Using cached content for {url}", flush=True)
        return cache["content"]

    try:
        # print(f"Caching new content for {url}", flush=True)
        content = fetch_with_retry(url)
        save_cache(url, content)
        sleep(0.7)
        return content
    except Exception as _:
        if cache:
            # Only use expired cache if it's less than double the expiration timeout
            now = time()
            expires_at = cache.get("expires_at", 0)
            if now < expires_at + EXPIRATION_SECONDS:
                # print(f"Using expired cache for {url}", flush=True)
                return cache["content"]
        raise  # no fallback available

def get_ncbi_taxid_from_genbank(genbank_accession:str)->int:
    """Gets the NCBI taxid from a genbank accession. Each genbank accession is
    checked in the nucleotide and genome databases (priority is given to nucleotide).
    
    Args:
        genbank_accession (str): The genbank accession number
        
    Returns:
        int: The NCBI taxid. Empty string if not found.
    """

    genbank_accession = str(genbank_accession)

    # First check the nucleotide database
    nucleotide_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nucleotide&term={genbank_accession}&retmode=json"
    r = cached_fetch(nucleotide_url)
    nucleotide_json = json.loads(r, strict=False)
    # print("nucleotide_json", nucleotide_json, flush=True)

    nucleotide_taxid = ""
    if "esearchresult" in nucleotide_json:
        if "idlist" in nucleotide_json["esearchresult"]:
            if len(nucleotide_json["esearchresult"]["idlist"]) > 0:
                nucleotide_id = nucleotide_json["esearchresult"]["idlist"][0]
                nucleotide_summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nucleotide&id={nucleotide_id}&retmode=json"
                r = cached_fetch(nucleotide_summary_url)
                nucleotide_summary_json = json.loads(r, strict=False)
                if "result" in nucleotide_summary_json:
                    if nucleotide_id in nucleotide_summary_json["result"]:
                        if "taxid" in nucleotide_summary_json["result"][nucleotide_id]:
                            nucleotide_taxid = nucleotide_summary_json["result"][nucleotide_id]["taxid"]

    # If not found in nucleotide, check the assembly database
    if nucleotide_taxid == "":
        assembly_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=assembly&term={genbank_accession}&retmode=json"
        r = cached_fetch(assembly_url)
        assembly_json = json.loads(r, strict=False)

        if "esearchresult" in assembly_json:
            if "idlist" in assembly_json["esearchresult"]:
                if len(assembly_json["esearchresult"]["idlist"]) > 0:
                    assembly_id = assembly_json["esearchresult"]["idlist"][0]
                    assembly_summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=assembly&id={assembly_id}&retmode=json"
                    r = cached_fetch(assembly_summary_url)
                    assembly_summary_json = json.loads(r, strict=False)

                    if "result" in assembly_summary_json:
                        if assembly_id in assembly_summary_json["result"]:
                            if "taxid" in assembly_summary_json["result"][assembly_id]:
                                nucleotide_taxid = assembly_summary_json["result"][assembly_id]["taxid"]

    return nucleotide_taxid

# def get_taxonomy_lineage_genbank(genbank_accession):
#     """Gets the taxonomic lineage string using a genbank accession. Each genbank
#     accession is mapped to a nuccore id, which is then used to get the taxonomy
#     information. Each function call is a HTTP request to the NCBI API.

#     This function calls sleep(0.5) twice to space out eutils requests. The API-key free rate limit
#     is 3 hits/second

#     Args:
#         genbank_accession (str): The genbank accession number

#     Returns:
#         str: The taxonomic lineage string
#     """    
#     # Updating the URL
#     mapping_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=nucleotide&db=nucleotide&id={}&rettype=gb&retmode=xml".format(genbank_accession)

#     r = fetch_with_retry(mapping_url)
#     sleep(0.5)

#     result_dictionary = xmltodict.parse(r.text)

#     try:
#         nuccore_id = result_dictionary["eLinkResult"]["LinkSet"][0]["IdList"]["Id"]
#     except:
#         nuccore_id = result_dictionary["eLinkResult"]["LinkSet"]["IdList"]["Id"]

#     # here we will use an API to get the information
#     xml_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&retmode=xml".format(nuccore_id)

#     r = fetch_with_retry(xml_url)
#     sleep(0.5)
#     result_dictionary = xmltodict.parse(r.text)

#     # Getting taxonomy
#     taxonomy = result_dictionary["GBSet"]["GBSeq"]["GBSeq_taxonomy"]
#     organism = result_dictionary["GBSet"]["GBSeq"]["GBSeq_organism"]

#     sourced_taxid = ""
#     # Find <GBQualifier_value>taxon:156453</GBQualifier_value> in text (not going to parse that)
#     try:
#         sourced_taxid = r.text.split("<GBQualifier_value>taxon:")[1].split("</GBQualifier_value>")[0]
#     except:
#         pass

#     return taxonomy + "; " + organism, sourced_taxid


# def get_taxonomy_lineage_ncbi(taxid, ncbi_taxa):
#     """Gets the taxonomic lineage string using a taxid. Each taxid is used to get
#     the full lineage of the organism. The lineage is then translated to get the
#     scientific names of each taxid. The lineage is then joined with semicolons.
#     This function uses the cached ncbi taxonomy database.

#     Args:
#         taxid (str): The taxid of the organism
#         ncbi_taxa (NCBITaxa): The ncbi taxonomy database

#     Returns:
#         str: The taxonomic lineage string
#     """
#     # Get the full lineage of the taxid
#     lineage = ncbi_taxa.get_lineage(taxid)
#     # Translate the lineage to get scientific names
#     names = ncbi_taxa.get_taxid_translator(lineage)
#     # Get ranks for each taxid in the lineage
#     ranks = ncbi_taxa.get_rank(lineage)
#     # Define the primary seven taxonomic levels
#     main_ranks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
#     # Extract the taxonomic levels of interest
#     lineage_str = []
#     for rank in main_ranks:
#         # Find the taxid corresponding to the current rank
#         taxid_at_rank = next((tid for tid, r in ranks.items() if r == rank), None)
#         if taxid_at_rank:
#             lineage_str.append(names[taxid_at_rank])
#         else:
#             lineage_str.append("")
#     # Join the lineage components with semicolons
#     return ";".join(lineage_str)

def get_taxonomy_dict_from_ncbi(taxid:int, ncbi_taxa:NCBITaxa):
    """Gets the taxonomic linear as a dictionary using a taxid. 
    
    Args:
        taxid (str): The taxid of the organism
        ncbi_taxa (NCBITaxa): The ncbi taxonomy database
        
    Returns:
        dict: The taxonomic lineage dictionary
    """
    taxid = int(taxid)
    if not isinstance(ncbi_taxa, NCBITaxa):
        raise ValueError("ncbi_taxa must be an instance of NCBITaxa")
    
    lineage_as_int = ncbi_taxa.get_lineage(taxid)
    # print("Lineage as int", lineage_as_int, flush=True)
    names = ncbi_taxa.get_taxid_translator(lineage_as_int)
    ranks = ncbi_taxa.get_rank(lineage_as_int)
    common_keys = list(set(names.keys()).intersection(set(ranks.keys())))

    lineage_dict = {}
    for key in common_keys:
        if ranks[key] != 'no rank':
            lineage_dict[ranks[key]] = names[key]

    return lineage_dict

# def deprecated_get_taxonomy(spectra_entry, ncbi_taxa):
#     """Gets the taxonomic lineage string for a spectra entry. First uses the genbank
#     accession to get the lineage. If the genbank accession is not available, the
#     NCBI taxid is used as a fallback. If both are unavailable, an empty string is

#     Args:
#         spectra_entry (dict): The spectra database entry.
#         ncbi_taxa (NCBITaxa): The ncbi taxonomy database

#     Returns:
#         str: The taxonomic lineage string. Empty string if there is an error.
#     """
#     genbank_accession = spectra_entry.get("Genbank accession", "")

#     ncbi_taxid = spectra_entry.get("NCBI taxid", "")

#     taxonomy = ""
#     sourced_ncbi_taxid = ""
#     if genbank_accession != "":
#         # Prioritize genbank accession
#         try:
#             taxonomy, sourced_ncbi_taxid = get_taxonomy_lineage_genbank(genbank_accession)
#         except Exception as e:
#             print("Exception while getting taxonomy for Genbank accession", genbank_accession, flush=True)
#             print(e, flush=True)

#         if taxonomy != "":
#             return taxonomy, sourced_ncbi_taxid

#     if ncbi_taxid != "":
#         # Use the NCBI taxid as a fallback
#         try:
#             ncbi_taxid = int(ncbi_taxid)
#             taxonomy = get_taxonomy_lineage_ncbi(ncbi_taxid, ncbi_taxa)
#         except Exception as e:
#             print("Exception while getting taxonomy for NCBI taxid", ncbi_taxid, flush=True)
#             print(e, flush=True)

#         if taxonomy != "":
#             return taxonomy, ncbi_taxid
        
#     # Final fallback to 16S Taxonomy
#     if "16S Taxonomy" in spectra_entry:
#         if spectra_entry["16S Taxonomy"] is not None and spectra_entry["16S Taxonomy"] != "":
#             taxonomy = spectra_entry["16S Taxonomy"].strip() + " (User Submitted 16S)"

#     return taxonomy, ""

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
    taxonomy_dict = {}
    genbank_accession = spectra_entry.get("Genbank accession", "")

    ncbi_taxid = spectra_entry.get("NCBI taxid", "")

    if genbank_accession != "" and genbank_accession != "None" and not pd.isna(genbank_accession):
        # Prefer genbank over NCBI taxid
        try:
            ncbi_taxid = get_ncbi_taxid_from_genbank(genbank_accession)
        except Exception as _:
            print("Exception while getting NCBI taxid for Genbank accession", genbank_accession, flush=True)
            traceback.print_exc(file=sys.stdout)
            pass

    if ncbi_taxid != "" and ncbi_taxid != "None" and not pd.isna(ncbi_taxid):
        # Use the given NCBI taxid as a fallback
        try:
            ncbi_taxid = int(ncbi_taxid)
            taxonomy_dict = get_taxonomy_dict_from_ncbi(ncbi_taxid, ncbi_taxa)

        except Exception as e:
            print("Exception while getting taxonomy for NCBI taxid", ncbi_taxid, flush=True)
            traceback.print_exc(file=sys.stdout)
            pass

        if taxonomy_dict != {}:
            return taxonomy_dict, ncbi_taxid
        
    # Final fallback to User-Specified 16S Taxonomy
    # if "16S Taxonomy" in spectra_entry:
    #     if spectra_entry["16S Taxonomy"] is not None and spectra_entry["16S Taxonomy"] != "":
    #         raise NotImplementedError("16S Taxonomy is not supported at this time")
    #         taxonomy = spectra_entry["16S Taxonomy"].strip() + " (User Submitted 16S)"

    return taxonomy_dict, ""
        
def populate_taxonomies(spectra_list):
    """Populates the FullTaxonomy field in each spectra entry in the spectra list.
    This function uses the NCBI taxonomy database to get the taxonomic lineage
    for each entry.

    Args:
        spectra_list (list): The list of spectra entries.

    Returns:
        list: The list of spectra entries with the FullTaxonomy field populated.
    """
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)   # Initialize a database of NCBITaxa (Downloads all files over HTTP)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)   # Initialize a database of NCBITaxa (Downloads all files over HTTP)

    total_entries = len(spectra_list)
    for i, spectra_entry in enumerate(spectra_list):
        # Print progress every 10%
        if total_entries > 0 and i % (total_entries // 10) == 0:
            print(f"{(i / total_entries) * 100:.0f}% done", flush=True)

        ncbi_tax_id = ""
        taxonomy_dict = {}
        try:
            taxonomy_dict, ncbi_tax_id = get_taxonomy(spectra_entry, ncbi_taxa)
            # print("Taxonomy dict", taxonomy_dict, flush=True)
            # print("NCBI Taxid", ncbi_tax_id, flush=True)

            # Check if any of the keys conflict, if so remove it and log it
            for key in taxonomy_dict:
                if key in spectra_entry:
                    # print(f"Key {key} already exists in spectra entry. Removing it.", flush=True)
                    del spectra_entry[key]
            
            # print(taxonomy_dict, flush=True)
            
            # Add the taxonomy to the spectra entry
            spectra_entry.update(taxonomy_dict)

            if spectra_entry['NCBI taxid'] == "" or pd.isna(spectra_entry['NCBI taxid']):
                if ncbi_tax_id != "":
                    spectra_entry['NCBI taxid'] = ncbi_tax_id
        except Exception as _:
            print("Exception while populating taxonomies", flush=True)
            print(f"Got NCBI taxid '{ncbi_tax_id}' and genbank accession '{spectra_entry.get('Genbank accession', 'Unknown')}'", flush=True)
            # Print the traceback for debugging
            traceback.print_exc(file=sys.stdout)
            continue

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

    if dev_mode:
        svg_path = "assets/tree.svg"
        png_path = "assets/tree.png"
    else:
        svg_path = "/app/assets/tree.svg"
        png_path = "/app/assets/tree.png"

    # Initialize NCBI Taxa database
    if dev_mode:
        ncbi = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite")
    else:
        ncbi = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite")

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
    # Save to newick tree format
    if dev_mode:
        tree.write(format=0, outfile="assets/tree.nwk")
    else:
        tree.write(format=0, outfile="/app/assets/tree.nwk")

def convert_to_mzml(json_run:Path):
    """Converts a json run to an mzML file using psims. Returns in a BytesIO object.

    Args:
        json_run (Path): The path to the json run file.

    Returns:
        BytesIO: The mzML file as a BytesIO object.
    """

    json_run = Path(str(json_run))
    if not json_run.exists():
        raise FileNotFoundError(f"File {json_run} not found")

    output_bytes = BytesIO()

    with open(json_run, 'r') as file_handle:
        run_dict = json.load(file_handle)

        other_keys = set(list(run_dict.keys()))
        other_keys.remove("spectrum")
        other_keys = sorted(list(other_keys))

        with MzMLWriter(output_bytes, close=False) as out:
            out.controlled_vocabularies()

            # Write the metadata as user parameters
            
            params = {}
            params['id'] = 'global_metadata'
            for key in other_keys:
                params[f'_{key}'] = run_dict[key] # Prevent resolutions for existing

            out.reference_param_group_list([
                params
            ])
               
            with out.run(id="admin_qc_download"):
                with out.spectrum_list(count=len(run_dict["spectrum"])):
                    scan = 1
                    for spectrum in run_dict["spectrum"]:
                        mz_array = [x[0] for x in spectrum]
                        intensity_array = [x[1] for x in spectrum]

                        out.write_spectrum(
                            mz_array, intensity_array,
                            id="scan={}".format(scan),
                            params=[
                                "MS1 Spectrum",
                                {"ms level": 1},
                                {"total ion current": sum(intensity_array)}
                            ])
                        scan += 1

    return output_bytes

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

def test_get_ncbi_taxid_from_genbank_1():
    genbank_accession = "JAHOEO000000000"
    taxid = 165179
    result = get_ncbi_taxid_from_genbank(genbank_accession)
    assert result == taxid, f"Expected taxid {taxid}, got {result}"

def test_get_ncbi_taxid_from_genbank_2():
    genbank_accession = "JAHONP000000000"
    taxid = 818
    result = get_ncbi_taxid_from_genbank(genbank_accession)
    assert result == taxid, f"Expected taxid {taxid}, got {result}"

def test_get_ncbi_taxid_from_genbank_3():
    genbank_accession = "MK168052"
    taxid = 1931
    result = get_ncbi_taxid_from_genbank(genbank_accession)
    assert result == taxid, f"Expected taxid {taxid}, got {result}"

def test_get_ncbi_taxid_from_genbank_4():
    genbank_accession = "JAHOMJ000000000"
    taxid = 1522
    assert get_ncbi_taxid_from_genbank(genbank_accession) == taxid, f"Expected taxid {taxid}, got {get_ncbi_taxid_from_genbank(genbank_accession)}"

def test_get_ncbi_taxid_from_genbank_5():
    genbank_accession = "MN588238"
    taxid = 76759
    assert get_ncbi_taxid_from_genbank(genbank_accession) == taxid, f"Expected taxid {taxid}, got {get_ncbi_taxid_from_genbank(genbank_accession)}"

def test_get_taxonomy_for_taxid_1():
    taxid = 165179
    genus = 'Segatella'
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)
    taxonomy_dict = get_taxonomy_dict_from_ncbi(taxid, ncbi_taxa)
    assert taxonomy_dict.get('genus', '')  == genus, f"Expected genus '{genus}', got '{taxonomy_dict.get('genus')}'"

def test_get_taxonomy_for_taxid_2():
    taxid = 818
    genus = 'Bacteroides'
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)
    taxonomy_dict = get_taxonomy_dict_from_ncbi(taxid, ncbi_taxa)
    assert taxonomy_dict.get('genus', '')  == genus, f"Expected genus '{genus}', got '{taxonomy_dict.get('genus')}'"

def test_get_taxonomy_for_taxid_3():
    taxid = 1931
    genus = 'Streptomyces'
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)
    taxonomy_dict = get_taxonomy_dict_from_ncbi(taxid, ncbi_taxa)
    assert taxonomy_dict.get('genus', '')  == genus, f"Expected genus '{genus}', got '{taxonomy_dict.get('genus')}'"

@pytest.mark.skip(reason="This test is likely to fail, since the taxid is awaiting transfer to a new genus.")
def test_get_taxonomy_for_taxid_4():
    taxid = 1522
    genus = 'Clostridium'
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)
    taxonomy_dict = get_taxonomy_dict_from_ncbi(taxid, ncbi_taxa)
    assert taxonomy_dict.get('genus', '')  == genus, f"Expected genus '{genus}', got '{taxonomy_dict}'"

def test_get_taxonomy_for_taxid_5():
    taxid = 76759
    genus = 'Pseudomonas'
    if dev_mode:
        ncbi_taxa = NCBITaxa(dbfile="database/ete3_ncbi_taxa.sqlite", update=True)
    else:
        ncbi_taxa = NCBITaxa(dbfile="/app/database/ete3_ncbi_taxa.sqlite", update=True)
    taxonomy_dict = get_taxonomy_dict_from_ncbi(taxid, ncbi_taxa)
    assert taxonomy_dict.get('genus', '') == genus, f"Expected genus '{genus}', got '{taxonomy_dict}'"