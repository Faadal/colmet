import os
import re
import errno
import struct
import copy

from colmet.metrics.taskstats_default import get_taskstats_class
from colmet.exceptions import NoEnoughPrivilegeError, JobNeedToBeDefinedError, OnlyOneJobIsSupportedError
from colmet.backends.base import InputBaseBackend
from colmet.job import Job

Counters = get_taskstats_class()

def get_input_backend_class():
    return TaskStatsNodeBackend

class TaskStatsNodeBackend(InputBaseBackend):
    def __init__(self, options):
        InputBaseBackend.__init__(self,options)
        self.options = options
        self.jobs = {}

        self.taskstats_nl = TaskStatsNetlink(options)
 
        #print "yop:" ,self.options.cpuset_rootpath
        #print "poy:" ,self.options.regex_job_id
        
        if (len(self.job_id_list) < 1) and (self.options.cpuset_rootpath =='') :
            raise JobNeedToBeDefinedError()
        if len(self.job_id_list) == 1:
            job_id = self.job_id_list[0]
            self.jobs[job_id] = Job(self, job_id, options) #get all options
        else:
            for i, job_id in enumerate(self.job_id_list):
                #j_options = OptionJob(["yop","yop"]) #TODO need to distinct options per job
                j_options = options
                self.jobs[job_id] = Job(self,job_id,j_options)
    
    @classmethod
    def _get_backend_name(cls):
        return "taskstats"

    def build_request(self, pid):
        return self.taskstats_nl.build_request(pid)
    
    def get_task_stats(self, request):
        counters = self.taskstats_nl.get_single_task_stats(request)
        return counters

    def pull(self):
        for job in self.jobs.values():
            job.update_stats()
        return [job.get_stats() for job in self.jobs.values()]

    def get_counters_class(self):
        return Counters
    
    def create_options_job_cgroups(self, cgroups):
        #options are duplicated to allow modification per jobs, here cgroups parametter
        options = copy.copy(self.options) 
        options.cgroups = cgroups
        return options

    def update_job_list(self):
        """Used to maintained job list upto date by adding new jobs and removing ones 
        to monitor accordingly to cpuset_rootpath and regex_job_id.
        """
         
        cpuset_rootpath = self.options.cpuset_rootpath[0]
        regex_job_id    = self.options.regex_job_id[0]

        #print "yop:" ,self.options.cpuset_rootpath
        #print "poy:" ,self.options.regex_job_id

        job_ids = set([])
        filenames = {}
        for filename in os.listdir(cpuset_rootpath):
            jid = re.findall(regex_job_id, filename)
            if len(jid)>0:
                job_ids.add(jid[0])
                filenames[jid[0]] = filename

        print "Ids of jobs to monitor: ", job_ids
        monitored_job_ids =  set(self.job_id_list)
        #Add new jobs
        for job_id in (job_ids - monitored_job_ids):
            self.jobs[job_id] = Job(self, job_id, self.create_options_job_cgroups([cpuset_rootpath+"/"+filenames[job_id]])) 
        #Del ended jobs
        for job_id in (monitored_job_ids-job_ids):
            del self.jobs[job_id]

#
# Taskstats Netlink
# 

from genetlink.netlink import Connection, NETLINK_GENERIC, U32Attr, NLM_F_REQUEST
from genetlink.genetlink import Controller, GeNlMessage

TASKSTATS_CMD_GET = 1

TASKSTATS_CMD_ATTR_PID = 1
TASKSTATS_CMD_ATTR_TGID = 2

TASKSTATS_TYPE_PID = 1
TASKSTATS_TYPE_TGID = 2
TASKSTATS_TYPE_STATS = 3
TASKSTATS_TYPE_AGGR_PID = 4
TASKSTATS_TYPE_AGGR_TGID = 5


class TaskStatsNetlink(object):
    # Keep in sync with format_stats() and pinfo.did_some_io()

    def __init__(self, options):
        self.options = options
        self.connection = Connection(NETLINK_GENERIC)
        controller = Controller(self.connection)
        self.family_id = controller.get_family_id('TASKSTATS')

    def build_request(self, tid):
        return GeNlMessage(self.family_id, cmd=TASKSTATS_CMD_GET,
                           attrs=[U32Attr(TASKSTATS_CMD_ATTR_PID, tid)],
                           flags=NLM_F_REQUEST)

    def get_single_task_stats(self, request):
        request.send(self.connection)
        try:
            reply = GeNlMessage.recv(self.connection)
        except OSError, e:
            if e.errno == errno.ESRCH:
                # OSError: Netlink error: No such process (3)
                return
            if e.errno == errno.EPERM:
                raise NoEnoughPrivilegeError
            raise
        for attr_type, attr_value in reply.attrs.iteritems():
            if attr_type == TASKSTATS_TYPE_AGGR_PID:
                reply = attr_value.nested()
                break
            #elif attr_type == TASKSTATS_TYPE_PID:
            #    pass
        else:
            return
        taskstats_data = reply[TASKSTATS_TYPE_STATS].data
        if len(taskstats_data) < 272:
            # Short reply
            return
        taskstats_version = struct.unpack('H', taskstats_data[:2])[0]
        assert taskstats_version == 4
        return Counters(taskstats_buffer = taskstats_data)


