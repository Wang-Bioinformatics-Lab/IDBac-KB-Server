import sys
import os
import glob
import argparse
import pandas as pd
import json
from psims.mzml.writer import MzMLWriter
import logging

def process_spectrum(json_filename, out_mzml, scan_mapping_file, json_file, scan_counter, dry_run=False):
    if dry_run:
        # Set files to None for safety
        out_mzml = None
        scan_mapping_file = None
        json_file = None


    database_id = os.path.basename(json_filename).replace(".json", "")
    
    with open(json_filename, "r") as f:
        spectrum_dict = json.load(f)
    
    spectrum_dict["database_id"] = database_id
    
    # Write spectrum to JSON file immediately
    if not dry_run:
        json.dump(spectrum_dict, json_file)
        json_file.write("\n")
    
    spectrum_list = spectrum_dict["spectrum"]
    logging.info("Processing %s with %d spectra", json_filename, len(spectrum_list))
    
    instrument_model = spectrum_dict.get("MALDI instrument", "unknown")
    instrument_model = str(instrument_model).strip().lower().replace(" ", "_").replace("-", "_")

    for spectrum in spectrum_list:
        mz_array = [x[0] for x in spectrum]
        intensity_array = [x[1] for x in spectrum]

        if not dry_run:
            out_mzml.write_spectrum(
                mz_array, intensity_array,
                id=f"scan={scan_counter}", params=[
                    "MS1 Spectrum",
                    {"ms level": 1},
                    {"total ion current": sum(intensity_array)},
                    {"instrument model": instrument_model},
                ])

        # Write scan mapping immediately
        if not dry_run:
            scan_mapping_file.write(f"{scan_counter}\t{database_id}\t{instrument_model}\n")

        scan_counter += 1
    
    print("Returning scan_counter", scan_counter)
    return int(scan_counter)

def main():
    parser = argparse.ArgumentParser(description='Formatting the entire Database.')
    parser.add_argument('input_json_folder')
    parser.add_argument('output_library_json')
    parser.add_argument('output_library_scan_mapping_txt')
    parser.add_argument('output_library_mzml')
    
    args = parser.parse_args()

    all_json_entries = glob.glob(os.path.join(args.input_json_folder, "**/*.json"), recursive=True)
    print(all_json_entries)
    logging.info("Found %d JSON files in the input folder.", len(all_json_entries))
        
    # Intial Dry Run to get the count of spectra
    dryrun_scan_counter = 1
    for json_filename in all_json_entries:
        with open(json_filename, "r") as f:
            spectrum_dict = json.load(f)
        spectrum_list = spectrum_dict["spectrum"]
        dryrun_scan_counter = process_spectrum(json_filename, None, None, None, dryrun_scan_counter, dry_run=True)

    dryrun_scan_counter = int(dryrun_scan_counter)
    print('dryrun_scan_counter', dryrun_scan_counter)
    logging.info("Total number of scans to be processed: %d", dryrun_scan_counter - 1)
    
    with open(args.output_library_json, "w") as json_file, \
        open(args.output_library_scan_mapping_txt, "w") as scan_mapping_file, \
        MzMLWriter(open(args.output_library_mzml, 'wb'), close=True) as out_mzml:
    
        # Write headers into scan_mapping_file
        scan_mapping_file.write("scan\tdatabase_id\tmaldi_instrument\n")

        out_mzml.controlled_vocabularies()
        scan_counter = 1
        with out_mzml.run(id="my_analysis"):
            with out_mzml.spectrum_list(count=dryrun_scan_counter-1):  # Minus 1 since we start from 1
                for json_filename in all_json_entries:
                    scan_counter = process_spectrum(json_filename, out_mzml, scan_mapping_file, json_file, scan_counter)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
