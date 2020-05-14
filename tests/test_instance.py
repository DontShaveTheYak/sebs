import unittest
from sebs.ec2 import Instance
from unittest.mock import patch, MagicMock, call


class TestInstance(unittest.TestCase):

    def setUp(self):
        self.default_tag = 'sebs'
        self.device_name = '/dev/xdf'
        self.mock_instance = MagicMock(name='mock_instance', id='in-1111')

    def tearDown(self):
        pass

    @patch('sebs.ec2.Instance.get_instance')
    def test_class_properites(self, mock_method):
        mock_method.return_value = self.mock_instance

        server = Instance(self.default_tag)

        self.assertEqual(server.instance, self.mock_instance,
                         'Should set an instance field.')
        self.assertEqual(server.volume_tag, self.default_tag,
                         'Should set volume_tag field.')
        self.assertEqual(server.backup, [], 'Should have empty backup list.')

        mock_method.assert_called_once()

    @patch('sebs.ec2.StatefulVolume')
    @patch('sebs.ec2.Instance.get_instance')
    def test_add_device(self, mock_method, mock_volume_class):
        mock_method.return_value = self.mock_instance
        mock_volume = MagicMock(name='mock_volume')
        mock_volume_class.return_value = mock_volume

        server = Instance(self.default_tag)

        server.add_stateful_device(self.device_name)

        mock_method.assert_called_once()
        mock_volume_class.assert_called_once()
        mock_volume_class.assert_called_once_with(
            self.mock_instance.id, self.device_name, self.default_tag)
        self.assertIn(mock_volume, server.backup,
                      'Should put our device in the backup list.')
        mock_volume.get_status.assert_called_once()

    @patch('sebs.ec2.StatefulVolume')
    @patch('sebs.ec2.Instance.get_instance')
    def test_add_multiple_devices(self, mock_method, mock_volume_class):
        mock_method.return_value = self.mock_instance
        mock_volume = MagicMock(name='mock_volume_1')
        mock_volume2 = MagicMock(name='mock_volume_1')
        mock_volume_class.return_value = mock_volume

        server = Instance(self.default_tag)

        server.add_stateful_device(self.device_name)
        server.add_stateful_device('/dev/2')

        mock_method.assert_called_once()
        self.assertEqual(mock_volume_class.call_count, 2,
                         'Should create two volumes.')

        mock_volume_class.assert_has_calls(
            [call(self.mock_instance.id, self.device_name, self.default_tag),
             call(self.mock_instance.id, '/dev/2', self.default_tag)])

        self.assertEqual(len(server.backup), 2, 'Should have two volumes.')
        self.assertEqual(mock_volume.get_status.call_count, 2,
                         'Should have called get_status twice')


if __name__ == '__main__':
    unittest.main()
