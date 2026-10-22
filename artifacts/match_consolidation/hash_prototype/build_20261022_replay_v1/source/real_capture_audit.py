"""Required fixed-source/build closure on top of generic declared-pin audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from capture_manifest import (CORE_REVISION, audit_capture, check_file,
                              json_bytes, relative_path, require, sha256)
from capture_source import CORE_FILES, instrument_core
from dependency_closure import audit_build_dependencies

SUPPORT = ('record.hpp', 'trace_io.hpp', 'capture_hook.hpp', 'capture_adapter.cpp', 'led_demo.cpp')
PROVENANCE = ('capture_source.py', 'capture_manifest.py', 'real_capture_audit.py',
              'dependency_closure.py', 'real_capture_build.py', 'real_capture_build.ps1',
              'run_capture.py', 'CAPTURE_PROTOCOL.json')


def approved_command(snapshot, compiler, opencv, role, executable):
    core = snapshot/('captured' if role == 'capture' else 'original')
    command = [str(compiler), '-std=c++17', '-O3', '-mssse3', '-msse4.1', '-fopenmp',
               '-Wall', '-Wextra', '-Wno-sign-compare',
               '-DSBM_CAPTURE='+('1' if role == 'capture' else '0'),
               '-I'+str(core), '-I'+str(core/'MIPP'), '-I'+str(snapshot/'support'),
               '-I'+str(opencv/'build')]
    command += ['-I'+str(opencv/'modules'/module/'include')
                for module in ('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')]
    work = executable.parent/(role+'_objects')
    commands = [command+['-c', '-MD', '-MF', str(work/(name+'.d')), '-MT', name+'.o',
                        str(source), '-o', str(work/(name+'.o'))]
                for name, source in (('core', core/'line2Dup.cpp'),
                                      ('adapter', snapshot/'support/capture_adapter.cpp'))]
    commands.append([str(compiler), str(work/'core.o'), str(work/'adapter.o'), '-fopenmp',
                     str(opencv/'build/lib/libopencv_world4120.dll.a'), '-o', str(executable)])
    return commands


def audit_real_capture(manifest_path, protocol_path, repo_root,
                       load_git=None, support_root=None):
    try:
        generic = audit_capture(manifest_path, protocol_path, repo_root)
        root = Path(repo_root).resolve(strict=True)
        support = Path(support_root or Path(__file__).resolve().parent).resolve(strict=True)
        require(support.is_relative_to(root), 'Author source root must stay in repository')
        manifest_path, protocol_path = Path(manifest_path).resolve(), Path(protocol_path).resolve()
        manifest_hash, protocol_hash = sha256(manifest_path), sha256(protocol_path)
        protocol = json_bytes(protocol_path.read_bytes())
        closure = protocol['real_build_closure']
        pinned = []

        def pin(path, metadata, label):
            check_file(path, metadata, label)
            pinned.append((path, metadata, label))

        source_pin = closure['source_manifest']
        source_manifest_path = relative_path(root, source_pin['path'])
        require(source_manifest_path.name == 'source_manifest.json', 'Fixed source manifest name required')
        pin(source_manifest_path, source_pin, 'source manifest')
        snapshot = source_manifest_path.parent
        source_manifest = json_bytes(source_manifest_path.read_bytes())
        require(source_manifest['core_revision'] == CORE_REVISION
                and source_manifest['mipp_file_count'] == 16
                and source_manifest['helper_unchanged'] is True,
                'Fixed Git source manifest identity differs')
        if load_git is None:
            def load_git(*arguments):
                return subprocess.check_output(['git', *arguments], cwd=root)
        require(load_git('rev-parse', '--verify', CORE_REVISION).decode('ascii').strip()
                == CORE_REVISION, 'Exact V11 Git revision required')
        entries = {}
        for item in load_git('ls-tree', '-r', '-z', CORE_REVISION).split(b'\0'):
            if not item:
                continue
            properties, encoded_name = item.split(b'\t', 1)
            name = encoded_name.decode('utf-8')
            if name not in CORE_FILES and not name.startswith('MIPP/'):
                continue
            fields = properties.decode('ascii').split(' ')
            require(len(fields) == 3 and fields[0] in ('100644', '100755')
                    and fields[1] == 'blob' and re.fullmatch('[0-9a-f]{40}', fields[2])
                    and name not in entries, 'Invalid fixed Git source inventory')
            relative_path(root, name)
            entries[name] = fields[2]
        require(set(name for name in entries if not name.startswith('MIPP/')) == set(CORE_FILES)
                and sum(name.startswith('MIPP/') for name in entries) == 16
                and set(source_manifest['files']) == set(entries),
                'Incomplete fixed 23-file Git source closure')
        expected_sources = {'capture': set(), 'reference': set()}
        source_union = {source_manifest_path.relative_to(root).as_posix()}
        for name, blob in entries.items():
            data = load_git('show', CORE_REVISION+':'+name)
            require(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == blob,
                    'Fixed Git source payload differs')
            generated = instrument_core(data) if name == 'line2Dup.cpp' else data
            expected_metadata = dict(git_blob=blob, original_bytes=len(data),
                                     captured_bytes=len(generated),
                                     original_sha256=hashlib.sha256(data).hexdigest(),
                                     captured_sha256=hashlib.sha256(generated).hexdigest())
            require(source_manifest['files'][name] == expected_metadata,
                    'Git source manifest hash/length/seam differs: '+name)
            for role, kind, value in (('capture', 'captured', generated),
                                      ('reference', 'original', data)):
                path = relative_path(root, (snapshot/kind/name).relative_to(root).as_posix())
                metadata = dict(sha256=hashlib.sha256(value).hexdigest(), size_bytes=len(value))
                pin(path, metadata, kind+' Git source '+name)
                relative = path.relative_to(root).as_posix()
                expected_sources[role].add(relative)
                source_union.add(relative)
        for name in SUPPORT+PROVENANCE:
            author = support/name
            require(author.is_file(), 'Required author support source missing: '+name)
            data = author.read_bytes()
            metadata = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
            pin(author, metadata, 'author source '+name)
            source_union.add(author.relative_to(root).as_posix())
            if name in PROVENANCE:
                continue
            copied = (snapshot/'captured/capture_hook.hpp' if name == 'capture_hook.hpp'
                      else snapshot/'support'/name)
            pin(copied, metadata, 'copied support source '+name)
            relative = copied.relative_to(root).as_posix()
            source_union.add(relative)
            expected_sources['capture'].add(relative)
            if name != 'capture_hook.hpp':
                expected_sources['reference'].add(relative)
        led_origin = relative_path(root, 'artifacts/led_match/led_demo.cpp')
        require(led_origin.read_bytes() == (support/'led_demo.cpp').read_bytes(),
                'Copied LED fixture source differs from its origin')
        pin(led_origin, dict(sha256=sha256(led_origin), size_bytes=led_origin.stat().st_size),
            'LED fixture source origin')
        source_union.add(led_origin.relative_to(root).as_posix())
        protocol_source_pins = [p for p in protocol['pins'] if p['role'] == 'source']
        require({p['path'] for p in protocol_source_pins} == source_union
                and len(protocol_source_pins) == len(source_union),
                'Protocol source pin closure omits/adds a required dependency')
        toolchain = closure['toolchain']

        def external(item, label):
            require(isinstance(item['path'], str) and Path(item['path']).is_absolute()
                    and '\0' not in item['path'], label+' explicit absolute path required')
            path = Path(item['path']).resolve(strict=True)
            pin(path, item, label)
            return path

        compiler = external(toolchain['compiler'], 'compiler')
        require(compiler.name == 'g++.exe', 'Fixed GCC compiler name required')
        opencv = Path(toolchain['opencv_root']).resolve(strict=True)
        require(Path(toolchain['opencv_root']).is_absolute(), 'Explicit OpenCV root required')
        expected_runtimes = [opencv/'build/bin/libopencv_world4120.dll']+[
            compiler.parent/name for name in ('libgomp-1.dll', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll')]
        runtime_paths = [external(item, 'runtime') for item in toolchain['runtimes']]
        require(runtime_paths == expected_runtimes, 'Complete fixed runtime closure required')
        executables = []
        for role in ('capture', 'reference'):
            matching = [p for p in protocol['pins'] if p['role'] == role+'_build']
            require(len(matching) == 1, 'One bound '+role+' build required')
            build_pin = matching[0]
            build_path = relative_path(root, build_pin['path'])
            pin(build_path, build_pin, role+' build manifest')
            built = json_bytes(build_path.read_bytes())
            require(type(built['schema_version']) is int and built['schema_version'] == 1
                    and built['passed'] is True and built['compile_exit'] == 0
                    and type(built['compile_exit']) is int and built['sources_unchanged'] is True
                    and built['role'] == role and built['core_revision'] == CORE_REVISION,
                    'Failed or mismatched '+role+' build')
            require(built['source_manifest_sha256'] == source_pin['sha256'],
                    role+' build is not bound to fixed source manifest')
            require(built['compiler'] == toolchain['compiler'] and
                    built['runtimes'] == toolchain['runtimes'], role+' build toolchain closure differs')
            files = built['source_files']
            require(isinstance(files, list) and len(files) == len(expected_sources[role])
                    and {item['path'] for item in files} == expected_sources[role],
                    role+' build source dependency closure differs')
            for item in files:
                path = relative_path(root, item['path'])
                pin(path, item, role+' compiled source')
            executable = relative_path(root, built['executable']['path'])
            pin(executable, built['executable'], role+' executable')
            require(executable.suffix == '.exe' and executable not in executables,
                    'Separate native capture/reference executables required')
            executables.append(executable)
            require(Path(built['working_directory']).resolve(strict=True) ==
                    executable.parent/(role+'_objects'), 'Build working directory differs')
            pinned.extend(audit_build_dependencies(root, snapshot, toolchain, built,
                                                   expected_sources[role]))
            require(built['command'] == approved_command(snapshot, compiler, opencv, role, executable),
                    role+' approved compiler/source/adapter/flag/executable recipe differs')
        for path, metadata, label in pinned:
            check_file(path, metadata, label+' after audit')
        require(sha256(manifest_path) == manifest_hash and sha256(protocol_path) == protocol_hash,
                'Capture manifest/protocol changed during closure audit')
        generic.update(real_build_closure_verified=True, git_source_files=len(entries),
                       builds_verified=2, closure_file_checks=len(pinned),
                       limitation='Synthetic-tested fixed-source/build and saved-output closure; '
                                  'not an image accuracy or performance result')
        return generic
    except (OSError, KeyError, TypeError, AttributeError, UnicodeError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise ValueError('Invalid real capture closure: '+str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_real_capture(args.manifest, args.protocol, args.repo_root)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
