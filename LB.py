import boto.ec2.elb
import boto.ec2.autoscale
import boto.ec2.cloudwatch
import urllib2
import time
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
from boto.ec2.cloudwatch import MetricAlarm


#ELB
conn = boto.ec2.elb.connect_to_region('us-east-1')


hc = HealthCheck(
        interval=30,
        healthy_threshold=3,
        unhealthy_threshold=5,
        target='HTTP:80/heartbeat?username=mayurs'
    )

zones = ['us-east-1a']
ports = [(80, 80, 'http')]
lb = conn.create_load_balancer('mayursPyLB', zones, ports)
lb.configure_health_check(hc)
lb_name = lb.dns_name

#Security Group

conn = boto.ec2.connect_to_region("us-east-1")

web = conn.create_security_group('mayursPySG', 'My Project 3 Security Group - allows http connections')
web.authorize('tcp', 80, 80, '0.0.0.0/0')

#AUTOSCALE
conn = boto.ec2.autoscale.connect_to_region('us-east-1');

lc = LaunchConfiguration(name='mayursPyLC', image_id='ami-ee16a986',instance_type='m3.medium', security_groups=['mayursPySG'])
conn.create_launch_configuration(lc) ;



ag = AutoScalingGroup(group_name='mayursPyASG', load_balancers=['mayursPyLB'],availability_zones=zones,launch_config=lc, min_size=2, max_size=4, desired_capacity=2, connection=conn)
conn.create_auto_scaling_group(ag);

scale_up_policy = ScalingPolicy(
            name='mayursPy_scale_up', adjustment_type='ChangeInCapacity',
            as_name='mayursPyASG', scaling_adjustment=2, cooldown=240)

scale_down_policy = ScalingPolicy(
            name='mayursPy_scale_down', adjustment_type='ChangeInCapacity',
            as_name='mayursPyASG', scaling_adjustment=-1, cooldown=120)


conn.create_scaling_policy(scale_up_policy)
conn.create_scaling_policy(scale_down_policy)

#Get Amazon Resource Name (ARN) of each policy,
scale_up_policy = conn.get_all_policies(
            as_group='mayursPyASG', policy_names=['mayursPy_scale_up'])[0]
scale_down_policy = conn.get_all_policies(
            as_group='mayursPyASG', policy_names=['mayursPy_scale_down'])[0]

#Cloudwatch to set up alarms
cloudwatch = boto.ec2.cloudwatch.connect_to_region('us-east-1')

#Alarm would be over whole autoscaling group
alarm_dimensions = {"AutoScalingGroupName": 'mayursPyASG'}

scale_up_alarm = MetricAlarm(
            name='mayursPy_scale_up_on_network', namespace='AWS/EC2',
            metric='NetworkIn', statistic='Average',
	        comparison='>', threshold='1000000',
            period='60', evaluation_periods=1,
            alarm_actions=[scale_up_policy.policy_arn],
            dimensions=alarm_dimensions)

cloudwatch.create_alarm(scale_up_alarm)

scale_down_alarm = MetricAlarm(
            name='mayursPy_scale_down_on_cpu', namespace='AWS/EC2',
            metric='NetworkIn', statistic='Average',
            comparison='<', threshold='20000000',
            period='60', evaluation_periods=2,
            alarm_actions=[scale_down_policy.policy_arn],
            dimensions=alarm_dimensions)

cloudwatch.create_alarm(scale_down_alarm)

#####################	LOAD GENERATOR    ########################
print "Waiting 120 sec."
time.sleep(120);
print "Done. Starting Load Generation Instance Creation."


conn = boto.ec2.connect_to_region("us-east-1")

mayursPy_reservation = conn.run_instances(
        'ami-dc5cefb4',
        instance_type='m3.medium',
        security_groups=['mayursPySG'])
print "Waiting 90 sec."
time.sleep(90);
print "Done. Fetching load generator instance."

reservations = conn.get_all_reservations()

for res in reservations:
	if res.id == mayursPy_reservation.id:
		mayursPy_reservation = res;

instances = mayursPy_reservation.instances
load_generator = instances[0];
load_generator_dns_name = load_generator.public_dns_name
print load_generator_dns_name
print "Waiting 90 sec."
time.sleep(90);
print "Done.Setting userid."


urllib2.urlopen("http://"+load_generator_dns_name+"/username?username=mayurs")

print "Waiting 10 sec."
time.sleep(10);
print "Done. Commencing Warmup - 2 Rounds"

for x in range(1,3):
	print "Warmup - "+str(x)
	urllib2.urlopen("http://"+load_generator_dns_name+"/warmup?dns="+lb_name+"&testId=warmupMayursPy"+str(x))
	print "Going for sleep of 5 mins."
	time.sleep(330)
	print "Done."

print "Going for Run"
urllib2.urlopen("http://"+load_generator_dns_name+"/run?dns="+lb_name+"&testId=runMayursPy")
print "Going for sleep of 100 mins."
time.sleep(6060)
print "Done."




#####################	FREEING EVERYTHING    ########################
print "Deleting AutoScalingGroup and LaunchConfiguration ..."
ag.shutdown_instances()
ag.delete()
lc.delete()
name = raw_input("Press any key to terminate ELB and Load Balancer ... ")
lb.delete()
load_generator.terminate()
print "Finished."




