import sys
import boto3
import requests
from ec2_metadata import ec2_metadata


class Instance:
    def __init__(self, volume_tag):
        self.instance = self.get_instance()
        self.volume_tag = volume_tag
        self.backup = []

    def get_instance(self):

        try:
            instance_id = ec2_metadata.instance_id
        except requests.exceptions.ConnectTimeout:
            print(
                'Failled to get instance metadata, are you sure you are running on an EC2 instance?')
            sys.exit(1)
        except:
            t, v, _tb = sys.exc_info()
            print("Unexpected error {}: {}".format(t, v))
            sys.exit(1)

        try:
            ec2 = boto3.resource('ec2', region_name=ec2_metadata.region)
            instance = ec2.Instance(instance_id)
            # We have to call load to see if we are really connected
            instance.load()
        except:
            t, v, _tb = sys.exc_info()
            print("Unexpected error {}: {}".format(t, v))
            sys.exit(2)

        return instance

    def add_stateful_device(self, device_name):
        print(f'Handling {device_name}')
        sv = StatefulVolume(self.instance.id, device_name, self.volume_tag)

        sv.get_status()

        self.backup.append(sv)

    def tag_stateful_volumes(self):

        for sv in self.backup:
            sv.tag_volume()

    def attach_stateful_volumes(self):

        for sv in self.backup:
            sv.copy(ec2_metadata.availability_zone)
            sv.attach()


class StatefulVolume:
    def __init__(self, instance_id, device_name, tag_name):
        self.instance_id = instance_id
        self.device_name = device_name
        self.ready = False
        self.status = 'Unknown'
        self.volume = None
        self.tag_name = tag_name
        self.ec2_client = boto3.client('ec2', region_name=ec2_metadata.region)
        self.ec2_resource = boto3.resource(
            'ec2', region_name=ec2_metadata.region)

    def get_status(self):

        response = self.ec2_client.describe_volumes(
            Filters=[
                {
                    'Name': 'tag:{}'.format(self.tag_name),
                    'Values': [
                        self.device_name,
                    ]
                },
            ]
        )

        if not response['Volumes']:
            # No previous volume found
            self.status = 'New'

            response = self.ec2_client.describe_volumes(
                Filters=[
                    {
                        'Name': 'attachment.instance-id',
                        'Values': [
                            self.instance_id,
                        ]
                    },
                ]
            )

            if not response['Volumes']:
                print(
                    f"Could not find {self.device_name} for {self.instance_id}")
                sys.exit(2)

            volumeId = response['Volumes'][0]['VolumeId']

            self.volume = self.ec2_resource.Volume(volumeId)

        elif len(response['Volumes']) != 1:
            # too many volumes found
            self.status = 'Duplicate'
            # Might have to do other stuffs
        else:
            # Previous backup volume found
            volumeId = response['Volumes'][0]['VolumeId']
            self.status = 'Not Attached'

            self.volume = self.ec2_resource.Volume(volumeId)
            # Might have to do other stuffs

        print(f'{self.device_name} is {self.status}')
        return self.status

    def tag_volume(self):
        print(f'Tagging {self.volume.volume_id} with control tag.')
        if self.status != 'New':
            return self.status

        self.volume.create_tags(Tags=[
            {
                'Key': self.tag_name,
                'Value': self.device_name
            },
        ]
        )

    def copy(self, target_az):
        # If the current volume az is in the target AZ do nothing
        if target_az == self.volume.availability_zone:
            return

        print(f'Copying {self.volume.volume_id} to {target_az}')

        snapshot = self.volume.create_snapshot(
            Description='Intermediate snapshot for SEBS.',
            TagSpecifications=[
                {
                    'ResourceType': 'snapshot',
                    'Tags': [
                        {
                            'Key': self.tag_name,
                            'Value': self.device_name
                        },
                    ]
                },
            ]
        )

        # Not sure but we probably have to wait until its completed
        snapshot.wait_until_completed()

        response = self.ec2_client.create_volume(
            AvailabilityZone=target_az,
            Encrypted=snapshot.encrypted,
            Iops=self.volume.iops,
            KmsKeyId=self.volume.kms_key_id,
            OutpostArn=self.volume.outpost_arn,
            Size=self.volume.size,
            SnapshotId=snapshot.snapshot_id,
            VolumeType=self.volume.volume_type,
            TagSpecifications=[
                {
                    'ResourceType': 'volume',
                    'Tags': [
                        {
                            'Key': self.tag_name,
                            'Value': self.device_name,
                        },
                    ]
                },
            ]
        )

        # Cleanup this temporary snapshot
        snapshot.delete()

        self.volume = self.ec2_resource.Volume(response['VolumeId'])

        waiter = self.ec2_client.get_waiter('volume_available')

        waiter.wait(self.volume.volume_id)

    def attach(self):
        print(f'Attaching {self.volume.volume_id} to {self.instance_id}')
        # Need to find and delete any current volumes
        response = self.ec2_client.describe_volumes(
            Filters=[
                {
                    'Name': 'attachment.instance-id',
                    'Values': [
                        self.instance_id,
                    ]
                },
                {
                    'Name': 'attachment.device',
                    'Values': [
                        self.device_name,
                    ]
                },
            ]
        )

        if response['Volumes']:
            prev_volume = self.ec2_resource.Volume(
                response['Volumes']['VolumeId'])

            pre_volume.detach_from_instance(
                Device=self.device_name,
                InstanceId=self.instance_id
            )

            waiter = self.ec2_client.get_waiter('volume_available')

            waiter.wait(prev_volume.volume_id)

            prev_volume.delete()

        self.volume.attach_to_instance(
            Device=self.device_name,
            InstanceId=self.instance_id
        )

        waiter = self.ec2_client.get_waiter('volume_in_use')

        waiter.wait(self.volume.volume_id)
