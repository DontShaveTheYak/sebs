import json
import boto3


def create_iam_resources():

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

    role_policy_doc['Statement'] = [{
        'Action': [
            "ec2:*"
        ],
        'Effect': 'Allow',
        'Resource': ["arn:aws:ec2:*:*:volume/*", "*"]
    }]

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

    waiter = boto3.client('iam').get_waiter('instance_profile_exists')

    waiter.wait(
        InstanceProfileName=instance_profile.name
    )

    return {
        'role': iam_role,
        'policy': iam_role_policy,
        'profile': instance_profile
    }
