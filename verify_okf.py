#!/usr/bin/env python3
"""Static OKF v0.2 checks for docs/okf after extraction in project root."""
from pathlib import Path
import re,sys
try:
    import yaml
except ImportError:
    print('PyYAML required for full validation: pip install pyyaml')
    raise SystemExit(2)
root=Path(__file__).parent/'docs'/'okf'
errors=[]
concepts=[]
for p in sorted(root.rglob('*.md')):
    text=p.read_text(encoding='utf-8')
    rel=p.relative_to(root)
    if p.name=='index.md':
        if p==root/'index.md':
            if not text.startswith('---\n'):
                errors.append(f'{rel}: root index missing version frontmatter')
            else:
                parts=text.split('---\n',2)
                try:
                    y=yaml.safe_load(parts[1]) or {}
                    if y.get('okf_version') != '0.2':errors.append(f'{rel}: invalid okf_version')
                except Exception as e:errors.append(f'{rel}: YAML {e}')
        elif text.startswith('---\n'):
            errors.append(f'{rel}: subindex must not contain frontmatter')
    elif p.name=='log.md':
        if not re.search(r'^## \d{4}-\d{2}-\d{2}$',text,re.M):
            errors.append(f'{rel}: log needs ISO date heading')
    else:
        concepts.append(p)
        if not text.startswith('---\n'):
            errors.append(f'{rel}: no frontmatter');continue
        parts=text.split('---\n',2)
        if len(parts)<3:
            errors.append(f'{rel}: malformed frontmatter');continue
        try:y=yaml.safe_load(parts[1])
        except Exception as e:errors.append(f'{rel}: YAML {e}');continue
        if not isinstance(y,dict) or not isinstance(y.get('type'),str) or not y['type'].strip():
            errors.append(f'{rel}: empty/missing type')
        for source in (y.get('sources') or []):
            r=source.get('resource') if isinstance(source,dict) else None
            if not r:errors.append(f'{rel}: bad sources')
            elif not re.match('^[A-Za-z]+://',r) and not (p.parent/r).exists():
                errors.append(f'{rel}: missing source target {r}')
    for target in re.findall(r'(?<!!)\[[^]]+\]\(([^)]+)\)',text):
        u=target.split('#')[0]
        if not u or re.match(r'^(?:[A-Za-z]+:|/)',u):continue
        if not (p.parent/u).exists():errors.append(f'{rel}: broken link {u}')
if not (root/'index.md').is_file() or not (root/'log.md').is_file():
    errors.append('Missing root index or log')
if errors:
    print('ERRORS',len(errors))
    for x in errors: print(' -',x)
    raise SystemExit(1)
print(f'OK: {len(concepts)} concepts; {len(list(root.rglob("index.md")))} indices; v0.2 frontmatter and local links validated')
