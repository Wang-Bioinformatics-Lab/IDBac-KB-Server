# Load the MALDIquant package
library(MALDIquant)
library(MALDIquantForeign)

process_mzML_file <- function(input_file, output_file) {
  # Read the mzML file
  spectra <- importMzMl(input_file)

  spectra <- transformIntensity(spectra, method="sqrt")

  spectra <- MALDIquant::smoothIntensity(spectra,
                                         method = 'SavitzkyGolay',
                                         halfWindowSize = 20L)

  # Perform baseline subtraction using the SNIP algorithm
  spectra_baseline_corrected <- removeBaseline(spectra, method="TopHat")

  # Perform peak detection
  peaks <- detectPeaks(spectra_baseline_corrected,
                      method='MAD',
                      halfWindowSize=20L,
                      SNR=3)

  # Export the processed spectra as an mzML file
  exportMzMl(peaks, output_file)
}

# Get the input and output file paths from command line arguments
args <- commandArgs(trailingOnly = TRUE)
input_file <- args[1]
output_file <- args[2]

process_mzML_file(input_file, output_file)
