import unittest
from sebs.ec2 import Instance
from unittest.mock import patch, MagicMock, call, PropertyMock


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

        # Instead of None it should be a session...
        # but I can't figure out how to make a mock method (get_instance)
        # set a class field self.session as a side effect.
        mock_volume_class.assert_called_once_with(None,
                                                  self.mock_instance.id,
                                                  self.device_name,
                                                  self.default_tag)
        self.assertIn(mock_volume, server.backup,
                      'Should put our device in the backup list.')
        mock_volume.get_status.assert_called_once()

    @patch('sebs.ec2.StatefulVolume')
    @patch('sebs.ec2.Instance.get_instance')
    def test_add_multiple_devices(self, mock_method, mock_volume_class):
        mock_method.return_value = self.mock_instance
        mock_volume = MagicMock(name='mock_volume_1')
        mock_volume_class.return_value = mock_volume

        server = Instance(self.default_tag)

        server.add_stateful_device(self.device_name)
        server.add_stateful_device('/dev/2')

        mock_method.assert_called_once()
        self.assertEqual(mock_volume_class.call_count, 2,
                         'Should create two volumes.')

        # Same as above test, need to replace None with session
        mock_volume_class.assert_has_calls(
            [call(None, self.mock_instance.id, self.device_name, self.default_tag),
             call(None, self.mock_instance.id, '/dev/2', self.default_tag)])

        self.assertEqual(len(server.backup), 2, 'Should have two volumes.')
        self.assertEqual(mock_volume.get_status.call_count, 2,
                         'Should have called get_status twice')

    @patch('sebs.ec2.Instance.get_instance')
    def test_tag_volumes(self, mock_method):
        server = Instance(self.default_tag)
        mock_volume = MagicMock(name='mock_volume_1', status='Not Attached')
        mock_volume2 = MagicMock(name='mock_volume_2', status='Missing')

        server = Instance(self.default_tag)
        server.backup = [mock_volume, mock_volume2]
        server.tag_stateful_volumes()

        # Should tag one volume but not the other.
        mock_volume.tag_volume.assert_called_once()
        mock_volume2.tag_volume.assert_not_called()

    @patch('sebs.ec2.ec2_metadata')
    @patch('sebs.ec2.Instance.get_instance')
    def test_attach_volumes(self, mock_method, mock_metadata):

        p = PropertyMock(return_value='AZ2')
        type(mock_metadata).availability_zone = p

        mock_volume = MagicMock(name='mock_volume_1', status='Not Attached')
        mock_volume2 = MagicMock(name='mock_volume_2', status='Missing')

        server = Instance(self.default_tag)
        server.backup = [mock_volume, mock_volume2]
        server.attach_stateful_volumes()

        # Should Attach one volume but not the other.
        mock_volume.copy.assert_called_once_with('AZ2')
        mock_volume.attach.assert_called_once()

        mock_volume2.copy.assert_not_called()
        mock_volume2.attach.assert_not_called()


if __name__ == '__main__':
    unittest.main()
