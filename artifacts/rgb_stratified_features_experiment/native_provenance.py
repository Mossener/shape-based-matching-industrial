"""Explicit native build/run closure for this isolated experiment.

Tracks declared compiler tools, actual GCC dependency files, explicit link
libraries and recursively resolved non-system PE imports. OS/API-set DLLs are
named but not attested. This is local provenance, not a cryptographic execution
attestation or a guarantee that every OS resource has been enumerated.
"""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess


def require(value, message):
    if not value:
        raise ValueError(message)


def file_pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def check_pin(pin):
    require(file_pin(pin['path']) == pin, 'Native closure SHA/size changed: '+pin['path'])


def parse_dependencies(data, target, cwd):
    # Same Make escaping rules as the separately tested capture dependency
    # parser, scoped locally to the experiment's two actual object targets.
    require(target in ('core.o', 'adapter.o') and b'\0' not in data, 'Invalid dependency target/data')
    text = data.decode('utf-8').replace('\\\r\n', '').replace('\\\n', '').strip()
    require(text.startswith(target+':'), 'Dependency target differs')
    text = text[len(target)+1:]
    require('\r' not in text and '\n' not in text, 'Multiple dependency rules')
    tokens, token, at = [], [], 0
    while at < len(text):
        char = text[at]
        if char in ' \t':
            if token:
                tokens.append(''.join(token));token = []
        elif char == '\\':
            require(at+1 < len(text), 'Truncated dependency escape')
            following = text[at+1]
            if following in ' \t#:$\\':
                token.append(following);at += 1
            else:
                token.append(char)
        elif char == '$':
            require(at+1 < len(text) and text[at+1] == '$', 'Unescaped Make dependency dollar')
            token.append('$');at += 1
        else:
            require(char != '#', 'Unescaped dependency comment');token.append(char)
        at += 1
    if token:
        tokens.append(''.join(token))
    require(tokens, 'Empty dependency rule')
    paths = [(Path(p) if Path(p).is_absolute() else Path(cwd)/p).resolve() for p in tokens]
    # GCC may emit the same header through different include spellings. Keep
    # every ordered occurrence: neither reject real aliases nor silently
    # deduplicate evidence before precompile/actual dependency comparison.
    return paths


def dependency_pins(data, target, cwd, repo, allowed_project):
    paths = parse_dependencies(data, target, cwd)
    repo = Path(repo).resolve()
    allowed = {Path(p).resolve() for p in allowed_project}
    # Check the complete path list before opening any dependency. A malicious
    # or erroneous depfile cannot make the auditor hash a heldout image.
    for path in paths:
        require(not path.is_relative_to(repo) or path in allowed, 'Dependency outside approved project source scope: '+str(path))
    return [file_pin(path) for path in paths]


def imports(output):
    names = []
    for line in output.splitlines():
        match = re.fullmatch(r'\s*DLL Name:\s*(\S+)\s*', line)
        if match:
            name = match.group(1)
            require('/' not in name and '\\' not in name and ':' not in name and name.lower().endswith('.dll'), 'Unsafe PE import name')
            names.append(name)
    require(len(names) == len(set(n.casefold() for n in names)), 'Duplicate PE imports')
    return names


def import_closure(seeds, compiler, opencv, env):
    compiler, opencv = Path(compiler).resolve(), Path(opencv).resolve()
    objdump = compiler.parent/'objdump.exe'
    roots = [Path(seed).resolve() for seed in seeds]
    before = file_pin(objdump)
    pending, visited, files, system, details = list(roots), set(), {}, set(), []
    system_root = Path(env.get('SystemRoot', 'C:/Windows')).resolve()/'System32'
    while pending:
        path = pending.pop(0)
        if path in visited:
            continue
        visited.add(path)
        require(len(visited) <= 256, 'Runtime import closure budget exceeded')
        pin = file_pin(path);files[str(path)] = pin
        command = [str(objdump), '-p', str(path)]
        run = subprocess.run(command, env=env, capture_output=True, check=False)
        require(run.returncode == 0, 'Cannot inspect actual PE imports: '+str(path))
        names = imports(run.stdout.decode('utf-8', errors='strict'))
        details.append(dict(path=str(path), imports=names, command=command,
                            stdout_sha256=hashlib.sha256(run.stdout).hexdigest()))
        for name in names:
            if name.lower().startswith(('api-ms-', 'ext-ms-')):
                system.add(name);continue
            candidate = next((base/name for base in (path.parent, opencv/'build/bin', compiler.parent, system_root) if (base/name).is_file()), None)
            require(candidate is not None, 'Unresolved PE import: '+name+' from '+str(path))
            candidate = candidate.resolve()
            if candidate.is_relative_to(system_root):
                system.add(name)
            else:
                pending.append(candidate)
        check_pin(pin)
    check_pin(before)
    files[str(objdump.resolve())] = before
    return dict(files=list(files.values()), system_import_names=sorted(system), pe_imports=details,
                limitation='Recursively resolved non-system static PE imports; OS/API-set DLLs named but not hashed; no claim about dynamic plugins or every OS resource')


def compiler_tools(compiler, env):
    compiler = Path(compiler).resolve(strict=True)
    files = [compiler]
    queries = []
    for name in ('cc1plus', 'as', 'collect2', 'ld'):
        command = [str(compiler), '-print-prog-name='+name]
        run = subprocess.run(command, env=env, capture_output=True, check=True)
        value = run.stdout.decode('utf-8').strip()
        path = Path(value)
        if not path.is_absolute():
            found = shutil.which(value, path=env['PATH'])
            require(found is not None, 'Compiler helper does not resolve: '+value);path = Path(found)
        files.append(path.resolve(strict=True));queries.append(dict(command=command, output=value))
    return files, queries
