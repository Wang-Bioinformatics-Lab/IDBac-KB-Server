# Load libraries
library(MALDIquant)
library(MALDIquantForeign)
library(yaml)

filter_by_intensity <- function(peaks, min_relative_intensity) {
  # Get maximum intensity across all peaks
  max_intensity <- max(sapply(peaks, function(p) max(intensity(p))))

  # Calculate absolute intensity threshold
  threshold <- min_relative_intensity * max_intensity

  # Filter peaks in each spectrum
  filtered_peaks <- lapply(peaks, function(p) {
    p[intensity(p) >= threshold]
  })
  return(filtered_peaks)
}

process_mzML_file <- function(input_file, output_file, cfg) {
  # Debug show input_file
  print(paste("Processing file:", input_file))
  
  # Read the mzML file
  spectra <- importMzMl(input_file)

  # Get the generic config
  inst_cgf <- cfg[['shimadzu_maldi_8020']]

  # Transform intensity
  spectra <- transformIntensity(
    spectra,
    method = inst_cgf$transformIntensity$method
  )

  # Smooth
  spectra <- MALDIquant::smoothIntensity(
    spectra,
    method = inst_cgf$smoothIntensity$method,
    halfWindowSize = as.integer(inst_cgf$smoothIntensity$halfWindowSize)
  )

  # Baseline subtraction
  spectra_baseline_corrected <- removeBaseline(
    spectra,
    method = inst_cgf$removeBaseline$method
  )

  # Print all peak detection args
  print(paste("Peak detection args:", 
              paste("method =", inst_cgf$detectPeaks$method),
              paste("halfWindowSize =", inst_cgf$detectPeaks$halfWindowSize),
              paste("SNR =", inst_cgf$detectPeaks$SNR)
  ))

  # Peak detection
  peaks <- detectPeaks(
    spectra_baseline_corrected,
    method = inst_cgf$detectPeaks$method,
    halfWindowSize = as.integer(inst_cgf$detectPeaks$halfWindowSize),
    SNR = inst_cgf$detectPeaks$SNR
  )

  peaks <- filter_by_intensity(peaks, inst_cgf$filterPeaks$relative_intensity)

  # Export
  exportMzMl(peaks, output_file)
}

# Get args: input, output, config section
args <- commandArgs(trailingOnly = TRUE)
input_file <- args[1]
output_file <- args[2]
config <- args[3]

config <- yaml::read_yaml(config)

protein_config <- config$ProteinSpectrumProcessing

process_mzML_file(input_file, output_file, protein_config)