import time
import json
import boto3
import unittest
import warnings
from tests.utils import aws_utils
from botocore.exceptions import ClientError


class TestSebs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print('Setting up environment...')

        warnings.filterwarnings(
            "ignore", category=ResourceWarning, message="unclosed.*<ssl.SSLSocket.*>")

        iam_resources = aws_utils.create_iam_resources()

        cls.iam_role = iam_resources['role']

        cls.iam_role_policy = iam_resources['policy']

        cls.instance_profile = iam_resources['profile']

        cls.default_user_data = aws_utils.create_default_userdata()

        ami_id = aws_utils.get_latest_ami()

        cls.default_instance = dict(BlockDeviceMappings=[],
                                    ImageId=ami_id,
                                    InstanceType='t1.micro',
                                    MaxCount=1,
                                    MinCount=1,
                                    Monitoring={'Enabled': False},
                                    UserData=cls.default_user_data,
                                    IamInstanceProfile={
            'Arn': cls.instance_profile.arn},
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

        print('Environment setup.')

    @classmethod
    def tearDownClass(cls):
        print('Cleaning up environment...')

        if cls.instance_profile:
            print('Removing role from instance profile.')
            cls.instance_profile.remove_role(
                RoleName=cls.iam_role.name
            )

        if cls.iam_role_policy:
            print(f'Deleting policy: {cls.iam_role_policy}')
            cls.iam_role_policy.delete()

        if cls.iam_role:
            print(f'Deleting Role: {cls.iam_role}')
            cls.iam_role.delete()

        if cls.instance_profile:
            print(f'Deleting Instance Profile: {cls.instance_profile}')
            cls.instance_profile.delete()

        print('Environment Cleanup Finished')

    def setUp(self):

        print('Setting up test.')
        self.volume_cleanup = []
        self.instance_cleanup = []

        self.ec2 = boto3.resource('ec2')

        self.iam = boto3.resource('iam')

        print('Finished test setup.')

    def tearDown(self):

        print('Running Test Cleanup...')
        for instance in self.instance_cleanup:
            print(f'Deleting {instance.id}')
            instance.terminate()

            waiter = aws_utils.get_ec2_waiter('instance_terminated')

            waiter.wait(InstanceIds=[instance.id])

        for volume in self.volume_cleanup:
            print(f'Deleting {volume.id}')
            try:
                volume.delete()
            except ClientError as e:
                if e.response['Error']['Code'] != 'InvalidVolume.NotFound':
                    raise e

        print('Test Cleanup Finished')

    def test_new_volume(self):

        print('Starting test_new_volume')
        control_tag = 'new-volume-sebs'
        device_name = '/dev/xvdh'

        server_config = self.__class__.default_instance.copy()
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device_name))

        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device_name} -n {control_tag} -vvv\n'
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

        volume_tagged = aws_utils.has_control_tag(
            control_tag, device_name, volume)

        self.assertTrue(volume_tagged, 'Volume should have our control tag.')

        print('Finshed test_new_volume')

    def test_new_volumes(self):

        print('Starting test_new_volumes')

        control_tag = 'new-volumes-sebs'
        device1_name = '/dev/xvdh'
        device2_name = '/dev/xvdm'

        server_config = self.__class__.default_instance.copy()
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device1_name))
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device2_name))

        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device1_name} -b {device2_name} -n {control_tag} -vvv\n'
            f'while [ ! -e {device1_name} ] ; do sleep 1 ; done\n'
            f'while [ ! -e {device2_name} ] ; do sleep 1 ; done\n'
        )

        instance = aws_utils.create_instance(server_config)

        self.instance_cleanup.append(instance)

        instance.wait_until_running()
        instance.reload()

        volume1_id = aws_utils.get_volume_from_bdm(device1_name, instance)
        volume2_id = aws_utils.get_volume_from_bdm(device2_name, instance)

        self.assertTrue(
            volume1_id, 'Should have the new volume attached')
        self.assertTrue(
            volume2_id, 'Should have the new volume attached')

        waiter = aws_utils.get_ec2_waiter('volume_in_use')
        waiter.wait(VolumeIds=[volume1_id])
        waiter.wait(VolumeIds=[volume2_id])

        volume1 = self.ec2.Volume(volume1_id)
        volume2 = self.ec2.Volume(volume2_id)

        volume1_tagged = aws_utils.has_control_tag(
            control_tag, device1_name, volume1)
        volume2_tagged = aws_utils.has_control_tag(
            control_tag, device2_name, volume2)

        self.assertTrue(volume1_tagged, 'Volume should have our control tag.')
        self.assertTrue(volume2_tagged, 'Volume should have our control tag.')

        print('Finished test_new_volumes')

    def test_existing_volume(self):

        print('Starting test_existing_volume')

        control_tag = 'existing-volume-sebs'
        device_name = '/dev/xvdh'

        az = aws_utils.get_avaliable_az()

        existing_vol = aws_utils.create_existing_volume(
            control_tag, device_name, az[0])

        self.volume_cleanup.append(existing_vol)

        server_config = self.__class__.default_instance.copy()
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device_name))
        server_config['Placement'] = {
            'AvailabilityZone': az[1]
        }

        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device_name} -n {control_tag} -vvv\n'
            f'while [ ! -e {device_name} ] ; do sleep 1 ; done\n'
        )

        instance = aws_utils.create_instance(server_config)

        self.instance_cleanup.append(instance)

        instance.wait_until_running()
        instance.reload()

        volume_id = aws_utils.get_volume_from_bdm(device_name, instance)

        default_vol = self.ec2.Volume(volume_id)

        self.assertTrue(volume_id, 'Should have the default volume attached')

        waiter = aws_utils.get_ec2_waiter('volume_deleted')
        waiter.wait(VolumeIds=[volume_id])

        instance.reload()

        new_vol_id = aws_utils.get_volume_from_bdm(device_name, instance)

        new_vol = self.ec2.Volume(new_vol_id)
        self.volume_cleanup.append(new_vol)

        self.assertNotEqual(new_vol.id, default_vol.id,
                            'Volume attached now should not be what we started with.')

        volume_tagged = aws_utils.has_control_tag(
            control_tag, device_name, new_vol)

        waiter = aws_utils.get_ec2_waiter('volume_deleted')

        waiter.wait(VolumeIds=[existing_vol.id, default_vol.id])

        self.assertTrue(volume_tagged, 'Volume should have our control tag.')

        print('Finished test_existing_volume')

    def test_existing_volumes(self):

        print('Starting test_existing_volumes')

        control_tag = 'existing-volumes-sebs'
        device1_name = '/dev/xvdh'
        device2_name = '/dev/xvdm'

        az = aws_utils.get_avaliable_az()

        existing_vol1 = aws_utils.create_existing_volume(
            control_tag, device1_name, az[0])

        existing_vol2 = aws_utils.create_existing_volume(
            control_tag, device2_name, az[0])

        self.volume_cleanup.extend([existing_vol1, existing_vol2])

        server_config = self.__class__.default_instance.copy()
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device1_name))
        server_config['BlockDeviceMappings'].append(
            aws_utils.create_block_device(device2_name))
        server_config['Placement'] = {
            'AvailabilityZone': az[1]
        }

        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device1_name} -b {device2_name} -n {control_tag} -vvv\n'
            f'while [ ! -e {device1_name} ] ; do sleep 1 ; done\n'
            f'while [ ! -e {device2_name} ] ; do sleep 1 ; done\n'
        )

        instance = aws_utils.create_instance(server_config)

        self.instance_cleanup.append(instance)

        instance.wait_until_running()
        instance.reload()

        default1_vol_id = aws_utils.get_volume_from_bdm(device1_name, instance)
        default2_vol_id = aws_utils.get_volume_from_bdm(device2_name, instance)

        default_vol1 = self.ec2.Volume(default1_vol_id)
        default_vol2 = self.ec2.Volume(default2_vol_id)

        self.volume_cleanup.extend([default_vol1, default_vol2])

        self.assertTrue(default1_vol_id,
                        'Should have the default volume attached')
        self.assertTrue(default2_vol_id,
                        'Should have the default volume attached')

        waiter = aws_utils.get_ec2_waiter('volume_deleted')
        waiter.wait(VolumeIds=[default1_vol_id])
        waiter.wait(VolumeIds=[default2_vol_id])

        instance.reload()

        new1_vol_id = aws_utils.get_volume_from_bdm(device1_name, instance)
        new2_vol_id = aws_utils.get_volume_from_bdm(device2_name, instance)

        new_vol1 = self.ec2.Volume(new1_vol_id)
        new_vol2 = self.ec2.Volume(new2_vol_id)

        self.volume_cleanup.extend([new_vol1, new_vol2])

        self.assertNotEqual(new_vol1.id, default_vol1.id,
                            'Volume attached now should not be what we started with.')
        self.assertNotEqual(new_vol2.id, default_vol2.id,
                            'Volume attached now should not be what we started with.')

        volume1_tagged = aws_utils.has_control_tag(
            control_tag, device1_name, new_vol1)

        volume2_tagged = aws_utils.has_control_tag(
            control_tag, device2_name, new_vol2)

        waiter = aws_utils.get_ec2_waiter('volume_deleted')

        waiter.wait(VolumeIds=[
                    existing_vol1.id,
                    default_vol1.id,
                    existing_vol2.id,
                    default_vol2.id
                    ])

        self.assertTrue(volume1_tagged, 'Volume should have our control tag.')
        self.assertTrue(volume2_tagged, 'Volume should have our control tag.')

        print('Finished test_existing_volumes')
