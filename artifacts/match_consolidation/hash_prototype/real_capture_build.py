"""Build private fixed-V11 capture/reference adapters; never invoke a matcher."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

from capture_manifest import check_file, require, sha256
from capture_source import make_snapshot
from dependency_closure import parse_depfile
from real_capture_audit import SUPPORT, PROVENANCE, approved_command

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def metadata(path, relative=False):
    path = Path(path).resolve(strict=True)
    return dict(path=path.relative_to(ROOT).as_posix() if relative else str(path),
                size_bytes=path.stat().st_size, sha256=sha256(path))


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv', type=Path, default=Path('D:/opencv-4.12.0'))
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Parent native CPU slot must be granted explicitly')
    output = args.output.resolve()
    require(output.is_relative_to(ROOT) and not output.exists(), 'Build output must be new in repository')
    output.mkdir(parents=True)
    snapshot = output/'snapshot'
    source_manifest = make_snapshot(ROOT, snapshot)
    (snapshot/'support').mkdir()
    origin = ROOT/'artifacts/led_match/led_demo.cpp'
    require((HERE/'led_demo.cpp').read_bytes() == origin.read_bytes(), 'LED source origin differs')
    for name in SUPPORT:
        destination = snapshot/('captured/capture_hook.hpp' if name == 'capture_hook.hpp'
                                else 'support/'+name)
        with destination.open('xb') as stream:
            stream.write((HERE/name).read_bytes())
    compiler, opencv = args.compiler.resolve(strict=True), args.opencv.resolve(strict=True)
    runtimes = [opencv/'build/bin/libopencv_world4120.dll'] + [compiler.parent/name for name in
                ('libgomp-1.dll', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll')]
    library = opencv/'build/lib/libopencv_world4120.dll.a'
    toolchain = dict(compiler=metadata(compiler), opencv_root=str(opencv),
                     import_library=metadata(library), runtimes=[metadata(p) for p in runtimes])
    author_sources = [HERE/name for name in SUPPORT+PROVENANCE]+[origin, HERE/'real_capture_build.py',
                     HERE/'real_capture_build.ps1']
    all_paths = list(snapshot.rglob('*'))+author_sources+[compiler, library, *runtimes]
    before = {str(p): metadata(p) for p in all_paths if p.is_file()}
    environment = dict(os.environ, PATH=str(opencv/'build/bin')+os.pathsep+str(compiler.parent)+
                       os.pathsep+os.environ.get('PATH', ''), OMP_WAIT_POLICY='PASSIVE',
                       OMP_NUM_THREADS='4', OMP_DYNAMIC='FALSE', OMP_MAX_ACTIVE_LEVELS='1')
    started = datetime.now(timezone.utc).isoformat()
    builds = {}
    # A discovery preprocessing pass gives the dependency bytes a before-build
    # pin. Real -MD compile artifacts must name the identical ordered inputs.
    for role in ('capture', 'reference'):
        work = output/(role+'_objects')
        work.mkdir()
        executable = output/(role+'.exe')
        commands = approved_command(snapshot, compiler, opencv, role, executable)
        build = dict(schema_version=1, passed=False, role=role,
                     core_revision=source_manifest['core_revision'],
                     source_manifest_sha256=sha256(snapshot/'source_manifest.json'),
                     compiler=toolchain['compiler'], runtimes=toolchain['runtimes'],
                     working_directory=str(work), command=commands, dependency_units=[],
                     compile_exits=[], link_exit=None, compile_exit=None, sources_unchanged=False,
                     started_at=datetime.now(timezone.utc).isoformat())
        build_path = output/(role+'_build.json')
        build['source_files'] = [metadata(snapshot/('captured' if role == 'capture' else 'original')/name, True)
                                 for name in source_manifest['files']]
        build['source_files'] += [metadata(snapshot/'support'/name, True) for name in SUPPORT
                                  if name != 'capture_hook.hpp']
        if role == 'capture':
            build['source_files'].append(metadata(snapshot/'captured/capture_hook.hpp', True))

        def invoke(command, prefix):
            process = subprocess.run(command, cwd=work, env=environment, capture_output=True)
            (work/(prefix+'_stdout.txt')).write_bytes(process.stdout)
            (work/(prefix+'_stderr.txt')).write_bytes(process.stderr)
            return process.returncode

        try:
            for name, command in zip(('core', 'adapter'), commands[:2]):
                source = Path(command[-3]).resolve(strict=True)
                scan = work/(name+'_scan.d')
                discovery = command[:command.index('-c')]+['-M', '-MF', str(scan), '-MT', name+'.o', str(source)]
                require(invoke(discovery, name+'_scan') == 0, 'Dependency discovery failed: '+role+'/'+name)
                discovered = parse_depfile(scan.read_bytes(), name+'.o', work)
                expected_sources = {p['path'] for p in build['source_files']}
                for path in discovered:
                    require(not path.is_relative_to(ROOT) or path.relative_to(ROOT).as_posix() in expected_sources,
                            'Actual dependency outside private project source closure')
                pins = [metadata(p) for p in discovered]
                for item in pins:
                    before.setdefault(item['path'], item)
                code = invoke(command, name+'_compile')
                build['compile_exits'].append(code)
                require(code == 0, 'Compile failed: '+role+'/'+name)
                actual_depfile = work/(name+'.d')
                require(parse_depfile(actual_depfile.read_bytes(), name+'.o', work) == discovered,
                        'Actual -MD dependency list differs from discovery')
                for path, item in zip(discovered, pins):
                    check_file(path, item, 'dependency after compile')
                build['dependency_units'].append(dict(
                    source=source.relative_to(ROOT).as_posix(), target=name+'.o',
                    object=metadata(work/(name+'.o'), True), depfile=metadata(actual_depfile, True),
                    discovery_depfile=metadata(scan, True), discovery_command=discovery,
                    dependencies=pins))
            build['link_exit'] = invoke(commands[2], 'link')
            require(build['link_exit'] == 0, 'Link failed: '+role)
            build['executable'] = metadata(executable, True)
            for path, item in before.items():
                check_file(Path(path), item, 'build input after link')
            build.update(passed=True, compile_exit=0, sources_unchanged=True)
        finally:
            build['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_new(build_path, build)
        builds[role] = metadata(build_path, True)
    for path, item in before.items():
        check_file(Path(path), item, 'all builds final input')
    receipt = dict(passed=True, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                   snapshot=metadata(snapshot/'source_manifest.json', True), toolchain=toolchain,
                   builds=builds, source_pins=[dict(metadata(Path(path), True), role='source')
                   for path in before if Path(path).is_relative_to(ROOT) and
                   (Path(path).is_relative_to(snapshot) or Path(path) in author_sources)],
                   matcher_calls=0, image_decodes=0, performance_measurement=False)
    # These build-wrapper provenance pins are separate from the exact source
    # inventory required by the real audit and are retained for receipt review.
    write_new(output/'build_receipt.json', receipt)
    print(json.dumps(dict(passed=True, receipt=str(output/'build_receipt.json'), matcher_calls=0)))


if __name__ == '__main__':
    main()
