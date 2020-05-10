import sys
import unittest
import datetime
import botocore.session
from botocore.stub import Stubber, ANY
from unittest.mock import patch, MagicMock, Mock


class TestStatefulVolume(unittest.TestCase):

    def setUp(self):
        # Setup our ec2 client stubb
        ec2 = botocore.session.get_session().create_client('ec2')
        self.stub_client = ec2
        self.stubber = Stubber(ec2)

        # Use mocks to pass out client stubb to our code
        self.boto3 = MagicMock(name='module_mock')
        self.mock_client = MagicMock(name='client_mock', return_value=ec2)
        self.boto3.client = self.mock_client

        # Setup resource and volume mocks
        self.actual_volume = Mock(name='actual_volume')
        self.mock_volume = MagicMock(
            name='volume_mock', return_value=self.actual_volume)
        self.mock_volume_class = MagicMock(
            name='volume_class_mock', return_value=self.mock_volume)
        self.mock_volume_class.Volume = self.mock_volume
        self.mock_resource = MagicMock(
            name='resource_mock', return_value=self.mock_volume_class)
        self.boto3.resource = self.mock_resource

        modules = {
            'boto3': self.boto3,
            'ec2_metadata': MagicMock()
        }

        self.instance_id = 'i-1234567890abcdef0'
        self.tag_name = 'sebs'
        self.device_name = '/dev/xdf'

        self.default_response = {
            'Volumes': [
                {
                    'Attachments': [],
                    'AvailabilityZone': 'string',
                    'CreateTime': datetime.datetime(2015, 1, 1),
                    'Encrypted': False,
                    'KmsKeyId': 'string',
                    'OutpostArn': 'string',
                    'Size': 123,
                    'SnapshotId': 'string',
                    'State': 'available',
                    'VolumeId': 'vol-XXXXXX',
                    'Iops': 123,
                    'Tags': [
                        {
                            'Key': 'string',
                            'Value': 'string'
                        },
                    ],
                    'VolumeType': 'gp2',
                    'FastRestored': False,
                    'MultiAttachEnabled': False
                }
            ]
        }

        self.default_params = {'Filters': ANY}

        self.stubber.activate()

        self.module_patcher = patch.dict('sys.modules', modules)
        self.module_patcher.start()

        from sebs.ec2 import StatefulVolume

        self.StatefulVolume = StatefulVolume

    def tearDown(self):
        self.module_patcher.stop()
        self.stubber.deactivate()

    def test_new_volume(self):

        response = self.default_response.copy()
        response['Volumes'] = []

        self.stubber.add_response(
            'describe_volumes', response, self.default_params)

        self.stubber.add_response(
            'describe_volumes', self.default_response, {'Filters': [
                {
                    'Name': 'attachment.instance-id',
                    'Values': [self.instance_id]
                },
                {
                    'Name': 'attachment.device',
                    'Values': [
                        self.device_name,
                    ]
                }
            ]})

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Mounted',
                         'Volume should be mounted already.')
        self.assertIsInstance(sv.volume, Mock,
                              'Should have a boto3 Volume resource')
        self.assertEqual(sv.ready, True, 'Should be ready.')

    def test_duplicate_volumes(self):

        response = self.default_response.copy()
        response['Volumes'] = [{}, {}]

        self.stubber.add_response(
            'describe_volumes', response, self.default_params)

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Duplicate',
                         'Should be a duplicate volume')
        self.assertEqual(sv.ready, False, 'Volume should not be Ready')

    def test_existing_volume(self):

        self.stubber.add_response(
            'describe_volumes', self.default_response, self.default_params)

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Not Attached',
                         'Should find an existing volume')
        self.assertIsInstance(sv.volume, Mock,
                              'Should be our volume mock')
        self.assertEqual(sv.ready, False, 'Volume should not be Ready')

    def test_class_properties(self):
        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        self.stubber.assert_no_pending_responses()

        self.assertEqual(sv.device_name, self.device_name,
                         'Should set the deviceName')
        self.assertEqual(
            sv.ready, False, 'Should set the volume to not ready.')
        self.assertEqual(sv.status, 'Unknown', 'Should set the status')
        self.assertEqual(sv.volume, None, 'Should set the tag name')
        self.assertEqual(sv.tag_name, self.tag_name, 'Should set the tag name')

    def test_volume_tagging(self):
        response = self.default_response.copy()
        response['Volumes'] = []

        self.stubber.add_response(
            'describe_volumes', response, {'Filters': [
                {
                    'Name': f'tag:{self.tag_name}',
                    'Values': [self.device_name]
                }
            ]})

        self.stubber.add_response(
            'describe_volumes', self.default_response, {'Filters': [
                {
                    'Name': 'attachment.instance-id',
                    'Values': [self.instance_id]
                },
                {
                    'Name': 'attachment.device',
                    'Values': [
                        self.device_name,
                    ]
                }
            ]})

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        sv.tag_volume()

        self.actual_volume.create_tags.assert_called_with(
            Tags=[{'Key': self.tag_name, 'Value': self.device_name}])


if __name__ == '__main__':
    unittest.main()
