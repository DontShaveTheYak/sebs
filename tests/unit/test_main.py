import unittest
import argparse
from sebs.app import main
from unittest.mock import MagicMock, patch


class TestApplicaton(unittest.TestCase):

    @patch('sebs.app.Instance')
    @patch('sebs.ec2.ec2_metadata')
    def test_main(self, mock_metadata, mock_class):
        mock_instance = MagicMock(name='mock_instance')
        mock_class.return_value = mock_instance

        args = argparse.Namespace(name='sebs', backup=['/dev/xdv', '/dev/svh'])
        with self.assertRaises(SystemExit):
            main(args)

        mock_class.assert_called_once_with('sebs')
        mock_instance.add_stateful_device.assert_any_call('/dev/xdv')
        mock_instance.add_stateful_device.assert_any_call('/dev/svh')
        mock_instance.attach_stateful_volumes.assert_called_once()
        mock_instance.tag_stateful_volumes.assert_called_once()


if __name__ == '__main__':
    unittest.main()
