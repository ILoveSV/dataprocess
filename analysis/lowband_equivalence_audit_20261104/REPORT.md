# Archived voltage and band-limited equivalence audit

## Scope

Date: 2026-11-04. No power-supply commands were issued by this analysis.
Five existing exact archives were inspected, not a complete experimental rerun.
Original acquisitions and previous analysis products were not modified.

This audit separates measured archived voltage from a synthetic waveform check.
No inspected acquisition records a DPS150 sinusoidal electrode excitation and
a simultaneous TC response. Nothing here demonstrates physical source equivalence.

## Retained data

The selected metadata describe 400 kHz, 12-channel voltage acquisitions.
The low-rate archive retains 4 kHz voltage traces after an elliptic anti-alias
filter (1.8 kHz passband, 2 kHz stopband, nominal 100 dB stop attenuation).
The coefficient/DC-normalization response at 1, 2, 5 and 10 Hz is recorded
in manifest.json. This is a processing-filter response, not a sensor response.
The separate 10 Hz summary is not appropriate for a 1-5 Hz waveform audit.

Each acquisition was screened with the repository's existing dynamic channel
quality helper, including segment-bandpower instability. Both automatically
bad and suspect channels were excluded for this descriptive audit. These flags
are screening decisions, not proof of defective hardware. Channels were not
concatenated. Different retained channel sets cannot establish a condition effect.

## Measured voltage results

The 4 kHz trace was digitally low-passed with a sixth-order Butterworth filter
at 10 Hz using forward/backward filtering and resampled to 100 Hz. Metadata-defined
stable intervals were used, then linear trends removed. Welch spectra used up to
20-second segments; RMS below is integrated over 0.1-10 Hz after this processing.
The cutoff is not a brick wall: near-cutoff amplitude is attenuated.

| Record | Retained channels | 0.1-10 Hz RMS, channel median (uV) |
|---|---:|---:|
| TC1 VFD background | 11 | 13.288 |
| TC2 VFD background | 9 | 12.849 |
| TC2 VFD 4 kHz carrier / 50 Hz run | 10 | 13.622 |
| TC2 electrochemical background | 10 | 13.167 |
| TC2 historical cp3000near label | 10 | 13.256 |

The historical CP label is not an independently measured current waveform.
Its switching schedule is not 2 Hz; the descriptive 2 Hz fits in the CSV are
arbitrary-frequency projections, not target detections or detection thresholds.
The same applies to all other historical 2 Hz projections.

Raw whole-record standard deviations are also saved. Their different interval,
detrending and bandwidth prevent interpreting their ratio to lowband RMS as a
calibrated gain or sensitivity improvement. All values are detector-output volts,
not electric-field units. No condition classification or significance test was run.

## Synthetic digital-filter check

Separate synthetic 1, 2 and 5 Hz sinusoids were compared with uniformly held
sinusoidal samples at 200 updates/s. The arbitrary amplitude is 10 uV peak in the
voltage-output domain; it is not a measured detector response or an applied field.
No electrode dynamics, output quantization, jitter, power-supply dynamics, sensor
transfer function or nonlinearities were modeled.

After the same numerical 10 Hz low-pass and removing the deterministic hold delay,
relative RMS differences are about 0.00410%, 0.01641% and 0.10252%, respectively.
Before delay alignment they are about 1.49%, 2.98% and 7.46% on the 4 kHz grid.
The grid's effective hold delay is 2.375 ms, versus 2.5 ms for a continuous hold;
the continuous ideal 2 Hz phase lag is 1.8 degrees, the numerical grid gives
1.71 degrees. This discretization is documented rather than interpreted as hardware.

The continuous ideal base gain is sinc(1/N), where N is points per cycle.
At 2 Hz and N=100 it is 0.9998355. Ideal image frequencies start at 198/202 Hz.
Suppressing those images leaves a nearly identical low-frequency component.
This checks the numerical argument only; no real-noise detection power is inferred.

## Interpretation

Existing voltage traces support a band-limited analysis endpoint, with separate
reporting of base-frequency amplitude and phase. For a stable linear field receiver,
matching the electric-field component at its input produces matching output
components at that frequency. A known field-scale mapping can likewise give a
known output-scale mapping without assuming the complete waveforms are equal.

Output filtering cannot prove that the input was an electric field, establish an
unknown electric-field-to-voltage calibration, remove in-band nonlinear products,
undo analog aliasing/rectification, or reconstruct a signal lost by saturation.
Quantization and electrode nonlinearity can create low-order harmonics inside the
analysis band, unlike the high-frequency images of the ideal hold model.

Supported statement: a low-frequency/base-frequency equivalent-source framework
is theoretically reasonable and numerically implementable on the retained voltage
data. Unsupported statement: the current DPS150/electrode/TC chain is already
physically equivalent to a real vessel, or has demonstrated a numerical percentage
of field-response similarity.

## Reproduction

Run: `D:\Anaconda\python.exe -X utf8 scripts\audit_lowband_equivalence_20261104.py`.
The script completed successfully and its three synthetic base-gain assertions passed.
Input hashes, channel decisions, per-channel measurements and synthetic-only
metrics are saved alongside this report. The figure's first two panels are
measured TC2 background; its third panel is synthetic only.

## References

- Zero-order hold: https://www.analog.com/en/resources/technical-articles/equalizing-techniques-flatten-dac-frequency-response.html
- Electrochemical nonlinearity: https://www.gamry.com/application-notes/eis/basics-of-electrochemical-impedance-spectroscopy/
- Numerical filtering: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
- Polyphase resampling: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
