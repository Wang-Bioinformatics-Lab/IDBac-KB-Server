import os
import argparse
import pandas as pd
import json
from pyteomics import mzml
from massql import msql_fileloading
from tqdm import tqdm
import logging
import numpy as np
import yaml

def load_data(input_filename):
    try:
        ms1_df, ms2_df = msql_fileloading.load_data(input_filename)

        return ms1_df, ms2_df
    except Exception as _:
        logging.warning("Error loading data with massql, falling back on pyteomics")
    
    ms1_df = pd.DataFrame()
    ms2_df = pd.DataFrame()

    all_mz = []
    all_i = []
    all_scan = []
    
    with mzml.read(input_filename) as reader:
        for spectrum in tqdm(reader):
            try:
                scan = spectrum["id"].replace("scanId=", "").split("scan=")[-1]
            except Exception as _:
                scan = spectrum["id"]

            mz = spectrum["m/z array"]
            intensity = spectrum["intensity array"]

            all_mz += list(mz)
            all_i += list(intensity)
            all_scan += len(mz) * [scan]
            
    if len(all_mz) > 0:
        ms1_df['i'] = all_i
        ms1_df['mz'] = all_mz
        ms1_df['scan'] = all_scan

    return ms1_df, ms2_df

def load_database(database_mzML, database_scan_mapping_tsv, bin_size=1.0):
    # Reading Data
    db_spectra, _ = load_data(database_mzML)
    db_scan_mapping_df = pd.read_csv(database_scan_mapping_tsv, sep="\t")
    
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
    # We want to do this by database_id
    all_database_id = spectra_binned_df["database_id"].unique()
    for database_id in all_database_id:
        bins_to_remove = []
        filtered_df = spectra_binned_df[spectra_binned_df["database_id"] == database_id]

        # Lets do the merge
        all_bins = [x for x in filtered_df.columns if x.startswith("BIN_")]
        for _bin in all_bins:
            all_values = filtered_df[_bin]

            # Count non-zero values
            non_zero_count = len(all_values[all_values > 0])

            # Calculate percent non-zero
            percent_non_zero = non_zero_count / len(all_values)

            if percent_non_zero < 0.5:
                bins_to_remove.append(_bin)

        # Removing the bins
        filtered_df = filtered_df.drop(bins_to_remove, axis=1)

        # Now lets get the mean for each bin
        filtered_df = filtered_df.groupby("database_id").mean().reset_index()
        filtered_df["scan"] = database_id

        merged_spectra_list.append(filtered_df)

    # merging everything
    if len(merged_spectra_list) == 0:
        logging.warning("No spectra found in the database, exiting")
        return pd.DataFrame()

    merged_spectra_df = pd.concat(merged_spectra_list)

    return merged_spectra_df

def peak_filtering(database_df, database_scan_mapping_tsv, config):
    """ Perform any instrument-specific postprocessing on merged spectra. 
    Current operations include: relative intensity peak filtering based on instrument type.
    
    """
    # Load the scan mapping
    scan_mapping_df = pd.read_csv(database_scan_mapping_tsv, sep="\t")

    # Load the config file
    with open(config, "r", encoding='utf-8') as f:
        config = yaml.safe_load(f)
    logging.info("Config:")
    logging.info(config)

    # Merge the instrument information into the database_df
    database_df = database_df.merge(
        scan_mapping_df[["database_id", "maldi_instrument"]],
        how="left",
        left_on="database_id",
        right_on="database_id"
    )

    bin_cols = [x for x in database_df.columns if x.startswith("BIN_")]

    def _helper(row):
        """Set all bin_cols to zero if they are below the relative intensity threshold
        for the given instrument

        Inputs:
            row: a row of the dataframe
        Returns:
            row: the modified row
        """
        inst = row["maldi_instrument"]
        if pd.isna(inst):
            inst = None
        try:
            c = config.get(inst, config["general"])
        except KeyError as exc:
            raise ValueError(f"Instrument {inst} not found in config file and no 'general' config was provided.") from exc
        thresh = c.get("relative_intensity", 0.0)

        if thresh > 0.0:
            max_intensity = row[bin_cols].max()
            if pd.isna(max_intensity) or max_intensity == 0:
                # If all intensities are zero, do nothing
                return row

            relative_thresh = max_intensity * thresh
            row[bin_cols] = row[bin_cols].apply(lambda x: x if x >= relative_thresh else 0)

        return row        

    database_df = database_df.apply(_helper, axis=1)
    database_df = database_df.drop("maldi_instrument", axis=1)

    return database_df

def output_database(database_df, output_mgf_filename, output_scan_mapping, output_spectra_folder, bin_size=1.0):
    database_id_to_scan_list = []

    with open(output_mgf_filename, "w", encoding='utf-8') as o:
        database_list = database_df.to_dict(orient="records")

        for database_entry in database_list:
            output_dictionary = {}

            row_id = database_entry["row_count"]

            scan_number = row_id + 1

            o.write("BEGIN IONS\n")
            o.write("SCANS={}\n".format(scan_number))
            o.write("TITLE={}\n".format(database_entry["scan"]))

            database_id_to_scan_obj = {}
            database_id_to_scan_obj["database_id"] = database_entry["scan"]
            database_id_to_scan_obj["mgf_scan"] = scan_number
            database_id_to_scan_list.append(database_id_to_scan_obj)

            output_dictionary["database_id"] = database_entry["scan"]

            # Finding all the masses
            all_binned_masses = [x for x in database_entry.keys() if x.startswith("BIN_")]

            peaks_list = []
            for binned_mass in all_binned_masses:
                intensity = database_entry[binned_mass]
                mz = float(binned_mass.replace("BIN_", "")) * bin_size

                if intensity > 0:
                    o.write("{} {}\n".format(mz, intensity))

                    peak_obj = {}
                    peak_obj["mz"] = mz
                    peak_obj["i"] = intensity

                    peaks_list.append(peak_obj)

            output_dictionary["peaks"] = peaks_list
            
            o.write("END IONS\n")

            # Writing out as json per file
            path_output_folder = os.path.join(output_spectra_folder, database_entry["scan"][0:4])
            os.makedirs(path_output_folder, exist_ok=True)
            path_to_json = os.path.join(path_output_folder, database_entry["scan"] + ".json")

            with open(path_to_json, "w") as f:
                f.write(json.dumps(output_dictionary, indent=4))

    # Writing out the mapping
    database_id_to_scan_df = pd.DataFrame(database_id_to_scan_list)
    database_id_to_scan_df.to_csv(output_scan_mapping, sep="\t", index=False)


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('database_mzML')
    parser.add_argument('database_scan_mapping_tsv', help="this file maps the scan in the mzML into the database_id")
    parser.add_argument('output_database_mgf', help="This is the merged database file output as an MGF file")
    parser.add_argument('output_mapping', help="This is the output tsv mapping from database_id to scan number in the MGF file")
    parser.add_argument('output_spectra_json', help="This is where we output the processed data as individual json files")
    parser.add_argument('--bin_size', default=1.0, type=float, help="The bin size to use for binning the data")
    parser.add_argument('--config', default=None, required=False, help="YAML file containing instrument-specific peak filtering configurations")
    
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    bin_size = float(args.bin_size)

    # Loading the database, this will also merge the spectra
    database_df = load_database(args.database_mzML, args.database_scan_mapping_tsv, bin_size=bin_size)

    # Instrument-Specific Postprocessing (Relative Intensity Peak Filtering)
    if args.config:
        logging.info("Config file provided, performing instrument-specific peak filtering")
        database_df = peak_filtering(database_df, args.database_scan_mapping_tsv, args.config)
    else:
        logging.info("No config file provided, skipping instrument-specific peak filtering")

    # Create a row count column, starting at 0, counting all the way up, will be useful for keeping track of things when we do matrix multiplication
    database_df["row_count"] = np.arange(len(database_df))

    # Updating filenames in database
    database_df["filename"] = os.path.basename(args.database_mzML)

    # Writing out the database itself so that we can more easily visualize it
    output_database(database_df, args.output_database_mgf, args.output_mapping, args.output_spectra_json, bin_size=bin_size)

if __name__ == '__main__':
    main()