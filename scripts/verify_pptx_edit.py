#!/usr/bin/env python3
"""Conservative, read-only verification for fixed-order PPTX slide edits."""
import argparse
import hashlib
import json
import posixpath
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def xml_model(node):
    # Namespace prefixes and XML attribute ordering carry no semantic change.
    # Retain text exactly: an inserted space can affect rendered text.
    return (node.tag, tuple(sorted(node.attrib.items())),
            node.text if node.text and node.text.strip() else '',
            tuple(xml_model(child) for child in node))


class Deck:
    def __init__(self, path):
        self.zip = ZipFile(path)
        self.names = set(self.zip.namelist())
        if len(self.names) != len(self.zip.namelist()):
            self.zip.close()
            raise ValueError('PPTX has duplicate ZIP members')
        self.models = {}

    def close(self):
        self.zip.close()

    def relationships(self, part):
        relpart = posixpath.join(posixpath.dirname(part), '_rels',
                                 posixpath.basename(part) + '.rels')
        if relpart not in self.names:
            return []
        result = []
        for rel in ET.fromstring(self.zip.read(relpart)):
            target = rel.attrib['Target']
            mode = rel.get('TargetMode', 'Internal')
            if mode != 'External':
                target = (target.lstrip('/') if target.startswith('/') else
                          posixpath.normpath(posixpath.join(posixpath.dirname(part), target)))
                if target.startswith('../') or target not in self.names:
                    raise ValueError('PPTX relationship references a missing part')
            result.append((rel.attrib['Id'], rel.attrib['Type'], mode, target))
        return result

    def slides(self):
        rels = {rid: target for rid, kind, mode, target in self.relationships('ppt/presentation.xml')
                if kind.endswith('/slide') and mode == 'Internal'}
        root = ET.fromstring(self.zip.read('ppt/presentation.xml'))
        return [rels[n.attrib['{' + NS['r'] + '}id']]
                for n in root.findall('p:sldIdLst/p:sldId', NS)]

    def content(self, part):
        if part not in self.models:
            raw = self.zip.read(part)
            if part.endswith('.xml'):
                model = repr(xml_model(ET.fromstring(raw))).encode('utf-8')
            else:
                model = raw
            self.models[part] = hashlib.sha256(model).hexdigest()
        return self.models[part]

    def dependencies(self, part, stack=()):
        # Skip backlinks to slide bodies, so a notes part does not compare the
        # edited slide again. Still inspect notes, masters, themes and media.
        rows = []
        for rid, kind, mode, target in self.relationships(part):
            if kind.endswith('/slide'):
                continue
            if mode == 'External':
                rows.append((rid, kind, mode, target))
            elif target in stack or target == part:
                rows.append((rid, kind, mode, 'cycle'))
            else:
                rows.append((rid, kind, mode, self.content(target),
                             self.dependencies(target, stack + (part,))))
        return tuple(sorted(rows))

    def native_summary(self, part):
        root = ET.fromstring(self.zip.read(part))
        local = lambda node: node.tag.rsplit('}', 1)[-1]
        texts = len(root.findall('.//p:sp/p:txBody', NS))
        pictures = len(root.findall('.//p:pic', NS))
        blips = sum(local(n) in ('blip', 'svgBlip') for n in root.iter())
        ole = sum(local(n) == 'oleObj' for n in root.iter())
        data = sum(local(n) in ('tbl', 'chart', 'oMath') for n in root.iter())
        return {'editable_text_frames': texts, 'native_data_objects': data,
                'picture_objects': pictures, 'image_references': blips,
                'embedded_ole_objects': ole,
                'passed': texts + data > 0 and pictures + blips + ole == 0}


def verify(before, after, changed, native=()):
    a, b = Deck(before), None
    try:
        b = Deck(after)
        aa, bb = a.slides(), b.slides()
        if len(aa) != len(bb):
            raise ValueError('Page counts differ; use an explicit page mapping instead')
        if any(n < 1 or n > len(aa) for n in set(changed) | set(native)):
            raise ValueError('Slide numbers must be within the current deck')
        kept, objects = [], []
        for i, (old, new) in enumerate(zip(aa, bb), 1):
            if i not in changed:
                kept.append({'page': i, 'slide_xml_equal': a.content(old) == b.content(new),
                             'associated_parts_equal': a.dependencies(old) == b.dependencies(new)})
            if i in native:
                objects.append({'page': i, **b.native_summary(new)})
        ok = all(n['slide_xml_equal'] and n['associated_parts_equal'] for n in kept)
        ok = ok and all(n['passed'] for n in objects)
        return {'status': 'passed' if ok else 'review_required', 'slide_count': len(aa),
                'unchanged_slides': kept, 'native_slides': objects,
                'limits': 'Structural comparison only; inspect rendering, meaning and actual editing separately.'}
    finally:
        a.close()
        if b is not None:
            b.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--changed-slides', type=int, nargs='*', default=[])
    parser.add_argument('--native-slides', type=int, nargs='*', default=[])
    args = parser.parse_args()
    try:
        result = verify(args.before, args.after, set(args.changed_slides), set(args.native_slides))
    except (OSError, KeyError, ValueError, BadZipFile, ET.ParseError) as exc:
        parser.exit(2, f'Cannot verify PPTX: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
