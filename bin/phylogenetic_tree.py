import argparse
import os
from ete3 import NCBITaxa
from ete3 import Tree, TreeStyle

import os
os.environ['QT_QPA_PLATFORM']='offscreen'

def generate_tree(taxid_list):
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
                print(taxid2name[taxid])
                node.name = " " + taxid2name[taxid]  # Set to taxonomic name

    # Customize the tree rendering (e.g., branch width, node labels)
    tree.render("./assets/styled_phylogenetic_tree.png", w=800, units="px", tree_style=ts)

def main():
    parser = argparse.ArgumentParser(description="Generate a phylogenetic tree")
    parser.add_argument("taxids", nargs="+", type=int, help="Taxonomy IDs to generate the tree")

    args = parser.parse_args()

    generate_tree(args.taxids)

if __name__ == "__main__":
    main()