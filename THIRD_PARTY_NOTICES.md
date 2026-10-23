# Third-party notices

## Matcher source

This project derives from [meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching), imported as a local source snapshot. The exact upstream revision has not been verified. [Source provenance](docs/source-provenance.md) describes the local history and changes.

The original [BSD-2-Clause LICENSE](LICENSE) is preserved verbatim, including its incomplete `Copyright (c) 2018,` line. No copyright holder has been inferred or substituted. Source and binary distributions must retain applicable notices, conditions and disclaimers.

The algorithm follows the LINEMOD gradient-orientation approach and uses OpenCV for image processing. The imported documentation discusses modifications relative to OpenCV LINEMOD; the exact historical OpenCV source revision and corresponding notices have not been verified. The current OpenCV license must not be assumed to retroactively identify historical source licensing.

## Bundled MIPP

The `MIPP/` directory is an inherited, locally modified snapshot of [MIPP](https://github.com/aff3ct/MIPP). Its exact upstream revision is unverified. Full notices are retained in the distributed files:

| Files | Retained notice |
| --- | --- |
| `MIPP/mipp.h` | MIT; Copyright (c) 2016 MIPP; author Adrien Cassagne |
| `MIPP/math/sse_mathfun.h`, `.hxx` | Copyright (C) 2007 Julien Pommier; zlib-style license |
| `MIPP/math/neon_mathfun.h`, `.hxx` | Copyright (C) 2011 Julien Pommier; zlib-style license |
| `MIPP/math/avx_mathfun.h`, `.hxx` | Copyright (C) 2012 Giovanni Garberoglio; zlib-style license; derived from Julien Pommier's code |
| `MIPP/math/avx512_mathfun.h`, `.hxx` | Copyright (C) 2017 Adrien Cassagne; MIT notice; derived from Julien Pommier's code |

This index does not replace the complete license text in those files. Preserve applicable notices, including embedded math-code licenses, when redistributing headers or binaries.

## External OpenCV and toolchain

OpenCV 4 is an external build/runtime dependency, not bundled in this source release. Use the LICENSE, NOTICE and third-party notices supplied with the actual OpenCV version you distribute. Compiler and optional OpenMP runtimes also carry their own redistribution terms. This source release does not bundle those runtimes.

## Images, datasets and research material

Release 0.1.0 contains no image dataset, SMD file, paper PDF or generated matching result. The example generates its own simple raster shapes in memory. Historical snapshots may contain earlier research assets; the root source-code license does not relicense third-party data, papers or private input material retained in Git history.

After 0.1.0, real LED and magnetic-part photographs and two sample SMD models were added under `examples/data/`, with matching previews under `docs/images/`. These inputs were supplied for this project and published with the provider's permission. They are separate from the upstream matcher source and are not an upstream benchmark. See [sample provenance](examples/data/README.md); no additional third-party data rights are inferred from the source-code license.
