# Matching real LED and magnetic parts

The photographs and SMD contour models below were supplied for this project. The input scenes are real images. The example reads the existing stored contours, builds angle/scale template banks, and runs the current C++ matcher; it does not generate the scene or learn a contour from a searched image.

## LED electrode localization

![LED original images, matching overlays and detail crops](images/led-matching.jpg)

This model describes the **two central electrodes**, not the LED's outer circular package. The images show different positions, orientations and reflective backgrounds. Each row contains the full original field of view, the highest-scoring matching overlay, and a labelled detail crop of that same result. Green points are transformed template features. Yellow shows the transformed model region and its center; it is not an independently annotated object box.

The three displayed photographs are `2.png`, `6.png` and `8.png`. All eight LED inputs were searched, including the template-source photograph `1.png`. The SMD's embedded 184 × 184 template image is pixel-identical to the crop at x=389, y=225 in `1.png`.

## Magnetic-part outline and hole localization

![Magnetic-part original images, matching overlays and detail crops](images/magnet-matching.jpg)

The stored contour follows the outside of the part and its central hole. The displayed `M02.png`, `M04.png` and `M06.png` exercise rotation and different apparent sizes. Their winning template scales are 1.00, 0.70 and 1.25. Those are template-bank settings, not independently measured physical scales.

All seven inputs were searched. `M01.png` is the template source: its full grayscale image is pixel-identical to the first embedded SMD image. Earlier development runs with a narrower 0.90–1.10 scale range missed `M04`–`M06`. This demonstration uses the same wider bank and full-bank padding checks for every image. It is a regression on previously inspected images, not an unseen test result.

## Reproduce

Build the repository, then run from its root:

```sh
mkdir showcase-output
build/showcase_example examples/data showcase-output
```

On Windows use `build/showcase_example.exe`, or `build/Release/showcase_example.exe` with a multi-configuration generator. The output directory must already exist. No Python is required. The source is [examples/showcase.cpp](../examples/showcase.cpp); inputs and provenance are in [examples/data](../examples/data/README.md).

The program saves all 15 result PNGs, `results.csv`, `timings.csv`, `candidates.csv`, `padding_preflight.csv` and `run_config.json`. All returned candidates from all five measured calls are retained in `candidates.csv`. Only the highest-scoring candidate from the first measured call is drawn. There is no extra spatial NMS in this example; returned candidate counts are pose hypotheses, not numbers of physical parts. Empty results are retained rather than omitted.

The README contact sheets were assembled from these output PNGs. Their first two columns retain the original field of view; the third column is explicitly cropped for inspection. The PNG source inputs are lossless grayscale conversions of the original BMPs, verified pixel for pixel. The SMD files are unchanged; [manifest.json](../examples/data/manifest.json) records their hashes and the input-pixel hashes.

## Fixed configuration and observed results

| Setting | LED | Magnetic part |
| --- | --- | --- |
| Original image | 768 × 576 | 640 × 480 |
| Stored feature counts, three levels | 236 / 111 / 46 | 1214 / 605 / 301 |
| Pose bank | 900 templates | 3060 templates |
| Bank angles | 0–358°, step 2° | 0–358°, step 2° |
| Bank scales | 0.90–1.10, step 0.05 | 0.60–1.40, step 0.05 |
| Pyramid strides / score threshold | 4 / 8 / 8; 75 | 4 / 8 / 8; 75 |
| Padded matching input | 896 × 704 | 896 × 832 |
| Images with a returned candidate scoring ≥75 | 8 of 8 | 7 of 7 |
| Highest scores, excluding source image | 86.02–93.54 | 89.70–99.49 |
| Mean of per-image median match times | 35.395 ms | 25.459 ms |

Run on 2026-10-23: Windows, Intel Core i5-13500HX, GCC 15.1 Release/SSE4.1, OpenCV 4.12 with one thread, OpenMP with four threads and `OMP_WAIT_POLICY=PASSIVE`. Each image receives one warmup and five measured calls using a reused workspace. Time covers the complete `detector.match` call; image loading, template-bank construction, padding, CSV output, drawing and saving are excluded. These are descriptive measurements from one run, not a latency guarantee or an optimization speedup comparison.

Every bank pose is checked against both refinement levels before matching: the padded input extent must be at least `(template_extent + 16 * stride) * 2^level`, with 32-pixel alignment. Only the right/bottom padding grows when the bank requires it. A successful match must not be traded away for an invalid coarse-to-fine search region.

The five measured calls returned identical complete candidate lists for each image. A separate OpenMP-disabled build also reproduced all complete candidate lists. The run checked 7,920 pose/level padding constraints and retained 1,470 candidate rows across 75 measured calls. See [all image results](matching-results.csv), [all 90 warmup/measured timings](matching-timings.csv) and [run configuration](matching-run.json).

The table below reports the best candidate in each image. “Source” identifies the two template-source self-checks. Angles and scales describe the winning stored pose; no angle/scale ground truth is available.

| Sample | Role | Best score | Bank angle | Bank scale | Returned candidates | Median match ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| led/1.png | Source | 98.411 | 0° | 1.00 | 52 | 25.712 |
| led/2.png | Additional | 88.771 | 356° | 1.05 | 43 | 29.079 |
| led/3.png | Additional | 90.996 | 0° | 1.00 | 33 | 27.541 |
| led/4.png | Additional | 86.017 | 2° | 1.00 | 15 | 30.964 |
| led/5.png | Additional | 89.619 | 358° | 1.05 | 37 | 35.848 |
| led/6.png | Additional | 87.606 | 172° | 0.95 | 35 | 42.424 |
| led/7.png | Additional | 93.538 | 176° | 1.00 | 41 | 34.993 |
| led/8.png | Additional | 86.123 | 172° | 1.05 | 15 | 56.599 |
| magnet/M01.png | Source | 99.856 | 0° | 1.00 | 3 | 21.093 |
| magnet/M02.png | Additional | 99.217 | 234° | 1.00 | 3 | 23.271 |
| magnet/M03.png | Additional | 99.012 | 140° | 1.00 | 4 | 22.840 |
| magnet/M04.png | Additional | 99.485 | 312° | 0.70 | 5 | 27.921 |
| magnet/M05.png | Additional | 98.250 | 260° | 0.70 | 4 | 32.145 |
| magnet/M06.png | Additional | 98.723 | 178° | 1.25 | 2 | 23.244 |
| magnet/M07.png | Additional | 89.703 | 82° | 0.90 | 2 | 27.701 |

## Evaluation limits

All 15 photographs have been used during development. There are 13 additional photographs and two template-source images, with no sealed holdout or dedicated negative-image evaluation. Returning a candidate above the threshold does not establish correct detection, calibrated confidence, recall or a false-positive rate. The images let users inspect contour placement; they are not a general industrial accuracy benchmark.

Unsigned gradient directions and LED electrode symmetry can produce roughly 180° orientation ambiguity. No subpixel position or calibrated angle/scale accuracy is established here. The sample reader supports only the two supplied, checked SMD layouts; support for other SMD files is not implied.
