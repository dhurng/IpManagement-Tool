# dash-deployment
A collection of tools for dashDB deployment automation

## setup_deployment_environment.py
For setting up new deployment environments
```
usage: setup_deployment_environment.py [-h] [-d DOMAIN]
                                       [--oauth2url OAUTH2URL]
                                       [--swiftendpoint SWIFTENDPOINT]
                                       [--dc DC] [--sslprocess SSLPROCESS]
                                       [-b BROKER] [-z BROKERAUTH]
                                       [--monregion MONREGION]
                                       [--logregion LOGREGION]
                                       [--backuptime BACKUPTIME]
                                       [--etcdpw ETCDPW] [--etcd1 ETCD1]
                                       [--etcd2 ETCD2]
                                       name parent id key token relay callback
                                       {dedicated,pcni,rollup,hipaa,us-fed,aws-prod}
                                       ...

A helper script to provision deployment environments in UCD

positional arguments:
  name                  Name of the deployment environment. No spaces
  parent                Name of the parent deployment environment (where this
                        is being run from).
  id                    Provisioning ID (Softlayer ID or AWS Access Key) for
                        new Deployment Environment
  key                   Provisioning Key (Softlayer API Key or AWS Secret
                        Access Key) for new Deployment Environment
  token                 UCD Access Token
  relay                 UCD Relay Zone
  callback              Process ID for logging purposes

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Domain name
  --oauth2url OAUTH2URL
                        OAUTH2 Discovery URL for bluemix SSO
  --swiftendpoint SWIFTENDPOINT
                        Swift backup endpoint (for Softlayer backups)
  --dc DC               Softlayer DataCenter. For AWS use the closest
                        geographical analog
  --sslprocess SSLPROCESS
                        SSL deploy process (if different from parent copying
                        from)
  -b BROKER, --broker BROKER
                        Service broker endpoint (should end in /providers)
  -z BROKERAUTH, --brokerauth BROKERAUTH
                        Service broker authroizeation Key
  --monregion MONREGION
                        Monitoring Region
  --logregion LOGREGION
                        Logging Region
  --backuptime BACKUPTIME
                        Backup time (for Softlayer)
  --etcdpw ETCDPW       etcd password for HA Txn plans
  --etcd1 ETCD1         etcd endpoint1 for HA Txn plans
  --etcd2 ETCD2         etcd endpoint2 for HA Txn plans

Type:
  New environment type

  {dedicated,pcni,rollup,hipaa,us-fed,aws-prod}
                        Newly created deployment environment type
    dedicated           New Bluemix Dedicated environment
    pcni                New PCNI environment
    rollup              New Rollup environment
    hipaa               New HIPAA ready environment
    us-fed              New US-Fed environment
    aws-prod            New AWS production environment
```
For Production AWS Environments:
```
usage: setup_deployment_environment.py name parent id key token relay callback aws-prod
       [-h] [-p]
       ami guardami availabilityzone subnet securitygroup [securitygroup ...]

positional arguments:
  ami               ID of the dashDB base AMI in the new availability zone
  guardami          ID of the guardium base AMI in the new availability zone
  region            Where is this new deployment environment
  subnet            Default subnet for new deployment environment
  securitygroup     The VPCs security groups. Be sure to list the APSM
                    security group first.

optional arguments:
  -h, --help        show this help message and exit
  -p, --public      Use the public IP for prepping the host (testing purposes
                    only)
```
