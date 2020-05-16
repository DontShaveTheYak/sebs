import json
import boto3
import time
import unittest
import warnings
import subprocess


class TestSebs(unittest.TestCase):

    def setUp(self):

        warnings.filterwarnings(
            "ignore", category=ResourceWarning, message="unclosed.*<ssl.SSLSocket.*>")

        self.volume_cleanup = []
        self.instance_cleanup = []

        self.ec2 = boto3.resource('ec2')

        self.iam = boto3.resource('iam')

        assume_role_policy_doc = {'Version': '2012-10-17'}

        assume_role_policy_doc['Statement'] = [{
            'Action': [
                "sts:AssumeRole"
            ],
            'Effect': 'Allow',
            'Principal': {
                'Service': ["ec2.amazonaws.com"]
            }
        }]

        self.iam_role = self.iam.create_role(
            RoleName='Sebs',
            AssumeRolePolicyDocument=json.dumps(
                assume_role_policy_doc, indent=2),
            Description='Used for functional testing.',
        )

        role_policy_doc = {'Version': '2012-10-17'}

        role_policy_doc['Statement'] = [{
            'Action': [
                "ec2:*"
            ],
            'Effect': 'Allow',
            'Resource': ["arn:aws:ec2:*:*:volume/*", "*"]
        }]

        self.iam_role_policy = self.iam_role.Policy('Create-Volumes')

        self.iam_role_policy.put(
            PolicyDocument=json.dumps(role_policy_doc, indent=2)
        )

        self.instance_profile = self.iam.create_instance_profile(
            InstanceProfileName='Sebs-EC2-Profile',
        )

        self.instance_profile.add_role(
            RoleName=self.iam_role.name
        )

        waiter = boto3.client('iam').get_waiter('instance_profile_exists')

        waiter.wait(
            InstanceProfileName=self.instance_profile.name
        )

        self.git_ref = subprocess.check_output(
            ["git", "rev-parse", "HEAD"]).strip().decode('ASCII')

        self.default_user_data = (
            "#!/bin/bash\n"
            "exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1\n"
            "yum install python3 git -y\n"
            f"python3 -m pip install git+https://github.com/DontShaveTheYak/sebs.git@{self.git_ref}#egg=sebs-test --upgrade \n"
        )

        images = self.ec2.images.filter(Owners=['amazon'], Filters=[{'Name': 'name',
                                                                     'Values': ['amzn2*']
                                                                     }])

        for image in images:
            ami = image
            break

        self.default_instance = dict(BlockDeviceMappings=[],
                                     ImageId=ami.id,
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
        server_config['BlockDeviceMappings'].append({
            'DeviceName': device_name,
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': 10,
                'VolumeType': 'gp2',
                'Encrypted': False
            }
        })

        server_config['UserData'] += (
            f'/usr/local/bin/sebs -b {device_name}\n'
            f'while [ ! -e {device_name} ] ; do sleep 1 ; done\n'
        )

        server_list = self.ec2.create_instances(**server_config)

        instance = server_list[0]

        self.instance_cleanup.append(instance)

        instance.wait_until_running()
        instance.reload()

        for device in instance.block_device_mappings:
            if device['DeviceName'] == device_name:
                volume_id = device['Ebs']['VolumeId']
                break

        print(volume_id)

        waiter = boto3.client('ec2').get_waiter('volume_in_use')

        waiter.wait(VolumeIds=[volume_id])

        volume = self.ec2.Volume(volume_id)

        # Need to add a customer waiting to look for tag creation.
        time.sleep(120)
        volume.reload()
        print(volume.tags)

        for tag in volume.tags:
            if tag['Key'] == 'sebs' or tag['Value'] == device_name:
                tag_name = tag['Key']
                tag_value = tag['Value']
            break

        self.assertEqual(tag_name, 'sebs',
                         'Volume should be tagged with our control tag.')
        self.assertEqual(tag_value, device_name,
                         "Tag value should be it's device name.")
