"""Verify the actual listed delivery files and their current source correspondence."""
from . import state, delivery_roles


def inspect(project, data, required=True):
    record = data.get('stages', {}).get('delivery', {})
    pointer = record.get('files', {}).get('manifest')
    issues, versions, covered = [], {}, set()
    if not isinstance(pointer, dict) or not pointer.get('path') or not pointer.get('sha256'):
        return {'issues': ['delivery/manifest: real path and sha256 required'] if required else [],
                'versions': {}}
    try:
        if not required and not state.resolve(project, pointer['path']).is_file():
            return {'issues': [], 'versions': {}}
        path = delivery_roles._file(project, pointer, 'delivery/manifest')
        manifest = state.read_json(path)
        if not isinstance(manifest, dict):
            raise ValueError('delivery/manifest: parseable object required')
        versions[pointer['path']] = pointer['sha256']
        sources = manifest.get('source_versions', {})
        if not isinstance(sources, dict):
            raise ValueError('delivery/manifest: source_versions object required')
        for name, sha in sources.items():
            delivery_roles._file(project, {'path': name, 'sha256': sha}, 'delivery/manifest/source')
        source_map = {state.resolve(project, name): sha for name, sha in sources.items()}
        members = manifest.get('artifacts', manifest.get('files'))
        if isinstance(members, dict):
            members = [{**item, '_role': delivery_roles.artifact_role(key, item)}
                       if isinstance(item, dict) else item for key, item in members.items()]
        if not isinstance(members, list) or not members:
            raise ValueError('delivery/manifest: nonempty artifacts or files required')
        for item in members:
            if not isinstance(item, dict):
                raise ValueError('delivery/manifest: each member needs actual path and sha256')
            destination = item.get('delivery_path', item.get('path'))
            actual = delivery_roles._file(project, {'path': destination, 'sha256': item.get('sha256')},
                                          'delivery/manifest/member')
            delivery_roles._delivery_path(state.relative_path(project, actual))
            versions[destination] = item['sha256']
            source = item.get('path') if item.get('delivery_path') else item.get('source_path')
            if source:
                origin = delivery_roles._file(project, {'path': source, 'sha256': item['sha256']},
                                              'delivery/manifest/original')
                covered.add((origin, item['sha256']))
            else:
                matches = {(p, sha) for p, sha in source_map.items() if sha == item['sha256']}
                if not matches:
                    raise ValueError('delivery/manifest: member has no matching source: ' + destination)
                covered.update(matches)
            if item.get('source_versions'):
                delivery_roles._sources(project, item['source_versions'], {}, 'delivery/manifest/member')
            role = item.get('_role', item.get('role'))
            if data.get('current_task', {}).get('mode') == 'selected_modules' and role:
                module = 'interactive' if role == 'interactive' else 'documents'
                delivery_roles._sources(project, item.get('source_versions', sources),
                    delivery_roles.current_inputs(project, data, module), 'delivery/manifest/' + role)
        materials = delivery_roles.check(project, data)
        issues.extend(materials['issues'])
        expected = [item for item in materials['artifacts'].values() if item.get('role')]
        task = data.get('current_task', {})
        modules = {m.removeprefix('math-courseware-') for m in task.get('modules', [])}
        if task.get('mode') == 'full_course' or 'editable' in modules:
            deck = data.get('stages', {}).get('editable', {}).get('files', {}).get('pptx')
            if not deck and 'editable' in modules:
                from . import editable_delivery
                deck = editable_delivery.current(project)
            if deck:
                expected.append(deck)
        expected.extend(item for role, item in record.get('files', {}).items()
                        if role not in ('manifest', 'wps', 'materials-manifest'))
        for item in expected:
            if (state.resolve(project, item['path']), item['sha256']) not in covered:
                issues.append('delivery/manifest: current deliverable missing or different: ' + item['path'])
    except (ValueError, OSError, TypeError, KeyError) as exc:
        issues.append('delivery/manifest: unverified: ' + str(exc))
    return {'issues': list(dict.fromkeys(issues)), 'versions': versions}
