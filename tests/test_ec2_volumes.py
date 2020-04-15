import sys
import unittest
import datetime
import botocore.session
from botocore.stub import Stubber, ANY
from unittest.mock import patch, MagicMock


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
        self.mock_volume = MagicMock(name='volume_mock')
        self.mock_volume_class = MagicMock(
            name='volume_class_mock', return_value=self.mock_volume)
        self.mock_volume_class.Volume = self.mock_volume
        self.mock_resource = MagicMock(
            name='resource_mock', return_value=self.mock_volume_class)
        self.boto3.resource = self.mock_resource

        modules = {
            'boto3': self.boto3
        }

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
                    'VolumeId': 'string',
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

        from sebs.ec2 import StatefulVolume, Instance

        self.StatefulVolume = StatefulVolume

    def tearDown(self):
        self.module_patcher.stop()
        self.stubber.deactivate()

    def test_new_volume(self):

        response = self.default_response.copy()
        response['Volumes'] = []

        self.stubber.add_response(
            'describe_volumes', response, self.default_params)

        sv = self.StatefulVolume('xdf', 'test')

        status = sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'New', 'Should be a new Volume')

    def test_duplicate_volumes(self):

        response = self.default_response.copy()
        response['Volumes'] = [{}, {}]

        self.stubber.add_response(
            'describe_volumes', response, self.default_params)

        sv = self.StatefulVolume('xdf', 'test')

        status = sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Duplicate',
                         'Should be a duplicate volume')

    def test_existing_volume(self):

        self.stubber.add_response(
            'describe_volumes', self.default_response, self.default_params)

        sv = self.StatefulVolume('xdf', 'test')

        status = sv.get_status()

        self.stubber.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Not Attached',
                         'Should find an existing volume')
        self.assertIsInstance(sv.volume, MagicMock,
                              'Should be our volume mock')

    def test_class_properties(self):
        sv = self.StatefulVolume('xdf', 'test')

        self.stubber.assert_no_pending_responses()

        self.assertEqual(sv.deviceName, 'xdf', 'Should set the deviceName')
        self.assertEqual(
            sv.ready, False, 'Should set the volume to not ready.')
        self.assertEqual(sv.status, 'Unknown', 'Should set the status')
        self.assertEqual(sv.volume, None, 'Should set the tag name')
        self.assertEqual(sv.tag_name, 'test', 'Should set the tag name')


if __name__ == '__main__':
    unittest.main()
