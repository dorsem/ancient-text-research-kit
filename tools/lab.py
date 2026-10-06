#!/usr/bin/env python3
"""Offline structural checks and a small, safe renderer for this kit's Markdown.

No model, network requests, scientific approval or general Markdown compliance.
"""
from pathlib import Path
from html import escape, unescape
from urllib.parse import urlsplit, unquote
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'source_assertion', 'observed_fact', 'interpretation', 'hypothesis'}
CONFIDENCE = {'high', 'medium', 'low', 'unknown'}
STATES = {'draft', 'checked', 'disputed'}
LINK = re.compile(r'(!?)\[([^\]]+)\]\(([^)]+)\)')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(root, path):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def content_files(root):
    return sorted(p for p in root.rglob('*') if p.is_file()
                  and not any(x in {'site', '.git', '__pycache__', '.build-tmp'}
                              or x.startswith('.staging-') for x in p.relative_to(root).parts)
                  and p.suffix != '.pyc' and p.name != '.DS_Store')


def input_hashes(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in content_files(root)}


def safe_url(url):
    decoded = unquote(unescape(url)).strip()
    scheme = urlsplit(decoded).scheme.lower()
    return not any(ord(c) < 32 for c in decoded) and (
        scheme in {'https', 'http'} or (not scheme and not decoded.startswith(('/', '\\'))
                                      and '\\' not in decoded))


def known_or_reason(value):
    return (isinstance(value, str) and bool(value.strip()) and value.lower() != 'unknown') or (
        isinstance(value, dict) and value.get('status') in {'unknown', 'not_applicable'}
        and isinstance(value.get('reason'), str) and bool(value['reason'].strip()))


def member(value, collection):
    return isinstance(value, str) and value in collection


def registry_errors(data):
    errors = []
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        return ['registry: expected schema_version 1 object']
    groups = {}
    for name in ('sources', 'witnesses', 'evidence', 'claims'):
        rows = data.get(name)
        if not isinstance(rows, list):
            errors.append(f'{name}: expected list'); rows = []
        by_id = {}
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', str(row.get('id', ''))):
                errors.append(f'{name}: missing or unsafe id'); continue
            key = row['id']
            if key in by_id:
                errors.append(f'{name}: duplicate {key}')
            by_id[key] = row
        groups[name] = by_id
    for key, row in groups['sources'].items():
        for field in ('title', 'independence_group', 'access_scope'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f'{key}: missing {field}')
        url = row.get('url')
        if not isinstance(url, str) or urlsplit(url).scheme not in {'https', 'http'} or not urlsplit(url).netloc or not safe_url(url):
            errors.append(f'{key}: expected source http(s) URL')
        if row.get('distribution') != 'link_only':
            errors.append(f'{key}: this version supports link_only sources')
    for key, row in groups['witnesses'].items():
        for field in ('inventory', 'object_date', 'inscription_date', 'composition_date', 'dating_basis'):
            if not known_or_reason(row.get(field)):
                errors.append(f'{key}: missing {field} or explicit reason')
    for key, row in groups['evidence'].items():
        if not member(row.get('source_id'), groups['sources']):
            errors.append(f'{key}: unknown source_id')
        if not known_or_reason(row.get('locator')):
            errors.append(f'{key}: missing locator or explicit reason')
        if not member(row.get('kind'), {'source_assertion', 'observed_fact'}):
            errors.append(f'{key}: invalid evidence kind')
        if not isinstance(row.get('description'), str) or not row['description'].strip():
            errors.append(f'{key}: missing description')
        refs = row.get('witness_ids')
        if not isinstance(refs, list) or not refs:
            errors.append(f'{key}: expected witness_ids')
        elif any(not member(x, groups['witnesses']) for x in refs):
            errors.append(f'{key}: unknown witness_id')
    for key, row in groups['claims'].items():
        for field, values in (('kind', KINDS), ('confidence', CONFIDENCE), ('review_status', STATES)):
            if not member(row.get(field), values):
                errors.append(f'{key}: invalid {field}')
        for field in ('alternative', 'next_check'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f'{key}: missing {field}')
        edges = row.get('evidence')
        if not isinstance(edges, list) or not edges:
            errors.append(f'{key}: requires evidence links'); edges = []
        seen = set()
        for edge in edges:
            if not isinstance(edge, dict):
                errors.append(f'{key}: invalid evidence edge'); continue
            eid = edge.get('evidence_id')
            relation = edge.get('relation')
            if not member(eid, groups['evidence']):
                errors.append(f'{key}: unknown evidence_id {eid}')
            if not member(relation, {'support', 'contradict', 'context'}):
                errors.append(f'{key}: invalid evidence relation')
            pair = (str(eid), str(relation))
            if pair in seen:
                errors.append(f'{key}: duplicate evidence edge')
            seen.add(pair)
        if row.get('review_status') == 'checked':
            review = row.get('review')
            if not isinstance(review, dict) or any(not review.get(f) for f in ('reviewer', 'role', 'method', 'date')):
                errors.append(f'{key}: checked requires attributed review')
            if not any(isinstance(e, dict) and e.get('relation') == 'support' for e in edges):
                errors.append(f'{key}: checked requires support')
            for edge in edges:
                if isinstance(edge, dict) and member(edge.get('evidence_id'), groups['evidence']):
                    if not isinstance(groups['evidence'][edge['evidence_id']].get('locator'), str):
                        errors.append(f'{key}: checked cannot rely on unknown locator')
    return errors


def heading_id(title, used):
    match = re.match(r'(C\d+)\.', title)
    stem = match[1].lower() if match else re.sub(r'[^\w-]+', '-', title.lower()).strip('-') or 'section'
    ident = stem
    n = 2
    while ident in used:
        ident = stem+'-'+str(n); n += 1
    used.add(ident)
    return ident


def anchors(text):
    used = set()
    for line in text.splitlines():
        m = re.match(r'#{1,6} (.+)', line)
        if m: heading_id(m[1], used)
    return used


def link_errors(root):
    errors = []
    for path in content_files(root):
        if path.suffix != '.md': continue
        text = path.read_text(encoding='utf-8')
        rel = path.relative_to(root)
        if re.search(r'/Users/|file://|/private/(?:tmp|var)/', text):
            errors.append(f'{rel}: private local path')
        for _, _, url in LINK.findall(text):
            if not safe_url(url):
                errors.append(f'{rel}: unsafe link {url}'); continue
            parts = urlsplit(url)
            if parts.scheme: continue
            target = (path.parent/unquote(parts.path)).resolve() if parts.path else path
            if not within(root, target):
                errors.append(f'{rel}: link escapes package {url}')
            elif not target.is_file():
                errors.append(f'{rel}: missing link {url}')
            elif parts.fragment and target.suffix == '.md' and unquote(parts.fragment) not in anchors(target.read_text(encoding='utf-8')):
                errors.append(f'{rel}: missing anchor {url}')
    return errors


def site_errors(root, require_fresh=True):
    site = root/'site'
    if not site.exists(): return []
    if site.is_symlink(): return ['site: symlink not allowed']
    if any(p.is_symlink() for p in site.rglob('*')): return ['site: symlinks not allowed']
    state = site/'build.json'
    if not state.is_file(): return ['site: existing directory has no build manifest; inspect it before rebuilding']
    try: data = json.loads(state.read_text())
    except (ValueError, OSError): return ['site: invalid build manifest']
    outputs = data.get('outputs', {})
    errors = []
    if not isinstance(outputs, dict): return ['site: invalid output manifest']
    for rel, expected in outputs.items():
        p = site/rel
        if not within(site, p) or not p.is_file() or p.is_symlink() or digest(p) != expected:
            errors.append(f'site: edited or missing generated file {rel}; reconcile before rebuilding')
    known = set(outputs) | {'build.json'}
    for p in site.rglob('*'):
        if p.is_file() and p.relative_to(site).as_posix() not in known:
            errors.append(f'site: untracked file {p.relative_to(site)}; preserve before rebuilding')
    if require_fresh and data.get('inputs') != input_hashes(root):
        errors.append('site: source files changed; run build after reconciling any HTML edits')
    return errors


def validate(root=ROOT, check_site=True):
    errors = []
    for p in content_files(root):
        if p.is_symlink() or not within(root, p): errors.append(f'package: unsafe file {p.name}')
    try:
        data = json.loads((root/'study/registry.json').read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        return [f'registry: cannot read {exc}']
    errors.extend(registry_errors(data))
    main = root/'study/reports/main_research.md'
    if main.exists():
        ids = re.findall(r'^### (C\d+)\.', main.read_text(encoding='utf-8'), re.M)
        if len(ids) != len(set(ids)): errors.append('main study: duplicate conclusion ID')
        expected = {c.get('id') for c in data.get('claims', []) if isinstance(c, dict)}
        if set(ids) != expected: errors.append('main study: conclusion IDs and registry disagree')
    else: errors.append('main study: missing')
    errors.extend(link_errors(root))
    if check_site: errors.extend(site_errors(root))
    return errors


def html_url(url):
    if not safe_url(url): raise ValueError('unsafe render URL')
    parts = urlsplit(url)
    if not parts.scheme and parts.path.endswith('.md'):
        return parts._replace(path=parts.path[:-3]+'.html').geturl()
    return url


def inline(text):
    # Only these literal tags are meaningful in scholarly readings. Attributes
    # and every other HTML construct are escaped, including scripts.
    token = re.compile(r'\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|(?<!\*)\*([^*]+)\*(?!\*)|</?(?:sup|sub|code|i)>')
    out = []; start = 0
    for m in token.finditer(text):
        out.append(escape(unescape(text[start:m.start()])))
        if m[1] is not None: out.append('<a href="'+escape(html_url(m[2]),quote=True)+'">'+escape(unescape(m[1]))+'</a>')
        elif m[3] is not None: out.append('<code>'+escape(unescape(m[3]))+'</code>')
        elif m[4] is not None: out.append('<strong>'+inline(m[4])+'</strong>')
        elif m[5] is not None: out.append('<em>'+escape(unescape(m[5]))+'</em>')
        else: out.append(m[0])
        start = m.end()
    out.append(escape(unescape(text[start:])))
    return ''.join(out)


CSS = '''body{max-width:1000px;margin:36px auto;padding:0 24px;background:#faf8f3;color:#292823;font:18px/1.65 Georgia,serif}h1{font-size:36px;line-height:1.2}h2{font-size:27px;margin-top:44px;line-height:1.3}h3{font-size:22px;line-height:1.4}a{color:#235f68;text-underline-offset:3px}nav,footer{font:14px/1.6 system-ui}nav a{margin-right:20px}table{border-collapse:collapse;font:15px/1.55 system-ui;width:100%;background:white}td,th{border:1px solid #d9d9d9;padding:10px;text-align:left;vertical-align:top}th{background:#e7eceb}.table{overflow:auto}pre{overflow:auto;background:#eee;padding:16px}code{font-size:.87em}li{margin:7px 0}footer{margin-top:45px;color:#555}a,td{overflow-wrap:anywhere}sup{font-size:.75em}@media(max-width:600px){body{padding:0 16px;font-size:17px}h1{font-size:29px}table{min-width:560px}}@media print{@page{size:A4;margin:18mm}body{background:white;margin:0;padding:0;font-size:11pt}nav,footer{display:none}h2,h3{break-after:avoid}table{font-size:9.5pt;min-width:0}tr{break-inside:avoid}a{color:inherit}}'''


def render(text, home, study):
    lines = text.splitlines(); i = 0; out = []; used = set(); title = 'Research kit'
    while i < len(lines):
        line = lines[i].strip()
        if not line: i += 1; continue
        if line.startswith('```'):
            code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i]); i += 1
            out.append('<pre><code>'+escape('\n'.join(code))+'</code></pre>'); i += 1; continue
        m = re.match(r'(#{1,6}) (.+)', line)
        if m:
            level, heading = len(m[1]), m[2]
            if level == 1: title = heading
            out.append(f'<h{level} id="{heading_id(heading,used)}">{inline(heading)}</h{level}>'); i += 1; continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{3,}:?',x) for x in row): rows.append(row)
                i += 1
            if len({len(row) for row in rows}) != 1: raise ValueError('ragged Markdown table')
            out.append('<div class="table"><table><thead><tr>'+''.join('<th scope="col">'+inline(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>')
            for row in rows[1:]: out.append('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>')
            out.append('</tbody></table></div>'); continue
        m = re.match(r'(?:- |\d+\. )(.+)',line)
        if m:
            ordered = not line.startswith('- '); tag = 'ol' if ordered else 'ul'; items=[]
            pattern = r'\d+\. (.+)' if ordered else r'- (.+)'
            while i < len(lines):
                m = re.match(pattern,lines[i].strip())
                if not m: break
                items.append('<li>'+inline(m[1])+'</li>'); i += 1
            out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>'); continue
        if line in {'---','***'}: out.append('<hr>'); i += 1; continue
        para=[line]; i += 1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#{1,6} |\||- |\d+\. |```)',lines[i].strip()):
            para.append(lines[i].strip()); i += 1
        out.append('<p>'+inline(' '.join(para))+'</p>')
    evidence=home.removesuffix('index.html')+'evidence.html'
    return '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+CSS+'</style></head><body><nav><a href="'+escape(home,quote=True)+'">О проекте</a><a href="'+escape(study,quote=True)+'">Исследование</a><a href="'+escape(evidence,quote=True)+'">Выводы и основания</a></nav><main>'+''.join(out)+'</main><footer>Рабочая редакция. Источники и разночтения проверяются отдельно от программных проверок. HTML собран из Markdown.</footer></body></html>'


def evidence_view(root):
    data=json.loads((root/'study/registry.json').read_text())
    source={s['id']:s for s in data['sources']}
    evidence={e['id']:e for e in data['evidence']}
    text=(root/'study/reports/main_research.md').read_text()
    blocks=re.split(r'(?=^### C\d+\.)',text,flags=re.M)
    sections={re.match(r'### (C\d+)\.',b)[1]:b.split('\n## ',1)[0].strip() for b in blocks if re.match(r'### (C\d+)\.',b)}
    md=['# Важные выводы и путь проверки', 'Формулировки взяты из основного текста, основания из реестра. Статус draft относится к отдельной проверке переносимого пакета. Сила основания и статус проверки различаются.']
    # These paragraphs move from study/reports to the site root. Retain each
    # source-relative link's target, including links to the source's own anchors.
    def main_link(match):
        import posixpath
        url = match[3]
        if not safe_url(url): raise ValueError('unsafe source section URL')
        parts = urlsplit(url)
        if parts.scheme: return match[0]
        target = (posixpath.normpath(posixpath.join('study/reports', parts.path))
                  if parts.path else 'study/reports/main_research.md')
        rebased = parts._replace(path=target).geturl()
        return f'{match[1]}[{match[2]}]({rebased})'

    for c in data['claims']:
        md.append(LINK.sub(main_link, sections[c['id']]))
        md.append(f"[В основном исследовании](study/reports/main_research.md#{c['id'].lower()}). Тип: {c['kind']}; уверенность: {c['confidence']}; проверка: {c['review_status']}.")
        md.append('Альтернатива: '+c['alternative']+' Следующая проверка: '+c['next_check'])
        for edge in c['evidence']:
            e=evidence[edge['evidence_id']]; s=source[e['source_id']]
            loc=e['locator'] if isinstance(e['locator'],str) else e['locator']['reason']
            relation={'support':'основание','contradict':'возражение','context':'контекст'}[edge['relation']]
            md.append(f"- **{e['id']}, {relation}.** [{s['id']}]({s['url']}), {loc}. {e['description']} Группа происхождения: {s['independence_group']}.")
    return render('\n\n'.join(md),'index.html','study/reports/main_research.html')


def build(root=ROOT):
    import os
    errors = validate(root, check_site=False) + site_errors(root, require_fresh=False)
    if errors: raise ValueError('\n'.join(errors))
    outputs = {}
    for p in content_files(root):
        rel = p.relative_to(root)
        if p.suffix == '.md':
            target = rel.with_suffix('.html')
            home = os.path.relpath(Path('index.html'),target.parent)
            study = os.path.relpath(Path('study/reports/main_research.html'),target.parent)
            outputs[target.as_posix()] = render(p.read_text(encoding='utf-8'),home,study).encode()
        elif rel.parts[0] in {'study','templates'} or p.name == 'CITATION.cff':
            outputs[rel.as_posix()] = p.read_bytes()
    outputs['index.html'] = outputs['README.html']
    outputs['evidence.html'] = evidence_view(root).encode()
    inputs = input_hashes(root)
    site = root/'site'; site.mkdir(exist_ok=True)
    # Render everything successfully before touching the previous build.
    for rel, blob in outputs.items():
        p = site/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(blob)
    previous = site/'build.json'
    if previous.exists():
        for rel in json.loads(previous.read_text()).get('outputs',{}):
            if rel not in outputs: (site/rel).unlink()
    manifest = {'schema_version':1,'inputs':inputs,'outputs':{key:hashlib.sha256(blob).hexdigest() for key,blob in outputs.items()},'scope':'structure and reproducible HTML, no scientific approval or page-count verification'}
    previous.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return len(outputs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','build'])
    args=parser.parse_args()
    if args.command=='build':
        try: print(json.dumps({'built_files':build(),'reader':'site/index.html'},ensure_ascii=False))
        except ValueError as exc: print(str(exc),file=sys.stderr); return 1
    else:
        errors=validate()
        if errors:
            print('\n'.join(errors),file=sys.stderr); return 1
        print('PASS: structure, local links and build freshness. Scientific review and pagination are separate.')
    return 0


if __name__=='__main__':
    sys.exit(main())
