# Data used for the image step

No scan data is stored in this repo. The image step uses one patient from a public research collection:

- **Collection:** RIDER Lung CT, The Cancer Imaging Archive (TCIA). 32 patients with lung cancer, each scanned
  twice within minutes ("coffee-break" scans), de-identified by TCIA.
- **Licence:** Creative Commons Attribution 4.0 International (as listed by the TCIA API for every series).
- **Patient used:** `RIDER-1129164940`, study of 2006-09-20: two CT series (236 and 213 slices) and the two
  RTSTRUCT outline files (`TEST`, `RETEST`), each with a manual and an automatic tumor outline (from the Wee et al. label set below).
- **Get it:** TCIA REST API, `getSeries?Collection=RIDER Lung CT&PatientID=RIDER-1129164940`, then
  `getImage?SeriesInstanceUID=...` for the four series. Put them in folders `CT_236`, `CT_213`,
  `RTSTRUCT_TEST`, `RTSTRUCT_RETEST`.

**Credit** (citations checked against the DOIs on 2026-11-12):

- CT images: Zhao, B., Schwartz, L. H., Kris, M. G., & Riely, G. J. (2015). *Coffee-break lung CT collection
  with scan images reconstructed at multiple imaging parameters* (Version 3) [Dataset]. The Cancer Imaging
  Archive. https://doi.org/10.7937/K9/TCIA.2015.U1X8A5NR
- Tumor outlines (manual and automatic, `GTVp_*`): Wee, L., Aerts, H., Kalendralis, P., & Dekker, A. (2020).
  *RIDER Lung CT Segmentation Labels from: Decoding tumour phenotype by noninvasive imaging using a quantitative
  radiomics approach* (Version 2) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/TCIA.2020.JIT9GRK8
- Both are licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

The figure `figures/repeat-scan.png` is derived from this data under the same licence.
