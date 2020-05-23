# Stateful Elastic Block Storage (sebs)

Sebs was created for the situation where you need to stick a stateful application in an AutoScaling
group with a max size of 1. Sebs will make sure that if the instance is recreated that the previous
volume is reattached back to the instance regardless of which AZ the instance is recreated in.

## Why

A single instance ASG is good protection in the event that the instance is [retired](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-retirement.html).
It can also help enable rolling upgrades and DR in the event that the AZ your instance is in goes down.

### Prerequisites

* python3
* EC2 Instance Profile with access to create/delete snapshots and volumes.

Example IAM Policy

```JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DetachVolume",
                "ec2:AttachVolume",
                "ec2:DeleteVolume",
                "ec2:DeleteSnapshot",
                "ec2:CreateTags",
                "ec2:CreateSnapshot",
                "ec2:CreateVolume"
            ],
            "Resource": [
                "arn:aws:ec2:*:*:instance/*",
                "arn:aws:ec2:*::snapshot/*",
                "arn:aws:ec2:*:*:volume/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeVolumes",
                "ec2:DescribeSnapshots"
            ],
            "Resource": "*"
        }
    ]
}
```

### Installing

Sebs should be run from an EC2 instance and can be run from userdata or any CaC tool.
Sebs can be installed from pip or GitHub.

From pip

```
pip install sebs
```

From GitHub

```
python3 -m pip install git+https://github.com/DontShaveTheYak/sebs.git#egg=sebs
```

## Usage

```
sebs
usage: sebs [-h] -b BACKUP [-n NAME] [-v] [--version]

optional arguments:
  -h, --help            show this help message and exit
  -b BACKUP, --backup BACKUP
                        <Required> List of Devices to Backup
  -n NAME, --name NAME  <Optional> specify a your app name.
  -v, --verbose         Verbosity (-v, -vv, etc)
  --version             show program's version number and exit
```

Note: If you are going to have more than one instance in a single region use sebs then you need to pass in a name.

```
sebs -b /dev/xvdz -n ${MY_APP_NAME}
```

Here is an example userdata script

```BASH
#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Running Sebs"
yum install python3 -y
python3 -m pip install sebs

# On RHEL and Amazon Linux2 /usr/local/bin is not in the path for root user.
/usr/local/bin/sebs -b /dev/xvdz -n example-app

echo 'Waiting on device /dev/xvdz to be available.'
while [ ! -e /dev/xvdz ] ; do sleep 1 ; done
echo 'Device is ready.'
```

On first run sebs will mark the volume mounted at `/dev/xvdz` with a control tag.
If the instance is re-created sebs will look for a volume with the control tag and
if found it will then mount that volume to the instance as the same device as before.

## Contributing

Please read [CONTRIBUTING.md](./CONTRIBUTING.md).

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available,
see the [tags on this repository](https://github.com/DontShaveTheYak/sebs/tags).

To see what has changed see the [CHANGELOG](./CHANGELOG.md).

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details
