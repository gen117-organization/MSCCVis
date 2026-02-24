import unittest
import pandas as pd
from .data_loader import build_file_tree_data, get_clone_related_files

class TestUILogic(unittest.TestCase):
    def test_build_file_tree_data(self):
        paths = [
            'src/A/file1.java',
            'src/A/file2.java',
            'src/B/sub/file3.java',
            'root_file.txt'
        ]
        
        tree = build_file_tree_data(paths)
        
        # Check root structure
        self.assertIn('src', tree)
        self.assertIn('root_file.txt', tree)
        self.assertEqual(tree['root_file.txt'], '__FILE__')
        
        # Check src structure
        src = tree['src']
        self.assertIn('A', src)
        self.assertIn('B', src)
        
        # Check A structure
        a = src['A']
        self.assertIn('file1.java', a)
        self.assertIn('file2.java', a)
        self.assertEqual(a['file1.java'], '__FILE__')
        
        # Check B structure
        b = src['B']
        self.assertIn('sub', b)
        sub = b['sub']
        self.assertIn('file3.java', sub)
        self.assertEqual(sub['file3.java'], '__FILE__')

    def test_get_clone_related_files(self):
        data = {
            'file_path_x': ['A/f1.java', 'B/f2.java', None],
            'file_path_y': ['A/f1.java', 'C/f3.java', 'B/f2.java']
        }
        df = pd.DataFrame(data)
        
        files = get_clone_related_files(df)
        
        expected = ['A/f1.java', 'B/f2.java', 'C/f3.java']
        self.assertEqual(sorted(files), sorted(expected))

if __name__ == '__main__':
    unittest.main()
