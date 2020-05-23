import os
import time
import json
import boto3
import subprocess


def create_iam_resources():
    print('Creating IAM resources for testing.')
    iam = boto3.resource('iam')

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

    iam_role = iam.create_role(
        RoleName='Sebs',
        AssumeRolePolicyDocument=json.dumps(
            assume_role_policy_doc, indent=2),
        Description='Used for functional testing.',
    )

    role_policy_doc = {'Version': '2012-10-17'}

    role_policy_doc['Statement'] = [
        {
            'Action': [
                "ec2:DetachVolume",
                "ec2:AttachVolume",
                "ec2:DeleteVolume",
                "ec2:DeleteSnapshot",
                "ec2:CreateTags",
                "ec2:CreateSnapshot",
                "ec2:CreateVolume"
            ],
            'Effect': 'Allow',
            'Resource': ["arn:aws:ec2:*:*:instance/*",
                         "arn:aws:ec2:*::snapshot/*",
                         "arn:aws:ec2:*:*:volume/*"]
        },
        {
            'Action': ["ec2:DescribeInstances", "ec2:DescribeVolumes", "ec2:DescribeSnapshots"],
            'Effect': 'Allow',
            'Resource': ["*"]
        }
    ]

    iam_role_policy = iam_role.Policy('Create-Volumes')

    iam_role_policy.put(
        PolicyDocument=json.dumps(role_policy_doc, indent=2)
    )

    instance_profile = iam.create_instance_profile(
        InstanceProfileName='Sebs-EC2-Profile',
    )

    instance_profile.add_role(
        RoleName=iam_role.name
    )
    print('Waiting on instance profile creation.')
    waiter = boto3.client('iam').get_waiter('instance_profile_exists')

    waiter.wait(
        InstanceProfileName=instance_profile.name
    )

    print('IAM resources created.')

    return {
        'role': iam_role,
        'policy': iam_role_policy,
        'profile': instance_profile
    }


def create_default_userdata():

    git_ref = os.getenv('GITHUB_SOURCE_BRANCH')

    if not git_ref:
        git_ref = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        ).strip().decode('ASCII')

    return (
        "#!/bin/bash\n"
        "exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1\n"
        "yum install python3 git -y\n"
        f"python3 -m pip install git+https://github.com/DontShaveTheYak/sebs.git@{git_ref}#egg=sebs --upgrade \n"
        "export AWS_METADATA_SERVICE_NUM_ATTEMPTS=3 \n"
        "export AWS_METADATA_SERVICE_TIMEOUT=2 \n"
    )


def get_latest_ami():
    ec2 = boto3.resource('ec2')
    images = ec2.images.filter(Owners=['amazon'],
                               Filters=[
                                   {'Name': 'name',
                                    'Values': ['amzn2*']
                                    }])

    for image in images:
        ami = image
        break

    return ami.id


def create_block_device(device_name):
    return {
        'DeviceName': device_name,
        'Ebs': {
            'DeleteOnTermination': True,
            'VolumeSize': 10,
            'VolumeType': 'gp2',
            'Encrypted': False
        }
    }


def create_instance(instance_config):
    ec2 = boto3.resource('ec2')
    server_list = ec2.create_instances(**instance_config)

    instance = server_list[0]

    return instance


def get_volume_from_bdm(device_name, instance):
    volume_id = ''
    for device in instance.block_device_mappings:
        if device['DeviceName'] == device_name:
            volume_id = device['Ebs']['VolumeId']
            break

    return volume_id


def get_ec2_waiter(name):
    waiter = boto3.client('ec2').get_waiter(name)
    return waiter


def has_control_tag(control_tag, device_name, volume):

    wait_for_volume_tag(volume)

    tags = [tag for tag in volume.tags if tag['Key']
            == control_tag and tag['Value'] == device_name]

    return bool(tags)


def wait_for_volume_tag(volume):
    i = 0
    tagged = False
    while True:
        i += 1

        volume.reload()

        if volume.tags:
            tagged = True
            break

        time.sleep(30)

        if i > 14:
            break

    if not tagged:
        raise Exception(f'{volume.id} was never tagged.')


def get_default_vpc():
    ec2 = boto3.resource('ec2')

    vpcs = ec2.vpcs.all()

    default_vpc = next(vpc for vpc in vpcs if vpc.is_default)

    return default_vpc


def get_avaliable_az():

    vpc = get_default_vpc()

    az = [subnet.availability_zone for subnet in vpc.subnets.all()]

    return az


def create_existing_volume(control_tag, device_name, az):
    ec2 = boto3.resource('ec2')

    volume = ec2.create_volume(
        AvailabilityZone=az,
        Encrypted=False,
        Size=10,
        VolumeType='gp2',
        TagSpecifications=[
            {
                'ResourceType': 'volume',
                'Tags': [
                    {
                        'Key': control_tag,
                        'Value': device_name
                    }
                ]
            }
        ]
    )

    waiter = get_ec2_waiter('volume_available')

    waiter.wait(VolumeIds=[volume.id])

    return volume
