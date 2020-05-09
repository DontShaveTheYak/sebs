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
            ec2 = boto3.resource('ec2')
            instance = ec2.Instance(instance_id)
            # We have to call load to see if we are really connected
            instance.load()
        except:
            t, v, _tb = sys.exc_info()
            print("Unexpected error {}: {}".format(t, v))
            sys.exit(2)

        return instance

    def add_stateful_device(self, device_name):

        sv = StatefulVolume(self.instance.id, device_name, self.volume_tag)

        sv.get_status()

        self.backup.append(sv)

    def tag_stateful_volumes(self):
        # Loop thrugh the volumes and call "tag_volume" on them.
        pass

    def attach_stateful_volumes(self):

        for sv in self.backup:
            # call copy on the volume

            # call attach on the volume
            pass


class StatefulVolume:
    def __init__(self, instance_id, device_name, tag_name):
        self.instance_id = instance_id
        self.device_name = device_name
        self.ready = False
        self.status = 'Unknown'
        self.volume = None
        self.tag_name = tag_name

    def get_status(self):
        client = boto3.client('ec2')
        ec2 = boto3.resource('ec2')

        response = client.describe_volumes(
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

            response = client.describe_volumes(
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

            self.volume = ec2.Volume(volumeId)

        elif len(response['Volumes']) != 1:
            # too many volumes found
            self.status = 'Duplicate'
            # Might have to do other stuffs
        else:
            # Previous backup volume found
            volumeId = response['Volumes'][0]['VolumeId']
            self.status = 'Not Attached'

            self.volume = ec2.Volume(volumeId)
            # Might have to do other stuffs
        return self.status

    def tag_volume(self):
        # If status is 'New' Find the new volume and tag it

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

        # else make a snapshot and get a new device created in the correct AZ
        pass

    def attach(self, instance):
        # if not attached to the current instance then attach it and set the status to attached
        pass
