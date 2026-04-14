SEAS5 Resolution Work Plan

1. Validate the archive layout and file schema.
   Confirm variable names, time axes, grid definitions, ensemble layout, and the
   exact overlap period between SEAS5 hindcasts and CMEMS anomalies.

2. Finalize the verification design.
   Lock down lead handling, detrending rules, mask treatment, and whether skill
   is summarized by lead, by region, or as an all-lead aggregate.

3. Build reproducible loaders and preprocessing.
   Load native and `1x1` SEAS5 SSH, compute ensemble means where needed, load
   altimetry anomalies, standardize units to meters, and align valid times.

4. Generate common-resolution products.
   Use proper regridding from native SEAS5 to regular `0.25 deg` altimetry
   coordinates. Use boxcar averaging for `0.25 -> 1 deg` and `1 -> 3 deg`
   products on regular grids.

5. Compute skill metrics.
   For each target resolution, compute `ACC` and `RMSE` across hindcast starts
   for each lead month and save gridded outputs.

6. Compare matched-resolution and fixed-observation experiments.
   Evaluate:
   - SEAS5 and altimetry at the same resolution
   - SEAS5 at `0.25`, `1`, and `3 deg` against altimetry fixed at `0.25 deg`

7. Summarize results.
   Produce maps, domain averages, and skill-difference diagnostics that test
   whether smoothing improves forecast skill.

8. Document caveats and next steps.
   Record unresolved masking choices, sensitivity to regridding details, and any
   data gaps or lead-time inconsistencies.
