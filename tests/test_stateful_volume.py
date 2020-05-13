import sys
import boto3
import unittest
import datetime
import botocore.session
from botocore.stub import Stubber, ANY
from unittest.mock import patch, MagicMock, Mock


class TestStatefulVolume(unittest.TestCase):

    def setUp(self):

        self.instance_id = 'i-1234567890abcdef0'
        self.tag_name = 'sebs'
        self.device_name = '/dev/xdf'

        # Setup our ec2 client stubb
        ec2 = botocore.session.get_session().create_client('ec2')
        self.ec2_client = ec2
        self.stub_client = Stubber(ec2)

        # Setup our ec2 resource stub
        ec2_resource = boto3.resource('ec2')
        self.stub_resource = Stubber(ec2_resource.meta.client)

        # Use mocks to pass out client stubb to our code
        self.boto3 = MagicMock(name='module_mock')
        self.mock_client = MagicMock(name='client_mock', return_value=ec2)
        self.mock_resource = MagicMock(
            name='resource_mock', return_value=ec2_resource)
        self.boto3.client = self.mock_client
        self.boto3.resource = self.mock_resource

        # Setup resource and volume mocks
        self.mock_snapshot = MagicMock(
            name='snapshot_mock', snapshot_id='sn-12345')
        self.actual_volume = Mock(name='actual_volume',
                                  attachments=[{'InstanceId': ''}], volume_type='GP2', volume_id='vol-1111')

        self.actual_volume.create_snapshot = Mock(
            return_value=self.mock_snapshot)
        self.mock_volume = MagicMock(
            name='volume_mock', return_value=self.actual_volume)
        self.mock_volume_class = MagicMock(
            name='volume_class_mock', return_value=self.mock_volume)
        self.mock_volume_class.Volume = self.mock_volume

        self.boto3.resource = MagicMock(
            name='resource_mock', return_value=self.mock_volume_class)

        modules = {
            'boto3': self.boto3,
            'ec2_metadata': MagicMock()
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

        self.stub_client.activate()

        self.module_patcher = patch.dict('sys.modules', modules)
        self.module_patcher.start()

        from sebs.ec2 import StatefulVolume

        self.StatefulVolume = StatefulVolume

    def tearDown(self):
        self.module_patcher.stop()
        self.stub_client.deactivate()

    def test_class_properties(self):
        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        self.stub_client.assert_no_pending_responses()

        self.assertEqual(sv.instance_id, self.instance_id,
                         'Should set the instance_id we pass in.')
        self.assertEqual(sv.device_name, self.device_name,
                         'Should set the deviceName')
        self.assertEqual(
            sv.ready, False, 'Should set the volume to not ready.')
        self.assertEqual(sv.status, 'Unknown', 'Should set the status')
        self.assertEqual(sv.volume, None, 'Should set the tag name')
        self.assertEqual(sv.tag_name, self.tag_name, 'Should set the tag name')
        self.assertEqual(sv.ec2_client, self.ec2_client,
                         'Should set an ec2 client')
        self.assertEqual(sv.ec2_resource, self.mock_volume_class,
                         'Should set our mock volume.')

    def test_status_new(self):

        response = self.default_response.copy()
        response['Volumes'] = []

        self.stub_client.add_response(
            'describe_volumes', response, self.default_params)

        self.stub_client.add_response(
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

        self.stub_client.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Attached',
                         'Volume should be mounted already.')
        self.assertIsInstance(sv.volume, Mock,
                              'Should have a boto3 Volume resource')
        self.assertEqual(sv.ready, True, 'Should be ready.')

    def test_status_missing(self):

        response = self.default_response.copy()
        response['Volumes'] = []

        self.stub_client.add_response(
            'describe_volumes', response, self.default_params)

        self.stub_client.add_response(
            'describe_volumes', response, {'Filters': [
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

        self.stub_client.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Missing',
                         'We should not find a tagged volume.')
        self.assertEqual(sv.volume, None,
                         'Should not have set a volume resourse.')
        self.assertEqual(sv.ready, False, 'Should not be ready.')

    def test_status_duplicate(self):

        response = self.default_response.copy()
        response['Volumes'] = [{}, {}]

        self.stub_client.add_response(
            'describe_volumes', response, self.default_params)

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        self.stub_client.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Duplicate',
                         'Should be a duplicate volume')
        self.assertEqual(sv.volume, None,
                         'Should not have set a volume resourse.')
        self.assertEqual(sv.ready, False, 'Volume should not be Ready')

    def test_status_not_attached(self):

        self.mock_volume

        self.stub_client.add_response(
            'describe_volumes', self.default_response, self.default_params)

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        sv.get_status()

        self.stub_client.assert_no_pending_responses()
        self.assertEqual(sv.status, 'Not Attached',
                         'Should find an existing volume')
        self.assertEqual(sv.volume, self.actual_volume,
                         'Should be our volume mock')
        self.assertEqual(sv.ready, False, 'Volume should not be Ready')

    def test_volume_tagging(self):
        response = self.default_response.copy()
        response['Volumes'] = []

        self.stub_client.add_response(
            'describe_volumes', response, {'Filters': [
                {
                    'Name': f'tag:{self.tag_name}',
                    'Values': [self.device_name]
                }
            ]})

        self.stub_client.add_response(
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

    def test_copy_new(self):
        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)
        sv.status = 'New'

        response = sv.copy('fakeAZ')

        self.assertEqual(response, sv.status,
                         "Should do nothing if status in not 'Not Attached'.")

    def test_copy_same_az(self):
        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        self.actual_volume.availability_zone = 'fakeAZ'
        sv.status = 'Not Attached'
        sv.volume = self.actual_volume

        response = sv.copy('fakeAZ')

        self.assertEqual(response, sv.status,
                         "Should not change the status if in the same AZ.")
        self.actual_volume.copy.assert_not_called()

    def test_copy_different_az(self):

        self.stub_client.add_response(
            'create_volume', {'VolumeId': 'vol-2222',
                              'AvailabilityZone': 'newAZ',
                              'Encrypted': True,
                              'Size': 50,
                              'SnapshotId': 'sn-2323',
                              'VolumeType': 'gp2'}, {'AvailabilityZone': 'newAZ',
                                                     'SnapshotId': ANY,
                                                     'VolumeType': ANY,
                                                     'TagSpecifications': ANY})

        # Volume ID's dont match here because we are not creating a second mock volume correctly
        self.stub_client.add_response('describe_volumes', {'Volumes': [
                                      {'VolumeId': 'vol-2222', 'State': 'available'}]}, {'VolumeIds': ['vol-1111']})

        sv = self.StatefulVolume(
            self.instance_id, self.device_name, self.tag_name)

        self.actual_volume.availability_zone = 'fakeAZ'
        sv.status = 'Not Attached'
        sv.volume = self.actual_volume

        response = sv.copy('newAZ')

        # Last test we need here is that we are actually creating a second volume
        self.assertEqual(response, sv.status,
                         'Should not change the status after a copy')
        self.assertFalse(sv.ready, 'We should not be ready after copying.')
        self.actual_volume.delete.assert_called_once()
        self.mock_snapshot.delete.assert_called_once()


if __name__ == '__main__':
    unittest.main()
