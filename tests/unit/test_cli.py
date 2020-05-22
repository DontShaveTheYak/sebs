import unittest
from io import StringIO
from unittest.mock import patch
from sebs.cli import parse_args

try:
    from importlib import metadata
except ImportError:
    # Running on pre-3.8 Python; use importlib-metadata package
    import importlib_metadata as metadata


class TestArugmentParsing(unittest.TestCase):

    def test_version(self):

        expected_version = metadata.version('sebs')
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            try:
                parse_args(['--version'])
            except:
                pass

        output = fakeOutput.getvalue().strip()

        self.assertTrue(expected_version in output,
                        'Should display the proper version.')

    def test_single_backup(self):
        args = parse_args(['-b', 'test'])
        self.assertEqual(len(args.backup), 1)

    def test_multiple_backup(self):
        args = parse_args(['-b', 'test1', '-b', 'test2'])

        self.assertEqual(len(args.backup), 2)

    def test_default_name(self):
        args = parse_args(['-b', 'test1', '-b', 'test2'])

        self.assertEqual(args.name, 'sebs')

    def test_override_name(self):
        args = parse_args(
            ['-b', 'test1', '-b', 'test2', '-n', 'not-default'])

        self.assertEqual(args.name, 'not-default-sebs')

    def test_verbose_level(self):
        args = parse_args(['-b', 'test1', '-b', 'test2', '-vvv'])

        self.assertEqual(args.verbose, 4)


if __name__ == '__main__':
    unittest.main()
