#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.input_database = ""
// params.bin_size = 10.0

TOOL_FOLDER = "$baseDir/bin"

include { MergeAndOutput as MergeAndOutput1 } from "$baseDir/bin/processes.nf" addParams(output_dir: "./nf_output/1_da_bin")
include { MergeAndOutput as MergeAndOutput5 } from "$baseDir/bin/processes.nf" addParams(output_dir: "./nf_output/5_da_bin")
include { MergeAndOutput as MergeAndOutput10 } from "$baseDir/bin/processes.nf" addParams(output_dir: "./nf_output/10_da_bin")

process formatDatabase {
    publishDir "./nf_output", mode: 'copy'

    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    file idbac_database_folder

    output:
    file 'idbac_database.json'
    file 'idbac_database_scanmapping.tsv'
    file 'idbac_database.mzML'

    """
    python $TOOL_FOLDER/format_database.py \
    $idbac_database_folder \
    idbac_database.json \
    idbac_database_scanmapping.tsv \
    idbac_database.mzML
    """
}

process baselineCorrection2 {
    publishDir "./nf_output/library", mode: 'copy'

    conda "$TOOL_FOLDER/conda_maldiquant.yml"

    input:
    file input_file 

    output:
    file 'baselinecorrected/*.mzML'

    """
    mkdir baselinecorrected
    Rscript $TOOL_FOLDER/baselineCorrection.R $input_file baselinecorrected/${input_file}
    """
}

// process mergeSpectra {
//     publishDir "./nf_output", mode: 'copy'

//     conda "$TOOL_FOLDER/conda_env.yml"

//     input:
//     file idbac_database_mzML
//     file idbac_database_scan_mapping

//     output:
//     file 'output_database.mgf' optional true
//     file 'output_mapping.tsv' optional true
//     file 'output_spectra_json' optional true

//     """
//     mkdir output_spectra_json
//     python $TOOL_FOLDER/merge_spectra.py \
//     $idbac_database_mzML \
//     $idbac_database_scan_mapping \
//     output_database.mgf \
//     output_mapping.tsv \
//     output_spectra_json \
//     --bin_size ${params.bin_size}
//     """
// }

// process prepareOutput {
//     publishDir "./nf_output", mode: 'copy'

//     conda "$TOOL_FOLDER/conda_env.yml"

//     input:
//     file idbac_full_spectra_json
//     file idbac_merged_spectra_json_folder

//     output:
//     file 'output_merged_spectra.json' optional true

//     """
//     python $TOOL_FOLDER/create_consolidated_merged_spectra.py \
//     $idbac_full_spectra_json \
//     $idbac_merged_spectra_json_folder \
//     output_merged_spectra.json
//     """
    
// }

// TODO: We need to merge the full summary with the scan mapping so we know the scan number to show in the summary

workflow {
    database_folder_ch = Channel.fromPath(params.input_database)

    // Downloading Database
    (output_idbac_database_ch, output_scan_mapping_ch, output_idbac_mzML_ch) = formatDatabase(database_folder_ch)

    // Baseline Correct the spectra
    baseline_corrected_database_mzML_ch = baselineCorrection2(output_idbac_mzML_ch)

    // Merging the database spectra
    // (_, _, merged_json_folder_ch) = mergeSpectra(baseline_corrected_database_mzML_ch, output_scan_mapping_ch)

    // Consolidating the merged output
    // prepareOutput(output_idbac_database_ch, merged_json_folder_ch)

    MergeAndOutput1(   baseline_corrected_database_mzML_ch, 
                        output_scan_mapping_ch,
                        output_idbac_database_ch,
                        1,
                        // "./nf_output/1_da_bin"
                    )

    MergeAndOutput5(   baseline_corrected_database_mzML_ch, 
                        output_scan_mapping_ch,
                        output_idbac_database_ch,
                        5,
                        // "./nf_output/5_da_bin"
                    )

    MergeAndOutput10(   baseline_corrected_database_mzML_ch, 
                        output_scan_mapping_ch,
                        output_idbac_database_ch,
                        10,
                        // "./nf_output/10_da_bin"
                    )
}