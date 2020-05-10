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
            if sv.status not in ['Duplicate', 'Missing']:
                sv.tag_volume()

    def attach_stateful_volumes(self):

        for sv in self.backup:
            if sv.status == 'Not Attached':
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
                    {
                        'Name': 'attachment.device',
                        'Values': [
                            self.device_name,
                        ]
                    }
                ]
            )

            if not response['Volumes']:
                print(
                    f"Could not find EBS volume mounted at {self.device_name} for {self.instance_id}")
                self.status = 'Missing'
                return self.status

            volumeId = response['Volumes'][0]['VolumeId']

            print(f'No pre-existing volume for {self.device_name}')
            self.status = 'Attached'
            self.volume = self.ec2_resource.Volume(volumeId)

            self.tag_volume()

        elif len(response['Volumes']) != 1:
            print(
                f"Found duplicate EBS volumes with tag {self.tag_name} for device {self.device_name}")
            self.status = 'Duplicate'
        else:
            volume = response['Volumes'][0]
            volumeId = volume['VolumeId']
            print(f'Found existing Volume {volumeId} for {self.device_name}')
            self.status = 'Not Attached'
            self.volume = self.ec2_resource.Volume(volumeId)

            for attachment in self.volume.attachments:
                if attachment['InstanceId'] == self.instance_id:
                    self.status = 'Attached'

        return self.status

    def tag_volume(self):
        print(
            f'Tagging {self.volume.volume_id} with control tag {self.tag_name}.')

        self.volume.create_tags(Tags=[
            {
                'Key': self.tag_name,
                'Value': self.device_name
            },
        ]
        )

        self.ready = True

    def copy(self, target_az):
        if self.status != 'Not Attached':
            return self.status
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

        # If we fail to create the volume we need to remove this temp snapshot

        response = self.ec2_client.create_volume(
            AvailabilityZone=target_az,
            Encrypted=False if not snapshot.encrypted else snapshot.encrypted,
            SnapshotId=snapshot.snapshot_id,
            VolumeType='' if not self.volume.volume_type else self.volume.volume_type,
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

        waiter.wait(VolumeIds=[self.volume.volume_id])

    def attach(self):
        if self.status != 'Not Attached':
            return self.status

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
                response['Volumes'][0]['VolumeId'])

            prev_volume.detach_from_instance(
                Device=self.device_name,
                InstanceId=self.instance_id
            )

            waiter = self.ec2_client.get_waiter('volume_available')

            waiter.wait(VolumeIds=[prev_volume.volume_id])

            prev_volume.delete()

        self.volume.attach_to_instance(
            Device=self.device_name,
            InstanceId=self.instance_id
        )

        waiter = self.ec2_client.get_waiter('volume_in_use')

        waiter.wait(VolumeIds=[self.volume.volume_id])

        self.status = 'Attached'
