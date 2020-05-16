import unittest
from io import StringIO
from unittest.mock import patch
from sebs.cli import parse_args


class TestArugmentParsing(unittest.TestCase):

    def test_version(self):

        version = "2.1.0"
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            try:
                parse_args(['--version'], version)
            except:
                pass

        output = fakeOutput.getvalue().strip()
        self.assertTrue(version in output,
                        'Should display the proper version.')

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

    def test_verbose_level(self):
        args = parse_args(['-b test1', '-b test2', '-vvv'], '')

        self.assertEqual(args.verbose, 4)


if __name__ == '__main__':
    unittest.main()
