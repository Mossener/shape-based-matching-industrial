"""Build the explicit V31 evidence selection; never invokes Git or native code.

Existing payload pins are copied and size-checked, not read or rehashed. Only
explicit small metadata/text inputs (at most 16 MiB each) are read and hashed.
Run the frozen publication successor afterwards to verify every payload and
then the exact Git index. No input_pins recursion or filesystem discovery occurs.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

ROOT = Path(__file__).resolve().parents[3]
BASE = "artifacts/rgb_stratified_features_experiment"
SELECTION = BASE + "/PUBLISH_SELECTION_V31.json"
PATHSPEC = BASE + "/PUBLISH_PATHSPEC_V31.nul"
MAX_FILE = 100 * 1024 * 1024
MAX_METADATA = 16 * 1024 * 1024
MAX_EXPORT = 95 * 1024 * 1024
GUARDS = ("guard_reservation.json", "guard_latest.json", "guard_telemetry.jsonl",
          "guard_receipt.json", "stdout.txt", "stderr.txt")
FORBIDDEN = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif",
             ".smd", ".avif", ".heic", ".ico", ".svg", ".exr", ".tga", ".pgm",
             ".ppm", ".pbm", ".pnm", ".exe", ".com", ".o", ".obj", ".dll", ".pyd",
             ".so", ".dylib", ".lib", ".a", ".bin", ".pdb", ".pyc", ".zip", ".7z", ".tar"}
EXPORT_PIN = dict(bytes=22826,
                  sha256="9094d4f4fde321b1c1099bd9f762cc3de9522e8e8894a026555812376323d10f")
REPO_TEXTS = (
    "README.md", "docs/optimization_versions.md",
    "docs/datasets/next-public-dataset-options.md",
    "docs/datasets/post-v31-holdout-external-validation-proposal.md",
    "docs/superpowers/plans/2026-10-23-ordered-contour-verifier.md",
    "docs/superpowers/plans/2026-10-23-ordered-contour-verifier-review.md",
    "docs/superpowers/plans/2026-10-23-ordered-contour-verifier-contract.md",
)
ROOT_TEXTS = (
    "QUALITY_AUDIT_ENTRYPOINT_FAILURES.md", "QUALITY_RESULTS_V31.md",
    "TIMING_RESULTS_V31.md", "ACTUAL_RESULTS_V31.md",
    "complete_quality_evidence.py", "validate_public_training_restore.py",
    "release_v31/FINAL_CANDIDATE_COLLECTION_PLAN.md",
    "release_v31/collect_actual_selection.py", "release_v31/test_collect_actual_selection.py",
    "release_v31/REPORT_REVIEW_V1.md", "INHERITED_PUBLIC_NUMERIC_AVAILABILITY.json",
    "release_v31/COLLECTOR_STATIC_REVIEW_V1.md",
    "release_v31/check_inherited_public_numeric.py",
    "release_v31/inherited_availability_attempt_v1/check_inherited_public_numeric.py",
    "release_v31/inherited_availability_attempt_v1/observed_failure.json",
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, "duplicate JSON key: " + key)
        value[key] = item
    return value


def bare_pin(value):
    need(isinstance(value, dict) and type(value.get("bytes")) is int and
         0 <= value["bytes"] and isinstance(value.get("sha256"), str) and
         re.fullmatch(r"[0-9a-f]{64}", value["sha256"]), "invalid numeric pin")
    return {key: value[key] for key in ("bytes", "sha256")}


class Collector:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.rows = {}
        self.allowed_pools = {}
        self.external_sources = []
        self.unavailable_historical_sources = []
        self.payload_bytes_read = 0

    def relative(self, name):
        need(isinstance(name, str) and name and "\\" not in name and ":" not in name and
             not PureWindowsPath(name).drive and not PurePosixPath(name).is_absolute() and
             not any(ord(c) < 32 or ord(c) == 127 for c in name) and
             all(part not in {"", ".", ".."} and not part.endswith((" ", "."))
                 for part in name.split("/")), "invalid relative path: " + repr(name))
        return name

    def path(self, value):
        if isinstance(value, Path):
            path = value
        else:
            need(isinstance(value, str), "path string required")
            path = Path(value)
            if not path.is_absolute():
                path = self.root / self.relative(value)
        need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink refused")
        resolved = path.resolve()
        need(resolved.is_relative_to(self.root), "path outside repository: " + str(value))
        return resolved

    def add_pin(self, value):
        numeric = bare_pin(value)
        need(numeric["bytes"] < MAX_FILE, "selected file exceeds GitHub limit")
        path = self.path(value.get("path"))
        rel = path.relative_to(self.root).as_posix()
        need(rel not in {SELECTION, PATHSPEC}, "selection/pathspec cannot pin themselves")
        need(not path.is_relative_to(self.root / BASE / "public_training_restore_validation_v1"),
             "materialized restore excluded")
        forbidden = set(path.suffixes) & FORBIDDEN
        need(not forbidden or (forbidden == {".bin"} and path.suffixes == [".bin", ".gz"] and
                              self.allowed_pools.get(rel) == numeric), "forbidden public file: " + rel)
        need(path.is_file(), "missing selected file: " + rel)
        need(path.stat().st_size == numeric["bytes"], "selected file size differs: " + rel)
        row = dict(path=rel, **numeric)
        need(rel not in self.rows or self.rows[rel] == row, "conflicting pin: " + rel)
        self.rows[rel] = row
        return dict(path=str(path), **numeric)

    def small(self, name):
        path = self.path(name)
        need(path.is_file(), "missing required metadata: " + str(name))
        need(path.stat().st_size <= MAX_METADATA, "unpinned metadata exceeds 16 MiB: " + str(name))
        data = path.read_bytes()
        need(len(data) <= MAX_METADATA, "metadata grew past read limit")
        value = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.add_pin(value)
        return value, data

    def json_file(self, name):
        _, data = self.small(name)
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_object,
                           parse_constant=lambda token: (_ for _ in ()).throw(
                               ValueError("nonfinite JSON value: " + token)))
        need(isinstance(value, dict), "JSON object required: " + str(name))
        return value

    def add_fields(self, value, names):
        for name in names:
            if value.get(name) is not None:
                self.add_pin(value[name])

    def add_list(self, values):
        need(isinstance(values, list), "pin inventory list required")
        for value in values:
            self.add_pin(value)

    def source_pins(self, values):
        need(isinstance(values, list), "source pin list required")
        for value in values:
            # The only intentionally external branch is a source/runtime list;
            # numeric outputs never use this exception.
            bare_pin(value)
            path = Path(value["path"])
            need(path.is_absolute(), "absolute source pin required")
            if not path.resolve().is_relative_to(self.root):
                if value not in self.external_sources:
                    self.external_sources.append(value)
                continue
            self.add_pin(value)

    def quality_source_records(self, receipt, failed_v1=False):
        need(isinstance(receipt.get("source_pins_before"), list) and receipt["source_pins_before"],
             "complete before-source inventory required")
        after = receipt.get("source_pins_after")
        if after is None:
            need(failed_v1 and receipt.get("passed") is False,
                 "only failed V1 quality history may omit after-source pins")
        else:
            need(isinstance(after, list) and after, "complete after-source inventory required")
            if receipt.get("passed") is True:
                need(after == receipt["source_pins_before"], "successful before/after source pins differ")
        self.source_pins(receipt["source_pins_before"])
        if after is not None:
            self.source_pins(after)

    def unavailable_history(self, value, reason):
        bare_pin(value)
        record = dict(expected_pin=value, reason=reason)
        if record not in self.unavailable_historical_sources:
            self.unavailable_historical_sources.append(record)

    def fixed_files(self, directory, names):
        for name in names:
            self.small(self.path(directory) / self.relative(name))

    def guards(self, directory):
        self.fixed_files(directory, GUARDS)

    def snapshot(self, directory, originals, override=None):
        need(isinstance(originals, list), "finite original source pins required")
        names = [Path(value["path"]).name for value in originals]
        need(len(set(names)) == len(names), "ambiguous source basenames")
        changed = Path(override["path"]).name if override else None
        need(not override or changed in names, "mutant override not in original source roles")
        for name, original in zip(names, originals):
            original = override if name == changed else original
            path = self.path(directory) / name
            self.add_pin(dict(path=str(path), **bare_pin(original)))

    def stage(self, name):
        value = self.json_file(name)
        need(value.get("completed") is True and value.get("post_verification_passed") is True and
             value.get("native_exit_code") == 0, "incomplete stage: " + str(name))
        self.add_list(value["files"])
        self.add_list(value["execution_files"])
        self.add_fields(value, ("build_manifest", "quality_inputs", "selftest", "previous_stage", "reservation"))
        if value.get("quality_audit"):
            self.add_fields(value["quality_audit"], ("acceptance", "independent_audit", "development_stage"))
        return value

    def selection(self, export_pin):
        rows = [self.rows[key] for key in sorted(self.rows)]
        return dict(schema="v31_actual_evidence_public_selection_v1",
                    scope="complete V31 source and actual experiment evidence; no production promotion",
                    files=rows, file_count=len(rows), selected_bytes=sum(v["bytes"] for v in rows),
                    accepted_training_export=export_pin, quality_tested=True, speed_tested=True,
                    numeric_quality_audit_passed=True, primary_accuracy_hypothesis_passed=False,
                    independent_timing_numeric_audit_passed=True, production_promotion=False,
                    production_version="V11", payload_hash_verification="required separately by frozen successor",
                    excluded_external_source_runtime_pins=self.external_sources,
                    unavailable_historical_sources=self.unavailable_historical_sources)

    def pathspec(self):
        return b"\0".join(name.encode("utf-8") for name in sorted(set(self.rows) | {SELECTION})) + b"\0"


def experiment(name):
    return BASE + "/" + name


def collect_export(c):
    name = experiment("public_training_export_v1/EXPORT_MANIFEST.json")
    manifest = c.json_file(name)
    fullpin = dict(path=str(c.path(name)), **bare_pin(c.rows[name]))
    need(bare_pin(fullpin) == EXPORT_PIN and manifest.get("passed") is True and
         manifest.get("schema") == "rgb_stratified_lossless_training_export_v1" and
         manifest.get("file_count") == len(manifest["files"]) == 46, "accepted 46-member export required")
    stored_names, original_names = set(), set()
    total = 0
    for row in manifest["files"]:
        stored, original = c.relative(row["stored_path"]), c.relative(row["original_path"])
        need(stored not in stored_names and original not in original_names, "duplicate export mapping")
        stored_names.add(stored)
        original_names.add(original)
        saved, before = bare_pin(row["stored"]), bare_pin(row["original"])
        need(saved["bytes"] <= MAX_EXPORT and row["encoding"] in {"identity", "gzip"}, "invalid export member")
        if row["encoding"] == "identity":
            need(saved == before, "identity export differs")
        target = c.path(experiment("public_training_export_v1")) / stored
        rel = target.relative_to(c.root).as_posix()
        if ".bin" in target.suffixes:
            need(re.fullmatch(r"pools_[0-9]{6}\.bin\.gz", original) and stored == original and
                 row["encoding"] == "identity" and before == saved, "unauthorized binary export")
            c.allowed_pools[rel] = saved
        c.add_pin(dict(path=str(target), **saved))
        total += saved["bytes"]
    need(total == manifest["stored_bytes"], "export stored-byte total differs")
    c.add_fields(manifest, ("training_provenance", "training_acceptance", "source"))
    acceptance = c.json_file(experiment("PUBLIC_EXPORT_ACCEPTANCE.json"))
    need(acceptance.get("passed") is True and acceptance.get("independently_restored") is True and
         acceptance.get("export_manifest") == fullpin, "independent accepted export restore required")
    c.add_fields(acceptance, ("export_manifest", "training_provenance", "restore_check", "invocation", "source"))
    c.add_list(acceptance["execution_files"])
    need(len(acceptance["execution_files"]) == 6, "complete restore guard required")
    restored = c.json_file(acceptance["restore_check"]["path"])
    need(restored.get("passed") is True and restored.get("files") == 46, "complete restore check required")
    c.source_pins(restored["sources"])
    # Intentionally never follows restored files[] or invocation.restore_root.
    return fullpin


def collect_public_sources(c):
    validation = c.json_file(experiment("release_v31/PUBLIC_SELECTION_VALIDATION.json"))
    need(validation.get("passed") is True and validation.get("scope") == "synthetic_source_only", "public source validation required")
    c.add_list(validation["files"])
    release = experiment("release_v31/")
    for run in ("successor_red_manifest_pool_v1", "successor_green_manifest_pool_v3"):
        receipt = c.json_file(release + run + "/receipt.json")
        c.add_list(receipt["source_snapshot_pins"])
        c.add_list(receipt["outputs"])
    for run in ("successor_mutations_v1", "successor_mutations_v2"):
        receipt = c.json_file(release + run + "/receipt.json")
        for mutant in receipt["mutants"]:
            path = c.path(mutant["mutant_pin"]["path"])
            c.snapshot(path.parent, receipt["source_pins"], mutant["mutant_pin"])
            c.add_list(mutant["outputs"])
            c.small(path.parent.parent / "receipt.json")


def collect_quality_sources(c):
    handoff = c.json_file(experiment("independent_quality_v2/SOURCE_HANDOFF_V2.json"))
    c.add_list(handoff["source_pins"])
    for key in ("regression_red", "regression_green", "full_source_green"):
        c.add_pin(handoff[key])
        receipt = c.json_file(handoff[key]["path"])
        directory = c.path(handoff[key]["path"]).parent
        if key.startswith("regression_"):
            c.snapshot(directory / "source", receipt["source_pins"])
            c.fixed_files(directory, ("stdout.txt", "stderr.txt"))
        else:
            need(receipt.get("passed") is True, "full quality source validation failed")
            c.add_list(receipt["source_snapshot"])
            c.add_fields(receipt["green"], ("stdout", "stderr"))
            originals = list(receipt["sources_before"].values())
            for mutant in receipt["mutant_red"]:
                c.snapshot(mutant["cwd"], originals, mutant["mutated_source"])
                c.add_fields(mutant, ("stdout", "stderr"))


def collect_training(c):
    acceptance = c.json_file(experiment("TRAINING_ACCEPTANCE.json"))
    need(acceptance.get("real_training_accepted") is True and acceptance.get("numeric_audit_passed") is True,
         "accepted complete training required")
    c.add_fields(acceptance, ("independent_runner", "independent_audit", "training_provenance", "source"))
    provenance = c.json_file(acceptance["training_provenance"]["path"])
    c.add_fields(provenance, ("build_manifest", "input_freeze", "reservation", "guard"))
    c.source_pins(provenance["script_pins"])
    c.guards(experiment("run_training_v1_execution"))
    # provenance.files/image_pins intentionally not followed: export owns the
    # complete training transport, and source images are not public evidence.
    for run in ("full_training_audit_v1", "full_training_audit_v2"):
        directory = experiment("independent/evidence/" + run)
        receipt = c.json_file(directory + "/RUNNER_RECEIPT.json")
        c.add_fields(receipt, ("reservation", "runner_provenance", "input_freeze", "output_pin_map", "audit_receipt"))
        if run.endswith("_v1"):
            for value in receipt["source_pins"]:
                name = Path(value["path"]).name
                if name == "run_full_audit.py":
                    c.unavailable_history(value,
                        "Failed V1 runner source snapshot not located; current V2 source differs. Failure record is not claimed fully replayable.")
                elif name == "training_audit.py":
                    old = experiment("independent/evidence/20261022T143555.182773Z_training_core/source_snapshot/training_audit.py")
                    c.add_pin(dict(path=str(c.path(old)), **bare_pin(value)))
                else:
                    c.source_pins([value])
        else:
            c.source_pins(receipt["source_pins"])
        c.guards(directory + "/execution")
    c.small(experiment("AUDIT_ENTRYPOINT_FAILURES.md"))
    c.fixed_files(experiment("independent/evidence"),
                  ("training_audit_reservation_v1.json", "training_audit_reservation_v2.json"))
    # Both the failed-run source and corrected successful-run source were
    # tested in named frozen snapshots; none of these historical pins is
    # imposed on today's same-named top-level files.
    for stamp in ("20261022T143555.182773Z_training_core", "20261022T162832.128350Z_training_core"):
        receipt = c.json_file(experiment("independent/evidence/" + stamp + "/RECEIPT.json"))
        need(receipt.get("all_checks_passed") is True, "training source selftest required")
        c.add_list(receipt["source_snapshot"])
        c.add_fields(receipt["green"], ("stdout", "stderr"))
        originals = list(receipt["sources_before"].values())
        for mutant in receipt["mutant_red"]:
            c.snapshot(mutant["cwd"], originals, mutant["mutated_source"])
            c.add_fields(mutant, ("stdout", "stderr"))


def collect_geometry(c):
    for name in ("GEOMETRY_INPUT_FREEZE.json", "ACCEPTED_TRAINING_GEOMETRY_REPORT.json",
                 "quality/TRAINING_GEOMETRY_ACCEPTANCE.json"):
        c.small(experiment(name))
    joined = c.json_file(experiment("ACCEPTED_TRAINING_GEOMETRY_REPORT.json"))
    c.add_fields(joined, ("training_execution_acceptance", "training_numeric_audit", "guarded_geometry_runner",
                          "independent_geometry_runner", "independent_geometry_audit", "source"))
    scan = c.json_file(experiment("geometry/real_scan_20261023_v1_RUNNER_RECEIPT.json"))
    need(scan.get("passed") is True, "accepted geometry scan required")
    c.add_fields(scan, ("launch", "guard", "scanner_receipt", "geometry_freeze"))
    c.source_pins(scan["source_pins"])
    freeze = c.json_file(scan["geometry_freeze"]["path"])
    c.add_fields(freeze, ("training_freeze", "source_numeric_audit", "geometry_report", "common_padding_plan", "reservation"))
    c.source_pins(freeze["source_pins"])
    scanner = c.json_file(scan["scanner_receipt"]["path"])
    c.add_fields(scanner, ("reservation", "reservation_consumed", "input_freeze", "source_numeric_audit",
                           "geometry_freeze", "geometry_report", "common_padding_plan"))
    c.guards(experiment("geometry/real_scan_20261023_v1_EXECUTION"))
    independent = c.json_file(experiment("geometry/real_independent_20261023_v1/RUNNER_RECEIPT.json"))
    need(independent.get("passed") is True, "accepted independent geometry required")
    c.add_fields(independent, ("reservation", "consumed_marker", "audit_output", "source_numeric_audit"))
    c.guards(experiment("geometry/real_independent_20261023_v1_EXECUTION"))


def collect_builds(c):
    for directory, log in (("build_training_v1", "commands.json"), ("quality/build_native_v1", "attempts.json")):
        prefix = experiment(directory)
        manifest = c.json_file(prefix + "/build_manifest.json")
        need(manifest.get("passed") is True, "successful build manifest required")
        c.source_pins(manifest["project_sources"])
        c.small(prefix + "/" + log)
        # Fixed compiler phases, not a directory scan; .o/.exe/runtime excluded.
        c.fixed_files(prefix, ("core_before.d", "adapter_before.d", "core.d", "adapter.d"))
        for label in ("core_dependency_before", "core_compile", "adapter_dependency_before", "adapter_compile", "link"):
            c.fixed_files(prefix, (label + ".stdout", label + ".stderr"))
        for unit in manifest["dependency_units"]:
            c.add_fields(unit, ("dependency_file",))


def collect_quality(c):
    for stage in ("selftest", "old_gate", "pilot", "development", "timing"):
        c.stage(experiment("quality/run_" + stage + "_v1/QUALITY_STAGE_FREEZE.json"))
    acceptance = c.json_file(experiment("quality/QUALITY_AUDIT_ACCEPTANCE.json"))
    need(acceptance.get("accepted_independent_audit") is True and acceptance.get("numeric_audit_passed") is True and
         acceptance.get("primary_accuracy_hypothesis_passed") is False and acceptance.get("production_promotion") is False,
         "root accepted failed accuracy hypothesis required")
    c.add_fields(acceptance, ("development_stage", "independent_audit", "independent_runner", "independent_guard", "source"))
    for folder, run, passed in (("independent_quality", "real_development_audit_v1", False),
                                ("independent_quality_v2", "real_development_audit_v2", True)):
        directory = experiment(folder + "/" + run)
        receipt = c.json_file(directory + "/RUNNER_RECEIPT.json")
        need(receipt.get("passed") is passed, "actual quality history status differs")
        c.add_fields(receipt, ("development_stage", "reservation", "consumed", "independent_audit"))
        c.add_list(receipt["evidence_files"])
        c.quality_source_records(receipt, failed_v1=not passed)
        c.small(directory + "/execution_provenance.json")
        c.guards(directory + "/execution")
        consumed = c.path(receipt["consumed"]["path"])
        need(consumed.name.endswith(".consumed.json"), "quality consumed marker naming differs")
        c.small(consumed.with_name(consumed.name[:-len(".consumed.json")] + ".json"))


def collect_timing(c):
    inputs = c.json_file(experiment("independent_timing/TIMING_INPUTS_V1.json"))
    need(inputs.get("schema") == "rgb_stratified_independent_timing_inputs_v1", "timing input declaration required")
    c.add_fields(inputs, ("timing_stage", "development_stage", "quality_inputs", "build_manifest", "selftest",
                          "development_audit", "quality_acceptance"))
    receipt = c.json_file(experiment("independent_timing/real_timing_audit_v1_RUNNER.json"))
    need(receipt.get("passed") is True and receipt.get("numeric_audit_passed") is True,
         "complete independent timing acceptance required")
    c.add_fields(receipt, ("input_pin", "timing_stage", "reservation", "consumed", "result"))
    c.source_pins(receipt["source_pins"])
    c.guards(experiment("independent_timing/real_timing_audit_v1_execution"))
    c.small(experiment("independent_timing/audit_reservations/timing.json"))


def collect_own_source_tests(c):
    for run in ("collector_source_tests_v1", "collector_source_tests_v2"):
        directory = experiment("release_v31/" + run)
        receipt = c.json_file(directory + "/receipt.json")
        need(receipt.get("passed") is True, "collector source tests have not passed")
        if run.endswith("_v1"):
            c.snapshot(directory + "/source", receipt["source_pins"])
        else:
            c.source_pins(receipt["source_pins"])
        c.fixed_files(directory, ("stdout.txt", "stderr.txt"))
        if "outputs" in receipt:
            c.add_list(receipt["outputs"])
    c.fixed_files(experiment("release_v31/collection_attempt_v1"),
                  ("collect_actual_selection.py", "receipt.json", "stdout.txt", "stderr.txt"))


def collect_root_join_reviews(c):
    root = experiment("root_source_tests/")
    for run in ("quality_join_review_v1", "quality_join_review_green_v1", "quality_join_review_green_v2"):
        directory = root + run
        receipt = c.json_file(directory + "/receipt.json")
        c.small(directory + "/cases.json")
        for key in ("source_pins_before", "source_pins_after"):
            for value in receipt[key]:
                if Path(value["path"]).name == "complete_quality_evidence.py" and value["bytes"] == 9196:
                    old = root + "quality_join_review_v1/complete_quality_evidence_before.py"
                    c.add_pin(dict(path=str(c.path(old)), **bare_pin(value)))
                elif Path(value["path"]).name == "complete_quality_evidence.py" and value["bytes"] == 10113:
                    c.unavailable_history(value,
                        "Intermediate green_v1 pure helper snapshot not located; final accepted 10420-byte helper and final review are available.")
                else:
                    c.source_pins([value])
        if run == "quality_join_review_v1":
            c.fixed_files(directory, ("complete_quality_evidence_before.py", "review_validate_result.py", "run_fresh.py", "REVIEW.md"))
        else:
            entry = c.json_file(directory + "/ENTRY_RECEIPT.json")
            c.add_list(entry["driver_and_entry"])
            c.add_fields(entry, ("review",))
    static = c.json_file(root + "quality_join_review_green_v1/STATIC_REVIEW_RECEIPT.json")
    for i, value in enumerate(static["sources_before"]):
        name = f"{i:02d}_" + Path(value["path"]).name
        copy = root + "quality_join_review_green_v1/reviewed_source/" + name
        c.add_pin(dict(path=str(c.path(copy)), **bare_pin(value)))
    c.source_pins(static["sources_before"])
    c.source_pins(static["sources_after"])
    c.add_fields(static, ("pure_green_receipt", "red_source_snapshot"))
    c.unavailable_history(static["reviewed_document"],
        "Earlier evolving review-document bytes not preserved; FINAL_REVIEW_RECEIPT binds the final report copy explicitly.")
    final = c.json_file(root + "quality_join_review_green_v2/FINAL_REVIEW_RECEIPT.json")
    need(final.get("passed") is True, "final root quality join source review required")
    c.add_fields(final, ("tiny_review", "fresh_entry", "final_report", "target", "prior_static_review"))


def collect(root=ROOT):
    c = Collector(root)
    export_pin = collect_export(c)
    checkpoint = c.json_file(experiment("SOURCE_CHECKPOINT_SELECTION.json"))
    need(checkpoint.get("schema") == "v31_source_checkpoint_selection_v1" and
         checkpoint.get("file_count") == len(checkpoint["files"]) and
         checkpoint.get("selected_bytes") == sum(row["bytes"] for row in checkpoint["files"]),
         "source checkpoint inventory differs")
    c.add_list(checkpoint["files"])
    collect_public_sources(c)
    collect_quality_sources(c)
    collect_training(c)
    collect_geometry(c)
    collect_builds(c)
    collect_quality(c)
    collect_timing(c)
    collect_own_source_tests(c)
    collect_root_join_reviews(c)
    c.small("artifacts/rgb_dilated_mask_experiment/PUBLISH_SELECTION_V30.json")
    for name in REPO_TEXTS:
        c.small(name)
    for name in ROOT_TEXTS:
        c.small(experiment(name))
    return c, c.selection(export_pin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    selection_path, pathspec_path = ROOT / SELECTION, ROOT / PATHSPEC
    need(not selection_path.exists() and not pathspec_path.exists(), "fresh selection and pathspec required")
    c, selection = collect()
    data = (json.dumps(selection, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    need(len(data) < MAX_FILE, "selection exceeds GitHub per-file limit")
    with selection_path.open("xb") as stream:
        stream.write(data)
    with pathspec_path.open("xb") as stream:
        stream.write(c.pathspec())
    print(json.dumps(dict(created=True, selection=str(selection_path), pathspec=str(pathspec_path),
                          file_count=selection["file_count"], selected_bytes=selection["selected_bytes"],
                          payload_bytes_read=c.payload_bytes_read, git_operations=0,
                          payload_verifier_required=True, staged_verifier_required=True)))


if __name__ == "__main__":
    main()
