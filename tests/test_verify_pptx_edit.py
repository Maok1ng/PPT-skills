"""Small OOXML fixtures exercise regressions that escape slide-text checks."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('verify', Path(__file__).parents[1] / 'scripts/verify_pptx_edit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
P, A, R = (module.NS[k] for k in ('p', 'a', 'r'))
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def rels(items):
    return '<Relationships xmlns="' + REL + '">' + ''.join(
        f'<Relationship Id="{rid}" Type="{R}/{kind}" Target="{target}"/>'
        for rid, kind, target in items) + '</Relationships>'


def fixture(path, text2='unchanged', media=b'original-image', note='note', theme='000000', picture=False):
    with ZipFile(path, 'w') as z:
        z.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="r1"/><p:sldId id="257" r:id="r2"/></p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels', rels([('r1', 'slide', 'slides/first.xml'), ('r2', 'slide', 'slides/custom-second.xml')]))
        for name, text in [('first', 'editable'), ('custom-second', text2)]:
            pic = '<p:pic><p:blipFill><a:blip r:embed="img"/></p:blipFill></p:pic>' if picture and name == 'first' else ''
            z.writestr(f'ppt/slides/{name}.xml', f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>{pic}</p:spTree></p:cSld></p:sld>')
            z.writestr(f'ppt/slides/_rels/{name}.xml.rels', rels([('img', 'image', '../media/a.png'), ('n', 'notesSlide', '../notes/custom.xml'), ('l', 'slideLayout', '../layouts/base.xml')]))
        z.writestr('ppt/media/a.png', media)
        z.writestr('ppt/notes/custom.xml', f'<notes><text>{note}</text></notes>')
        z.writestr('ppt/layouts/base.xml', '<layout/>')
        z.writestr('ppt/layouts/_rels/base.xml.rels', rels([('t', 'theme', '../theme/theme.xml')]))
        z.writestr('ppt/theme/theme.xml', f'<theme color="{theme}"/>')


class VerifyEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a, self.b = (Path(self.tmp.name) / n for n in ('a.pptx', 'b.pptx'))
        fixture(self.a)

    def result(self, **changes):
        fixture(self.b, **changes)
        return module.verify(self.a, self.b, {1}, {1})

    def test_same_deck_and_custom_part_names(self):
        self.assertEqual(self.result()['status'], 'passed')

    def test_unrequested_text_edit_is_detected(self):
        self.assertEqual(self.result(text2='changed')['status'], 'review_required')

    def test_replaced_image_is_detected_even_if_slide_xml_is_equal(self):
        r = self.result(media=b'replacement-image')
        self.assertTrue(r['unchanged_slides'][0]['slide_xml_equal'])
        self.assertFalse(r['unchanged_slides'][0]['associated_parts_equal'])

    def test_notes_change_is_detected(self):
        self.assertEqual(self.result(note='modified note')['status'], 'review_required')

    def test_theme_change_is_detected_through_layout(self):
        self.assertEqual(self.result(theme='FF0000')['status'], 'review_required')

    def test_picture_does_not_pass_as_native_diagram(self):
        self.assertFalse(self.result(picture=True)['native_slides'][0]['passed'])

    def test_declared_change_is_permitted(self):
        fixture(self.b, text2='requested edit')
        self.assertEqual(module.verify(self.a, self.b, {2})['status'], 'passed')

    def test_out_of_range_page_is_rejected(self):
        fixture(self.b)
        with self.assertRaises(ValueError):
            module.verify(self.a, self.b, {3})


if __name__ == '__main__':
    unittest.main()
