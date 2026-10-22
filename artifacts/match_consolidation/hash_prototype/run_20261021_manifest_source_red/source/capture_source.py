"""Create a new exact-V11 private source snapshot with one capture call seam."""
CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
CORE_FILES = ('line2Dup.cpp', 'line2Dup.h', 'line2Dup_local.hpp',
              'line2Dup_search.hpp', 'line2Dup_response.hpp',
              'line2Dup_spread.hpp', 'line2Dup_matches.hpp')


def instrument_core(source):
    # API stub for source-generator semantic RED.
    return source


def make_snapshot(repo_root, destination, load_git=None):
    # API stub: the RED fixture requires actual byte-preserving new files.
    return None
