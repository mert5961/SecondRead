# Data used for the image step

No scan data is stored in this repo. The image step uses one patient from a public research collection:

- **Collection:** RIDER Lung CT, The Cancer Imaging Archive (TCIA). 32 patients with lung cancer, each scanned
  twice within minutes ("coffee-break" scans), de-identified by TCIA.
- **Licence:** Creative Commons Attribution 4.0 International (as listed by the TCIA API for every series).
- **Patient used:** `RIDER-1129164940`, study of 2006-09-20: two CT series (236 and 213 slices) and the two
  RTSTRUCT outline files (`TEST`, `RETEST`), each with a manual and an automatic tumor outline.
- **Get it:** TCIA REST API, `getSeries?Collection=RIDER Lung CT&PatientID=RIDER-1129164940`, then
  `getImage?SeriesInstanceUID=...` for the four series. Put them in folders `CT_236`, `CT_213`,
  `RTSTRUCT_TEST`, `RTSTRUCT_RETEST`.

**Credit.** Please cite the collection as TCIA asks on its page (RIDER Lung CT, and the segmentation labels
added to it), plus Clark et al., *The Cancer Imaging Archive (TCIA)*, J Digit Imaging 2013.
The exact citation text for the outlines is to be copied from the TCIA collection page before this is shared
more widely (not yet verified by me).

The figure `figures/repeat-scan.png` is derived from this data under the same licence.
