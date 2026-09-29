# Exact analysis and raw-data retention plan

## What changed

The exact path is selected with `--exact`. It replaces the earlier cache path
for conclusions and makes the following corrections:

1. Raw samples remain `float64` until detrending and PSD calculation. The old
   three-window cache converted approximately 5 V absolute samples to
   `float32` too early and quantized away part of the sub-microvolt high-frequency
   signal.
2. Low-rate traces use a 100 dB-stopband anti-alias filter before decimation
   from 400 kHz to 4 kHz, followed by polyphase resampling to 10 Hz.
3. All stable samples contribute to 262144-sample, 50%-overlap Welch spectra.
   The final endpoint segment is included so the end of the record is covered.
4. Eight consecutive time epochs retain their own complete 0-200 kHz PSD.
   Per-segment band powers are also retained. This allows line and band
   stability to be checked over the complete acquisition rather than three
   selected windows.
5. Channel health is classified independently for every acquisition. A channel
   is excluded only for hard failure or corroborating time-domain health
   outliers; temporal spectral variability alone is retained as a warning.
   Comparisons use the healthy-channel intersection of all participating files.
   Key VFD band contrasts also retain a stricter sensitivity result that excludes
   both bad and suspect channels.
6. Channels are technical observations within one acquisition, not independent
   experimental repeats. Exact reports use matched-channel controls and
   file-level summaries. Welch segments are descriptive time coverage only.
7. Low-frequency blind scans use the anti-aliased 10 Hz trace and are marked
   exploratory because candidate selection and evaluation occur in the same
   file.

## Exact archive contents

Each TDMS file has one archive directory containing:

- `metadata.json`: source identity, acquisition properties and all analysis parameters.
- `health.json`: per-channel range, noise, clipping, flat-line and non-finite checks.
- `low_rate.npz`: complete anti-aliased 4 kHz and aligned 10 Hz traces.
- `envelopes.npz`: complete 10 Hz block/envelope features.
- `welch.npz`: complete stable-interval mean PSD, eight stable-interval epoch PSDs,
  every Welch segment's
  five band powers and dominant-peak tracks.
- `raw_snippets.npz`: centered 1 s raw snippets at 20%, 50% and 80%, with
  `float64` offsets so the absolute voltage is recoverable.
- `COMPLETE`: written only after all archive files have been saved successfully.

This archive is sufficient to reproduce the analyses currently defined in the
project. It is not mathematically equivalent to the raw TDMS. After raw deletion
it will not support arbitrary new high-frequency waveform filters, cross-channel
phase/coherence, sub-epoch transient searches, or re-decoding of TDMS/ADC data.

## Files that must be retained

1. Every case directory below each `exact_archive` root.
2. All MP4, M4A, WAV, JPG and related experiment media. These are small relative
   to TDMS and contain independent timing and water-cycle evidence.
3. Final CSV tables, plots, analysis manifests and reports below `results`.
4. The analysis code snapshot, Python/package versions and preservation manifests.
5. Experiment notes, filename-to-condition labels, detector placement records,
   VFD manuals/settings and COMSOL models/results.

`.tdms_index` files do not need to be retained after their TDMS files are deleted.

## Deletion gate

Do not delete raw TDMS until all checks below pass:

1. Every raw TDMS has exactly one version-4 exact archive and a `COMPLETE` marker.
2. `raw_tdms_manifest.csv` contains source size, modification time and SHA-256.
3. `retained_file_manifest.csv` contains SHA-256 for every archive, media and code file.
4. Both experiment reports run with `--exact` while loading completed archives.
5. Source counts, sample counts, durations and channel counts agree with the archive metadata.
6. The preservation package and results exist on two independent storage devices.
7. At least a random sample of archive hashes has been verified from the second copy.

Only after all seven checks pass should the TDMS files be removed.
