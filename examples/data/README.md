# Real matching samples

These are photographs and existing contour models supplied for this project, published with the provider's permission. They are not generated scenes. The PNG inputs are lossless grayscale conversions of the original BMP files; each decoded grayscale pixel was checked for equality. The two SMD files are unchanged byte copies.

| Directory | Inputs | Model | Template source |
| --- | --- | --- | --- |
| `led/` | `1.png`–`8.png`, 768 × 576 | `ku.smd` | A 184 × 184 crop of `1.png`, at x=389, y=225. The stored contour describes the two central electrodes. |
| `magnet/` | `M01.png`–`M07.png`, 640 × 480 | `moban.smd` | The full `M01.png` image. The contour describes the part outline and central hole. |

`manifest.json` records original filenames, source-file hashes, distributed-file hashes and decoded grayscale-pixel hashes. These names identify the original local samples; original BMP copies are not needed to run the example.

Both source images remain in the demonstration and are identified separately. The other 13 photographs are different from the source images, but all 15 have been used during development. This is a small positive-image regression set, with no sealed holdout or negative-image evaluation. Similarity scores are not detection probabilities.

The C++ showcase reads only the two checked SMD layouts included here. It is not a general SMD importer. It does not interpret the second embedded image as a training mask or infer unverified format fields.

Build from the repository root, then run:

```sh
mkdir showcase-output
build/showcase_example examples/data showcase-output
```

See [matching examples](../../docs/matching-examples.md) for settings and observed results.
