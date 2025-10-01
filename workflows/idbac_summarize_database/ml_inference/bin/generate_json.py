import argparse
from pathlib import Path
import pandas as pd
import json
from tqdm import tqdm
import logging

"""
Keys:
['Strain name', 'Strain ID', 'Filename', 'Scan/Coordinate', 'Genbank accession', 'NCBI taxid', '16S Taxonomy', '16S Sequence', 'Culture Collection', 'MALDI matrix name', 'MALDI prep', 'Cultivation media', 'Cultivation temp', 'Cultivation time', 'PI', 'MS Collected by', 'Isolate Collected by', 'Sample Collected by', 'Sample name', 'Isolate Source', 'Source Location Name', 'Longitude', 'Latitude', 'Altitude', 'Collection Temperature', 'spectrum', 'task', 'user', 'database_id']

"""


def main():
    parser = argparse.ArgumentParser(description="Generate JSON from preprocessed data")
    parser.add_argument('--idbac_full_spectra_json', type=str, help='Path to the input IDBac full spectra JSON file')
    parser.add_argument('--idbac_ml_vectors', type=str, help='Path to the input IDBac ML vectors feather file')
    parser.add_argument('--output_file', type=str, required=True, help='Output file to save the generated JSON')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    for arg in vars(args):
        logging.info("%s: %s", arg, getattr(args, arg))

    idbac_full_spectra_json = Path(args.idbac_full_spectra_json)
    idbac_ml_vectors = Path(args.idbac_ml_vectors)
    output_file = Path(args.output_file)

    if not idbac_full_spectra_json.exists():
        raise ValueError(f"IDBac full spectra JSON file does not exist: {idbac_full_spectra_json}")
    if not idbac_ml_vectors.exists():
        raise ValueError(f"IDBac ML vectors feather file does not exist: {idbac_ml_vectors}")
    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True, exist_ok=True)

    ml_vectors = pd.read_feather(idbac_ml_vectors)
    ids = ml_vectors['database_id'].tolist()
    ml_vectors.drop(columns=['database_id'], inplace=True)
    values = ml_vectors.values
    ml_vectors_dict = {id_: value for id_, value in zip(ids, values)}


    with open(idbac_full_spectra_json, 'r', encoding='utf-8') as f, \
        open(output_file, 'w', encoding='utf-8') as out_f:
        for line in tqdm(f, desc="Processing JSON lines", total=len(ml_vectors_dict)):
            data = json.loads(line)
            # Replace spectrum with ML vector
            db_id = data.get('database_id')

            data['raw_spectrum']    = data['spectrum']
            embedding = ml_vectors_dict.get(db_id)
            if embedding is None:
                logging.warning(f"No ML vector found for database_id: {db_id}. Skipping.")
                continue

            data['spectrum']        = embedding.tolist()

            # Write the modified data to the output file
            out_f.write(json.dumps(data) + '\n')

if __name__ == "__main__":
    main()