# Frozen silhouette-source prerequisites

No dataset image has been opened, decoded or matched by this experiment. No real template bank has been trained. Native synthetic tests created two toy masks and called `addTemplate`; matcher calls remain zero.

`private_source_create.json` and `private_source_test_green/` pass. The experiment owns 23 exact V11 Git blob files (7 core and 16 MIPP) in `private_v11/`, plus three independently pinned helper copies in `frozen_helpers/`. The build compiles the actual private `line2Dup.cpp` and explicitly includes private core/MIPP directories. The freezer verifies every private byte against the frozen Git revision rather than trusting a copy hash alone. Root/public matching source is not a runtime compilation dependency of this experiment.

`input_contract_red/` preserves the missing-feature assertion; `input_contract_green/` passes. Its synthetic oracles exercise path rejection, restoration of original JSON/CSV bytes from preservation gzip wrappers, byte-identical bank gzip reuse, all 432 six-object training views and 864 expected inputs, reserved-object exclusion, missing/duplicate views, missing source members, and incorrect original hashes. It opens no dataset member.

`build_source_test_red/` is an environment/wrapper failure, not semantic RED: Windows PowerShell 5 converted native MIPP warning stderr into a terminating error. The first compiler was observed running afterward and fully exited before the second build. Its source wrapper was reconstructed and matched to its saved attempt SHA. The wrapper correction preserves stderr and uses the actual native exit code.

`build_source_test_red2/` builds and its executable exits 1 on the expected alias defect: `Training source must clone binary mask`. Its source-policy stub snapshot is retained. `build_source_test_green/` builds and exits 0 after validating binary uint8 single-channel inputs and returning a clone. It verifies both mutation directions leave the other matrix intact, rejects four invalid masks, and checks `addTemplate` preserves the object mask. Both builds compile the explicit experiment-private V11 core; inherited MIPP/core warnings remain in compiler diagnostics.

| Fixed synthetic extraction | Template ID | Outcome | Feature counts |
| --- | ---: | --- | --- |
| Rectangle mask | -1 | insufficient_features | no successful layer |
| Polygon with diagonal edges | -1 | insufficient_features | no successful layer |

The native detector is unchanged: requested 32/16 features, T 4/8, weak/strong 20/40, and the original erosion/blur/NMS/selection logic. These failures confirm the design's stated risk that binary silhouette training can be rejected. They do not establish the outcome of the six real training banks, identify a unique mechanism, justify changing parameters, or support an accuracy claim. Failed poses will remain visible if the separately reviewed real experiment proceeds.

Source/build/exit snapshots live with each run. Numeric JSON and compiler diagnostics are evidence; build timings are not performance measurements. The real adapter, runtime/compiler closure and real-image stages remain subject to the explicit parent review/CPU gates.
