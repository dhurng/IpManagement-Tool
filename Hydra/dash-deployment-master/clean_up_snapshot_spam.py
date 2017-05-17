#!/usr/bin/python
import json
from ucd import cli

snapshots = cli.udcli('getSnapshotsInApplication -application dashDB')
snapshots = json.loads(snapshots)
snapshots = [ x for x in snapshots if x['active']]
my_user = 'dashdbtf (dashdbtf@ca.ibm.com)'
annoying_snapshots = [ x for x in snapshots if x['user'] == my_user]
sorted_annoying_snapshots = sorted(annoying_snapshots, key=lambda snap: snap['created'])
culled = sorted_annoying_snapshots[:-14]
for snap in culled:
    cli.udcli('deleteSnapshot -application dashDB -snapshot %s' % snap['id'])
    print 'Deleted snapshot %s' % snap['name']
