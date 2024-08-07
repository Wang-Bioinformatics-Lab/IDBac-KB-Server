from ete3 import NCBITaxa
import requests
import xmltodict

def get_taxonomy_lineage_genbank(genbank_accession):
    """Gets the taxonomic lineage string using a genbank accession. Each genbank
    accession is mapped to a nuccore id, which is then used to get the taxonomy
    information. Each function call is a HTTP request to the NCBI API.

    Args:
        genbank_accession (str): The genbank accession number

    Returns:
        str: The taxonomic lineage string
    """    
    # Updating the URL
    mapping_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=nucleotide&db=nucleotide&id={}&rettype=gb&retmode=xml".format(genbank_accession)

    r = requests.get(mapping_url, timeout=10)
    result_dictionary = xmltodict.parse(r.text)
    
    try:
        nuccore_id = result_dictionary["eLinkResult"]["LinkSet"][0]["IdList"]["Id"]
    except:
        nuccore_id = result_dictionary["eLinkResult"]["LinkSet"]["IdList"]["Id"]

    # here we will use an API to get the information
    xml_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&retmode=xml".format(nuccore_id)

    r = requests.get(xml_url, timeout=10)
    result_dictionary = xmltodict.parse(r.text)

    # Getting taxonomy
    taxonomy = result_dictionary["GBSet"]["GBSeq"]["GBSeq_taxonomy"]
    organism = result_dictionary["GBSet"]["GBSeq"]["GBSeq_organism"]

    return taxonomy + "; " + organism


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
    if genbank_accession != "":
        # Prioritize genbank accession
        try:
            taxonomy = get_taxonomy_lineage_genbank(genbank_accession)
        except Exception as e:
            print(e)

        if taxonomy != "":
            return taxonomy

    if ncbi_taxid != "":
        # Use the NCBI taxid as a fallback
        try:
            ncbi_taxid = int(ncbi_taxid)
            taxonomy = get_taxonomy_lineage_ncbi(ncbi_taxid, ncbi_taxa)
        except Exception as e:
            print(e)

    return taxonomy
        
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
            taxonomy_string = get_taxonomy(spectra_entry, ncbi_taxa)

            spectra_entry["FullTaxonomy"] = taxonomy_string
        except:
            pass

    return spectra_list