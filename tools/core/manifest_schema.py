"""Common template manifest schema validation."""
REQUIRED_TOP_LEVEL = ('manifest_version', 'schema_version', 'template', 'compatibility', 'files')
def validate(manifest):
    if not isinstance(manifest, dict): raise ValueError('Manifest must be a mapping')
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in manifest]
    if missing: raise ValueError('Manifest missing required fields: ' + ', '.join(missing))
    if not isinstance(manifest['manifest_version'], str) or not manifest['manifest_version']: raise ValueError('manifest_version must be a non-empty string')
    template = manifest['template']
    if not isinstance(template, dict): raise ValueError('template must be a mapping')
    for key in ('id', 'name', 'version', 'release'):
        if not isinstance(template.get(key), str) or not template[key]: raise ValueError('template.' + key + ' is required')
    if template['release'] != 'v' + template['version']: raise ValueError('template.release/version mismatch')
    compatibility = manifest['compatibility']
    if not isinstance(compatibility, dict): raise ValueError('compatibility must be a mapping')
    for key in ('schema_version', 'data_format_version'):
        if not isinstance(compatibility.get(key), str) or not compatibility[key]: raise ValueError('compatibility.' + key + ' is required')
    if not isinstance(manifest['files'], dict) or manifest['files'].get('template_base') != 'TEMPLATE_BASE.md': raise ValueError('files.template_base must be TEMPLATE_BASE.md')
    return manifest
