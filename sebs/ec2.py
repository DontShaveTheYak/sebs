import sys
import boto3
import logging
import requests
from ec2_metadata import ec2_metadata

log = logging.getLogger('sebs')

for name in logging.Logger.manager.loggerDict.keys():
    if ('boto' in name) or ('urllib3' in name):
        logging.getLogger(name).setLevel(logging.WARNING)


class Instance:
    def __init__(self, volume_tag):
        # Create a session so we don't have to keep getting creds.
        self.session = None
        self.instance = self.get_instance()
        self.volume_tag = volume_tag
        self.backup = []

    def get_instance(self):
        log.info('Getting EC2 instance metadata.')
        try:
            instance_id = ec2_metadata.instance_id
            log.info(f'Running on {instance_id}')
        except requests.exceptions.ConnectTimeout:
            log.error(
                'Failled to get instance metadata, are you sure you are running on an EC2 instance?')
            sys.exit(1)
        except:
            t, v, _tb = sys.exc_info()

            sys.exit(1)

        try:
            self.session = boto3.session.Session(
                region_name=ec2_metadata.region)
            ec2 = self.session.resource('ec2')
            instance = ec2.Instance(instance_id)
            # We have to call load to see if we are really connected
            instance.load()
        except:
            t, v, _tb = sys.exc_info()
            log.error(f'Unexpected Error {t}: {v}')
            sys.exit(2)

        return instance

    def add_stateful_device(self, device_name):
        log.info(f'Handling {device_name}')
        sv = StatefulVolume(self.session, self.instance.id,
                            device_name, self.volume_tag)

        sv.get_status()

        self.backup.append(sv)

    def tag_stateful_volumes(self):
        log.info(f'Tagging Volumes with control tag: {self.volume_tag}')
        for sv in self.backup:
            if sv.status not in ['Duplicate', 'Missing']:
                sv.tag_volume()

    def attach_stateful_volumes(self):
        log.info(f'Attaching Volumes to {self.instance.id}')
        for sv in self.backup:
            if sv.status == 'Not Attached':
                sv.copy(ec2_metadata.availability_zone)
                sv.attach()


class StatefulVolume:
    def __init__(self, session, instance_id, device_name, tag_name):
        # Use the existing session so we dont have to keep fetching creds
        self.session = session
        self.instance_id = instance_id
        self.device_name = device_name
        self.ready = False
        self.status = 'Unknown'
        self.volume = None
        self.tag_name = tag_name
        self.ec2_client = self.session.client('ec2')
        self.ec2_resource = self.session.resource('ec2')

    def get_status(self):
        log.info(f'Checking for previous volume of {self.device_name}')
        response = self.ec2_client.describe_volumes(
            Filters=[
                {
                    'Name': f'tag:{self.tag_name}',
                    'Values': [
                        self.device_name,
                    ]
                },
            ]
        )

        log.debug(f'Response of tag search: {response}')

        if not response['Volumes']:
            log.info(f'Did not find a previous volume for {self.device_name}')
            self.status = 'New'
            log.info(
                f'Checking if {self.device_name} is mounted to {self.instance_id}.')

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

            log.debug(f'Reponse of local attachment search: {response}')

            if not response['Volumes']:
                log.error(
                    f"Could not find EBS volume mounted at {self.device_name} for {self.instance_id}")

                self.status = 'Missing'
                return self.status

            volumeId = response['Volumes'][0]['VolumeId']
            log.info(f'No pre-existing volume for {self.device_name}')

            self.status = 'Attached'
            self.volume = self.ec2_resource.Volume(volumeId)
            log.info(f'Current volume is {volumeId} and is {self.status}')
            self.tag_volume()

        elif len(response['Volumes']) != 1:
            vol1 = response['Volumes'][0]['VolumeId']
            vol2 = response['Volumes'][1]['VolumeId']
            log.error(
                f"Found duplicate EBS volumes with tag {self.tag_name}: {vol1} and {vol2}")

            self.status = 'Duplicate'
        else:
            volumeId = response['Volumes'][0]['VolumeId']

            log.info(
                f'Found existing Volume {volumeId} for {self.device_name}')

            self.status = 'Not Attached'
            self.volume = self.ec2_resource.Volume(volumeId)

            for attachment in self.volume.attachments:
                if attachment['InstanceId'] == self.instance_id:
                    self.status = 'Attached'

        return self.status

    def tag_volume(self):
        log.info(
            f'Tagging {self.volume.volume_id} with control tag {self.tag_name}.')

        self.volume.create_tags(Tags=[
            {
                'Key': self.tag_name,
                'Value': self.device_name
            },
        ])

        self.ready = True

    def copy(self, target_az):
        if self.status != 'Not Attached':
            return self.status
        # If the current volume az is in the target AZ do nothing
        if target_az == self.volume.availability_zone:
            return self.status

        log.info(f'Copying {self.volume.volume_id} to {target_az}')

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

        log.debug(f'Snapshot: {snapshot.snapshot_id}')

        # Not sure but we probably have to wait until its completed
        snapshot.wait_until_completed()

        # If we fail to create the volume we need to remove this temp snapshot

        response = self.ec2_client.create_volume(
            AvailabilityZone=target_az,
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

        log.debug(f'New Volume: {response}')

        # This should be the existing volume thats in the wrong AZ
        prev_volume = self.volume

        self.volume = self.ec2_resource.Volume(response['VolumeId'])

        log.info(f'Waiting on volume {self.volume.volume_id} to be avaliable.')

        waiter = self.ec2_client.get_waiter('volume_available')

        waiter.wait(VolumeIds=[self.volume.volume_id])

        # Cleanup this temporary resources
        prev_volume.delete()
        snapshot.delete()

        return self.status

    def attach(self):
        if self.status != 'Not Attached':
            return self.status

        log.info(f'Attaching {self.volume.volume_id} to {self.instance_id}')

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

        log.debug(f'Existing Volume: {response}')

        if response['Volumes']:
            prev_volume = self.ec2_resource.Volume(
                response['Volumes'][0]['VolumeId'])

            log.info(
                f'Detaching curent Volume {prev_volume.volume_id} attached to {self.instance_id}')

            prev_volume.detach_from_instance(
                Device=self.device_name,
                InstanceId=self.instance_id
            )

            waiter = self.ec2_client.get_waiter('volume_available')

            waiter.wait(VolumeIds=[prev_volume.volume_id])

            log.info('Waiting on detachment and then deleting.')

            prev_volume.delete()

        log.info(
            f'Attaching sebs {self.volume.volume_id} to {self.instance_id}')

        self.volume.attach_to_instance(
            Device=self.device_name,
            InstanceId=self.instance_id
        )

        waiter = self.ec2_client.get_waiter('volume_in_use')

        waiter.wait(VolumeIds=[self.volume.volume_id])

        self.status = 'Attached'

        return self.status
