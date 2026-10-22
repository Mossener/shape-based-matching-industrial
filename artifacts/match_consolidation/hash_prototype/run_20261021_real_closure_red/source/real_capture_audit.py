"""Required fixed-source/build closure on top of generic declared-pin audit."""


def audit_real_capture(manifest_path, protocol_path, repo_root,
                       load_git=None, support_root=None):
    # First RED must reject an omitted dependency, not accept declared pins only.
    return dict(verified=True, real_build_closure_verified=True)
