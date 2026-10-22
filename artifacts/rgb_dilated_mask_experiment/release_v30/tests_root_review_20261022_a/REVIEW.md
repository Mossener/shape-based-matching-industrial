# Independent V30 publication review

The final verifier source was reviewed and executed against ten isolated mocked
Git-index fixtures. Under both SHA1 and SHA256 formats, the valid fixture passed
and wrong index bytes, an unrelated staged deletion, a missing index member and
an unmerged index were rejected by their intended gates. The saved run exited
0 with all ten tests passing and unchanged source hashes. No real Git commands,
index mutations, image reads or matcher calls occur in these fixtures.

Final reviewed verifier SHA256:
`1d4b8b8fbf1a2791da41114035c1f2d640a45518eea8f1d5ce4ee780f0ddb4e0`.

Saved fixture receipt SHA256:
`3916c842514f1819c2287c144e9f46ff4493d2c4917a413d51eab79209c4d442`.

The earlier independent full inventory/index scan covered 21,187 selected files
and all 673 inherited V29 selected paths. It found no forbidden image/SMD/native
binary or archive suffix, symlink, path traversal, unmerged index, unrelated
staged path or missing newly selected path. No individual selected file exceeded
100 MiB: the maximum was the 91,064,499-byte numeric `template_layers.csv`.
During that scan `.gitattributes` was being edited by root and therefore had a
known inventory/index mismatch. Root must refresh the completion-record pins,
the final selection and exact staged bytes after adding these review files;
this review does not claim that the final index has already passed.

The final source now checks full staged changes including deletions, resolved
path containment and symlink rejection, per-file size limits, stage-zero index
entries, regular file modes and exact Git blob identities for all selected
files plus the inventory. No blocking issue was found in this reviewed source
for the selected V30 scope. The fixture receipt is synthetic verifier evidence,
not a repeated native quality or performance measurement.
