import json
import boto3
import time
import unittest
import warnings

from tests.utils import aws_utils


class TestSebs(unittest.TestCase):

    def setUp(self):
        print('Setting up test environment...')
        warnings.filterwarnings(
            "ignore", category=ResourceWarning, message="unclosed.*<ssl.SSLSocket.*>")

        self.volume_cleanup = []
        self.instance_cleanup = []

        self.ec2 = boto3.resource('ec2')

        self.iam = boto3.resource('iam')

        iam_resources = aws_utils.create_iam_resources()

        self.iam_role = iam_resources['role']

        self.iam_role_policy = iam_resources['policy']

        self.instance_profile = iam_resources['profile']

        self.default_user_data = aws_utils.create_default_userdata()

        ami_id = aws_utils.get_latest_ami()

        self.default_instance = dict(BlockDeviceMappings=[],
                                     ImageId=ami_id,
                                     InstanceType='t1.micro',
                                     MaxCount=1,
                                     MinCount=1,
                                     Monitoring={'Enabled': False},
                                     UserData=self.default_user_data,
                                     IamInstanceProfile={
            'Arn': self.instance_profile.arn},
            TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': 'Test'
                    },
                ]
            }],
        )

    def tearDown(self):

        print('Running Cleanup...')
        for instance in self.instance_cleanup:
            print(f'Deleting {instance.id}')
            instance.terminate()

        for volume in self.volume_cleanup:
            print(f'Deleting {volume.id}')
            volume.delete()

        if self.instance_profile:
            print('Removing role from instance profile.')
            self.instance_profile.remove_role(
                RoleName=self.iam_role.name
            )

        if self.iam_role_policy:
            print(f'Deleting policy: {self.iam_role_policy}')
            self.iam_role_policy.delete()

        if self.iam_role:
            print(f'Deleting Role: {self.iam_role}')
            self.iam_role.delete()

        if self.instance_profile:
            print(f'Deleting Instance Profile: {self.instance_profile}')
            self.instance_profile.delete()

    def test_new_volume(self):

        device_name = '/dev/xvdh'
        server_config = self.default_instance.copy()
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device_name))

        control_tag = 'new-volume-sebs'
        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device_name} -n {control_tag}\n'
            f'while [ ! -e {device_name} ] ; do sleep 1 ; done\n'
        )

        instance = aws_utils.create_instance(server_config)

        self.instance_cleanup.append(instance)

        instance.wait_until_running()
        instance.reload()

        volume_id = aws_utils.get_volume_from_bdm(device_name, instance)

        self.assertTrue(volume_id, 'Should have the new volume attached')

        waiter = aws_utils.get_ec2_waiter('volume_in_use')
        waiter.wait(VolumeIds=[volume_id])

        volume = self.ec2.Volume(volume_id)

        aws_utils.wait_for_volume_tag(volume)

        tag_name, tag_value = aws_utils.get_control_tag(
            control_tag, volume.tags)

        self.assertEqual(tag_name, control_tag,
                         'Volume should be tagged with our control tag.')
        self.assertEqual(tag_value, device_name,
                         "Tag value should be it's device name.")
