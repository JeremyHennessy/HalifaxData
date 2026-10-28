import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from public_schema import validate_public_shape
class PublicationShape(unittest.TestCase):
    def setUp(self):self.bundle=json.loads((ROOT/'data/foundation.json').read_text())
    def test_actual(self):validate_public_shape(self.bundle)
    def test_unknown_private_top_level(self):
        self.bundle['internalNotes']={'person':'private'}
        with self.assertRaises(ValueError):validate_public_shape(self.bundle)
    def test_unknown_nested_personal_data(self):
        self.bundle['moneyFacts'][0]['medicalDetails']='private'
        with self.assertRaises(ValueError):validate_public_shape(self.bundle)
    def test_unknown_provenance_payload(self):
        self.bundle['sources'][0]['provenance']['credentials']={'secret':'private'}
        with self.assertRaises(ValueError):validate_public_shape(self.bundle)
    def test_nested_object_inside_free_text_rejected(self):
        self.bundle['investigations'][0]['summary']={'secret':'private'}
        with self.assertRaises(ValueError):validate_public_shape(self.bundle)
if __name__=='__main__':unittest.main()
