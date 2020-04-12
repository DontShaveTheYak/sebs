import unittest
from sebs.cli import parse_args


class TestArugmentParsing(unittest.TestCase):

    def setUp(self):
        pass

    def test_version(self):

        try:
            version = "2.1.0"
            parse_args(['--version'], version)
        except:
            pass

    def test_single_backup(self):
        args = parse_args(['-b test'], '')
        self.assertEqual(len(args.backup), 1)

    def test_multiple_backup(self):
        args = parse_args(['-b test1', '-b test2'], '')

        self.assertEqual(len(args.backup), 2)

    def test_default_name(self):
        args = parse_args(['-b test1', '-b test2'], '')

        self.assertEqual(args.name, 'sebs')

    def test_override_name(self):
        args = parse_args(['-b test1', '-b test2', '-n not-default'], '')

        self.assertEqual(args.name, ' not-default')


if __name__ == '__main__':
    unittest.main()
