"""Local GCC -MD dependency artifacts; not an attestation of every OS resource."""
from pathlib import Path

from capture_manifest import check_file, relative_path, require


def parse_depfile(data, target, working_directory):
    require(isinstance(data, bytes) and b'\0' not in data, 'Invalid dependency bytes')
    try:
        text = data.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Dependency file must be UTF-8') from error
    require(target in ('core.o', 'adapter.o'), 'Fixed dependency target required')
    text = text.replace('\\\r\n', '').replace('\\\n', '').strip()
    require(text.startswith(target+':'), 'Dependency target differs')
    text = text[len(target)+1:]
    require('\r' not in text and '\n' not in text, 'Multiple dependency rules rejected')
    tokens, token = [], []
    position = 0
    while position < len(text):
        char = text[position]
        if char in ' \t':
            if token:
                tokens.append(''.join(token))
                token = []
        elif char == '\\':
            require(position+1 < len(text), 'Truncated dependency escape')
            following = text[position+1]
            if following in ' \t#:$\\':
                token.append(following)
                position += 1
            else:
                # Native MinGW paths can retain Windows separators; only
                # Make-special following characters consume an escape.
                token.append(char)
        elif char == '$':
            require(position+1 < len(text) and text[position+1] == '$',
                    'Unescaped Make dependency dollar')
            token.append('$')
            position += 1
        else:
            require(char != '#', 'Unescaped Make dependency comment')
            token.append(char)
        position += 1
    if token:
        tokens.append(''.join(token))
    require(tokens, 'Empty dependency list')
    cwd = Path(working_directory).resolve(strict=True)
    result = [(Path(value) if Path(value).is_absolute() else cwd/value).resolve()
              for value in tokens]
    require(len(result) == len(set(result)), 'Duplicate resolved dependency path')
    return result


def audit_build_dependencies(root, snapshot, toolchain, built, expected_sources):
    root, snapshot = Path(root).resolve(strict=True), Path(snapshot).resolve(strict=True)
    role = built['role']
    require(role in ('capture', 'reference'), 'Unknown dependency build role')
    cwd = Path(built['working_directory']).resolve(strict=True)
    require(Path(built['working_directory']).is_absolute() and cwd.is_relative_to(root)
            and cwd.name == role+'_objects', 'Fixed dependency build directory required')
    require(isinstance(built['compile_exits'], list)
            and len(built['compile_exits']) == 2
            and all(type(value) is int and value == 0 for value in built['compile_exits'])
            and type(built['link_exit']) is int and built['link_exit'] == 0,
            'Both dependency compiles and link must succeed')
    library = toolchain['import_library']
    require(Path(library['path']).is_absolute(), 'Explicit absolute import library required')
    library_path = Path(library['path']).resolve(strict=True)
    require(library_path == Path(toolchain['opencv_root']).resolve(strict=True)/
            'build/lib/libopencv_world4120.dll.a', 'Fixed OpenCV import library required')
    checked = []

    def pin(path, metadata, label):
        check_file(path, metadata, label)
        checked.append((path, metadata, label))

    pin(library_path, library, 'OpenCV import library')
    units = built['dependency_units']
    require(isinstance(units, list) and len(units) == 2,
            'Two independent compiler dependency artifacts required')
    kind = 'captured' if role == 'capture' else 'original'
    expected = [('core', snapshot/kind/'line2Dup.cpp'),
                ('adapter', snapshot/'support/capture_adapter.cpp')]
    for unit, (name, source) in zip(units, expected):
        require(unit['source'] == source.relative_to(root).as_posix()
                and unit['target'] == name+'.o', 'Dependency source/target binding differs')
        paths = {}
        for key, suffix in (('object', '.o'), ('depfile', '.d')):
            item = unit[key]
            path = relative_path(root, item['path'])
            require(path == cwd/(name+suffix), 'Fixed compiler artifact path differs')
            pin(path, item, 'compiler '+key)
            paths[key] = path
        parsed = parse_depfile(paths['depfile'].read_bytes(), unit['target'], cwd)
        # Scope every path before hashing any dependency. This auditor must
        # never hash a heldout/dataset path injected into a declared depfile.
        for path in parsed:
            require(not path.is_relative_to(root) or
                    path.relative_to(root).as_posix() in expected_sources,
                    'Dependency outside approved repository project-source scope')
        require(source in parsed, 'Compiler source omitted from dependency list')
        declared = unit['dependencies']
        require(isinstance(declared, list), 'Dependency metadata list required')
        declared_paths = []
        for item in declared:
            require(isinstance(item['path'], str) and Path(item['path']).is_absolute(),
                    'Dependency pin needs explicit absolute path')
            declared_paths.append(Path(item['path']).resolve())
        require(declared_paths == parsed, 'Complete ordered dependency pin list differs')
        for path, item in zip(parsed, declared):
            pin(path, item, 'actual compiler dependency')
    for path, metadata, label in checked:
        check_file(path, metadata, label+' after dependency read')
    return checked
