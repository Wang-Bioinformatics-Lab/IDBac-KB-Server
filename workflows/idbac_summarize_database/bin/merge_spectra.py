import sys
import os
import argparse
import pandas as pd
import requests
import json
from pyteomics import mzxml, mzml
from massql import msql_fileloading
from tqdm import tqdm
import glob
import numpy as np

bin_size = 10.0

def load_data(input_filename):
    try:
        ms1_df, ms2_df = msql_fileloading.load_data(input_filename)

        return ms1_df, ms2_df
    except:
        print("Error loading data, falling back on default")

    MS_precisions = {
        1: 5e-6,
        2: 20e-6,
        3: 20e-6,
        4: 20e-6,
        5: 20e-6,
        6: 20e-6,
        7: 20e-6
    }
    
    ms1_df = pd.DataFrame()
    ms2_df = pd.DataFrame()

    all_mz = []
    all_i = []
    all_scan = []
    
    # TODO: read the mzML directly
    with mzml.read(input_filename) as reader:
        for spectrum in tqdm(reader):
            try:
                scan = spectrum["id"].replace("scanId=", "").split("scan=")[-1]
            except:
                scan = spectrum["id"]

            mz = spectrum["m/z array"]
            intensity = spectrum["intensity array"]

            all_mz += list(mz)
            all_i += list(intensity)
            all_scan += len(mz) * [scan]

            print(spectrum["id"])
            
    if len(all_mz) > 0:
        ms1_df['i'] = all_i
        ms1_df['mz'] = all_mz
        ms1_df['scan'] = all_scan

    return ms1_df, ms2_df

def load_database(database_mzML, database_scan_mapping_tsv, merge_replicates="Yes"):
    # Reading Data
    db_spectra, _ = load_data(database_mzML)
    db_scan_mapping_df = pd.read_csv(database_scan_mapping_tsv, sep="\t")
    
    # Now we need to create consensus spectra in the database
    max_mz = 15000.0

    # Filtering m/z
    db_spectra = db_spectra[db_spectra['mz'] < max_mz]

    # Bin the MS1 Data by m/z within each spectrum
    db_spectra['bin'] = (db_spectra['mz'] / bin_size).astype(int)

    # Now we need to group by scan and bin
    db_spectra = db_spectra.groupby(['scan', 'bin']).agg({'i': 'sum'}).reset_index()
    db_spectra["mz"] = db_spectra["bin"] * bin_size
    db_spectra["bin_name"] = "BIN_" + db_spectra["bin"].astype(str)

    # Turning each scan into a 1d vector that is the intensity value for each bin
    spectra_binned_df = db_spectra.pivot(index='scan', columns='bin_name', values='i').reset_index()

    # Mapping
    spectra_binned_df = spectra_binned_df.merge(db_scan_mapping_df, how="left", left_on="scan", right_on="scan")
    
    # Lets now merge everything
    merged_spectra_list = []
    if merge_replicates == "Yes":
        # We want to do this by database_id
        all_database_id = spectra_binned_df["database_id"].unique()
        for database_id in all_database_id:
            bins_to_remove = []
            filtered_df = spectra_binned_df[spectra_binned_df["database_id"] == database_id]

            # Lets do the merge
            all_bins = [x for x in filtered_df.columns if x.startswith("BIN_")]
            for bin in all_bins:
                all_values = filtered_df[bin]

                # Count non-zero values
                non_zero_count = len(all_values[all_values > 0])

                # Calculate percent non-zero
                percent_non_zero = non_zero_count / len(all_values)

                if percent_non_zero < 0.5:
                    bins_to_remove.append(bin)

            # Removing the bins
            filtered_df = filtered_df.drop(bins_to_remove, axis=1)

            # Now lets get the mean for each bin
            filtered_df = filtered_df.groupby("database_id").mean().reset_index()
            filtered_df["scan"] = database_id

            merged_spectra_list.append(filtered_df)

        # merging everything
        merged_spectra_df = pd.concat(merged_spectra_list)

    return merged_spectra_df


def output_database(database_df, output_mgf_filename, output_scan_mapping):
    database_id_to_scan_list = []

    with open(output_mgf_filename, "w") as o:
        database_list = database_df.to_dict(orient="records")

        for database_entry in database_list:
            row_id = database_entry["row_count"]

            scan_number = row_id + 1

            o.write("BEGIN IONS\n")
            o.write("SCANS={}\n".format(scan_number))
            o.write("TITLE={}\n".format(database_entry["scan"]))

            database_id_to_scan_obj = {}
            database_id_to_scan_obj["database_id"] = database_entry["scan"]
            database_id_to_scan_obj["mgf_scan"] = scan_number
            database_id_to_scan_list.append(database_id_to_scan_obj)

            # Finding all the masses
            all_binned_masses = [x for x in database_entry.keys() if x.startswith("BIN_")]

            for binned_mass in all_binned_masses:
                intensity = database_entry[binned_mass]
                mz = float(binned_mass.replace("BIN_", "")) * bin_size

                if intensity > 0:
                    o.write("{} {}\n".format(mz, intensity))
            
            o.write("END IONS\n")

    # Writing out the mapping
    database_id_to_scan_df = pd.DataFrame(database_id_to_scan_list)
    database_id_to_scan_df.to_csv(output_scan_mapping, sep="\t", index=False)


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('database_mzML')
    parser.add_argument('database_scan_mapping_tsv', help="this file maps the scan in the mzML into the database_id")
    parser.add_argument('output_database_mgf', help="This is the merged database file output as an MGF file")
    parser.add_argument('output_mapping', help="This is the output tsv mapping from database_id to scan number in the MGF file")
    
    args = parser.parse_args()

    # Loading the database, this will also merge the spectra
    database_df = load_database(args.database_mzML, args.database_scan_mapping_tsv, merge_replicates="Yes")

    # Create a row count column, starting at 0, counting all the way up, will be useful for keeping track of things when we do matrix multiplication
    database_df["row_count"] = np.arange(len(database_df))

    # Updating filenames in database
    database_df["filename"] = os.path.basename(args.database_mzML)

    # Writing out the database itself so that we can more easily visualize it
    output_database(database_df, args.output_database_mgf, args.output_mapping)



if __name__ == '__main__':
    main()