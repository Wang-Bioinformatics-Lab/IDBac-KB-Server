import argparse
import os
import glob

def main():
    parser = argparse.ArgumentParser(description="Create a merged spectrum from multiple spectra")
    parser.add_argument("idbac_full_spectra_json", help="idbac_full_spectra_json")
    parser.add_argument("idbac_filtered_spectra_folder", help="idbac_filtered_spectra_folder")
    parser.add_argument("output_filtered_spectra_json", help="output_filtered_spectra_json")
    args = parser.parse_args()

    # Getting all the json files
    all_json_entries = glob.glob("{}/**/*.json".format(args.idbac_filtered_spectra_folder), recursive=True)

    spectra_list = []
    # Reading the full spectra
    for json_filename in all_json_entries:
        print(json_filename)
        with open(json_filename, "r") as f:
            entry = json.loads(f.read())
            entry["database_id"] = os.path.basename(json_filename).replace(".json", "")

            spectra_list.append(entry)

    # lets write this out
    with open(args.output_filtered_spectra_json, "w") as f:
        f.write(json.dumps(spectra_list))


if __name__ == "__main__":
    main()