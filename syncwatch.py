#!/usr/bin/python3

# -*- coding: utf-8 -*-
#########################################################
# SERVICE : SyncWatch.py                                #
#           Service to synchronize 2 locations          #
#           on file or folder change                    #
#           I. Helwegen 2019                            #
#########################################################

####################### GLOBALS #########################
VERSION      = "0.83"
XML_FILENAME = "syncwatch.xml"
LOG_FILENAME = "syncwatch.log"
SYNC_TOOL    = "rsync"
LOG_MAXSIZE  = 100*1024*1024
DEF_DELAY    = 10
SYNC_WAIT    = 1
RETRY_DELAY  = 10

####################### IMPORTS #########################
import sys
import os
import signal
import xml.etree.ElementTree as ET
from getopt import getopt, GetoptError
import logging
import logging.handlers
import locale
from time import sleep
from threading import Thread, Timer, Lock, Event
from subprocess import run, PIPE, DEVNULL
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except:
    try:
        import pip
        try:
            package="watchdog"
            if hasattr(pip, 'main'):
                pip.main(['install', package])
            else:
                pip._internal.main(['install', package])
        except:
            print("SyncWatch file and folder synchronization")
            print("Version: " + VERSION)
            print(" ")
            print("Unable to install required packages")
            print("watchdog not installed")
            exit(1)
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except:
        print("SyncWatch file and folder synchronization")
        print("Version: " + VERSION)
        print(" ")
        print("Pip not installed, please install pip to continue")
        print("SyncWatch is not able to install the required packages")
        exit(1)

#########################################################
# Class : Common                                        #
#########################################################
class Common(object):
    @classmethod
    def checkkey(cls, mydict, key):
        if key in mydict:
            retval = mydict[key]
        else:
            retval = None
        return retval
    
    @classmethod
    def gettype(cls, text):
        try:
            retval = int(text)
        except:
            try:
                retval = float(text)
            except:
                if text:
                    if text.lower() == "false":
                        retval = False
                    elif text.lower() == "true":
                        retval = True
                    else:
                        retval = text
                else:
                    retval = None
                        
        return retval
    
    @classmethod
    def which(cls, progr):
        retval = None
        try: 
            result = run(['which', progr], stdout=PIPE, stderr=DEVNULL)
            if result.returncode == 0:
                retval = result.stdout.decode("utf-8").strip()
            else:
                retval = None
        except: 
            retval = None
        return retval

#########################################################
# Class : SyncTimer                                     #
#########################################################
class SyncTimer(object):
    def __init__(self, delay, resettimer, callback):
        self.delay=delay
        self.resettimer=resettimer
        self.callback=callback
        self.timer = None
        self.timerBusy = Event()
        self.timerBusy.clear()
        self.mutex = Lock()
    
    def __del__(self):
        self.mutex.acquire()
        if self.timerBusy and self.timer:
            self.timer.cancel()
        self.mutex.release()
        del self.timerBusy
        del self.mutex
        del self.timer
    
    def start(self):
        self.mutex.acquire()
        if self.timerBusy.isSet() and self.timer:
            if self.resettimer:
                self.timer.cancel()
                self.timer = None
                self.timerBusy.clear()
        if not self.timerBusy.isSet() and not self.timer:
            self.timer = Timer(self.delay, self.callback)
            self.timer.start()
            self.timerBusy.set()
        self.mutex.release()
    
    def clear(self):
        self.mutex.acquire()
        if self.timerBusy.isSet() and self.timer:
            self.timer.cancel()
            self.timer = None
        self.timerBusy.clear()
        self.mutex.release()

#########################################################
# Class : rsyncThread                                   #
#########################################################        
class rsyncThread(Thread):
    def __init__(self, logger, sync, callback):
        self.sync=sync
        self.logger=logger
        self.callback=callback
        Thread.__init__(self)
        self.setDaemon(False)
        
    def __del__(self):
        pass
    
    def run(self):
        opts=self._rsyncbuildopts()
        result = run(opts, stdout=PIPE, stderr=PIPE)
        if result.returncode == 0:
            if result.stdout.decode("utf-8").strip():
                self.logger.info("{}: Output:\n{}".format(self.sync['name'],result.stdout.decode("utf-8").strip()))
        else:
            self.logger.error("{}: Error during syncing: {}".format(self.sync['name'],result.returncode))
            if result.stdout.decode("utf-8").strip():
                self.logger.info("{}: Output:\n{}".format(self.sync['name'],result.stdout.decode("utf-8").strip()))
            if result.stderr.decode("utf-8").strip():
                self.logger.info("{}: Error:\n{}".format(self.sync['name'],result.stderr.decode("utf-8").strip()))
        self.callback()
        
    def _rsyncbuildopts(self):
        if not Common.checkkey(self.sync,'source') or not Common.checkkey(self.sync,'destination'):
            return None
        params=[]
        params.append(Common.which(SYNC_TOOL))
        opt="-Pa"
        
        if Common.checkkey(self.sync,'compress'):
            opt=opt+"z"
        if Common.checkkey(self.sync,'update'):
            opt=opt+"u"
        params.append(opt)
        if Common.checkkey(self.sync,'delete'):
            params.append("--delete")
        if Common.checkkey(self.sync,'exclude'):
            excludes=self.sync['exclude'].split(',')
            for exclude in excludes:
                params.append("--exclude={}".format(exclude.strip()))
        if Common.checkkey(self.sync,'include'):
            includes=self.sync['include'].split(',')
            for include in includes:
                params.append("--include={}".format(include.strip()))
        if Common.checkkey(self.sync,'options'):
            options=self.sync['options'].split(',')
            for option in options:
                params.append("{}".format(option.strip()))
        params.append(os.path.join(self.sync['source'],''))
        params.append(os.path.normpath(self.sync['destination']))      
        
        return params

#########################################################
# Class : rsync                                         #
#########################################################
class rsync(object): 
    def __init__(self, logger, sync):
        self.sync=sync
        self.logger=logger
        self.syncThread=None
        self.waitsync=Event()
        self.waitsync.clear()
        self.sync['1'].set()
    
    def __del__(self):
        if self.syncThread:
            self.syncThread.join()
        del self.waitsync
        del self.sync['1']
        
    def __call__(self):
        if self.syncThread:
            if self.syncThread.isAlive():
                self.waitsync.set()
                return
        self._startSync()
        return
    
    def _startSync(self):
        self.sync['1'].clear()
        self.logger.info("{}: Synchronization started".format(self.sync['name']))
        self.syncThread = rsyncThread(self.logger, self.sync, self._Callback)
        self.syncThread.start()
        
    def _Callback(self):
        self.logger.info("{}: Synchronization finished".format(self.sync['name']))
        if self.waitsync.isSet():
            self._startSync()
            self.waitsync.clear()
        # wait for synchronization with events in list
        sleep(SYNC_WAIT)
        self.sync['1'].set()
        self.sync['list1'].clear()
    
#########################################################
# Class : SyncHandler                                   #
#########################################################
class SyncHandler(FileSystemEventHandler):
    def __init__(self, logger, sync):
        self.sync = sync
        self.logger = logger
        self.logger.info("{}: Starting watch".format(self.sync['name']))
        if not Common.checkkey(sync,'delay'):
            self.logger.info("{}: No sync delay set with <delay>, default to {} seconds".format(self.sync['name'],DEF_DELAY))
            sync['delay']=DEF_DELAY
        self.rsync=rsync(logger, sync)
        self.timer=SyncTimer(sync['delay'], sync['resettimer'], self.onTimer)
        if Common.checkkey(sync,'initsync'):
            self.on_any_event(None)

    def __del__(self):
        self.logger.info("{}: Stopping watch".format(self.sync['name']))
        del self.timer
        del self.rsync
        
    def on_any_event(self, event):
        if not event:
            self.logger.info("{}: Execute initial sync".format(self.sync['name']))
            self.timer.start()
        else:
            exec = True
            if self.sync['2']:
                if not self.sync['2'].isSet():
                    exec=self.doIgnoreFromList(event)
            if exec:
                self.addToList(event)
                self.logger.info("{}: {} event detected on {}".format(self.sync['name'], event.event_type, event.src_path))
                self.timer.start()
        
    def addToList(self, event):
        li = {"type":event.event_type, "dir":event.is_directory, "path":event.src_path}
        if li not in self.sync['list1']:
            self.sync['list1'].append(li)
    
    def doIgnoreFromList(self, event):
        exec = True
        
        if event.is_directory:
            if os.path.normpath(event.src_path) == os.path.normpath(self.sync["source"]):
                exec = False
            else:
                for li in self.sync['list2']:
                    if li["dir"]:
                        if self._checkPath(event.src_path, li["path"], False):
                            exec=False
        else: 
            for li in self.sync['list2']:
                if not li["dir"]:
                    if self._checkPath(event.src_path, li["path"]):
                        #if path if true then check file or temp based file
                        if self._checkFile(event.src_path, li["path"]):
                            exec=False
        return exec
    
    def _checkPath(self, src_path, dest_path, psplit = True):
        if psplit:
            p1 = os.path.split(src_path)
            p2 = os.path.split(dest_path)
        else:
            p1 = (os.path.normpath(src_path),"")
            p2 = (os.path.normpath(dest_path),"")
        p1=p1 + (self._getPathPart(p1[0],self.sync["source"]),)
        p2=p2 + (self._getPathPart(p2[0],self.sync["destination"]),)
        return p1[2] == p2[2]
    
    def _getPathPart(self, src_path, cmp_path):
        new_path = ""
        if src_path.startswith(os.path.normpath(cmp_path)):
            new_path=src_path.replace(os.path.normpath(cmp_path),"")
        return new_path
    
    def _checkFile(self, src_path, dest_path):
        same = False
        p1 = os.path.split(src_path)
        p2 = os.path.split(dest_path)

        if p1[1] == p2[1]:
            same = True
        elif p1[1].find("."+p2[1]+'.') == 0:
            same = True
        return same
        
    def onTimer(self):
        self.timer.clear()
        if self.sync['2']:
            if not self.sync['2'].isSet():
                self.logger.info("{}: Waiting on reverse action to finish".format(self.sync['name']))
                self.sync['2'].wait()
        self.rsync()
        
#########################################################
# Class : SyncWatch                                     #
#########################################################
class SyncWatch(object):
    def __init__(self):
        self.syncs = []
        signal.signal(signal.SIGINT, self.exit_app)
        signal.signal(signal.SIGTERM, self.exit_app)
        self.exitevent = Event()
        self.exitevent.clear()
        self.logger = logging.getLogger('syncwatch')
        self.logger.setLevel(logging.INFO)
        # create file handler which logs even debug messages
        fh = logging.handlers.RotatingFileHandler(self.GetLogger(), maxBytes=LOG_MAXSIZE, backupCount=5)
        # create console handler with a higher log level
        ch = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        logging.captureWarnings(True)
        tmformat=("{} {}".format(locale.nl_langinfo(locale.D_FMT),locale.nl_langinfo(locale.T_FMT)))
        tmformat=tmformat.replace("%y", "%Y")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s', tmformat)
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

    def __del__(self):
        del self.syncs
        logging.shutdown()

    def run(self, argv):
        self.parseopts(argv)
        self.GetXML()
        
        if not Common.which(SYNC_TOOL):
            self.logger.error("{} not found, please install {} before running this program".format(SYNC_TOOL, SYNC_TOOL))
            exit(1)
        
        self.logger.info("Starting SyncWatch")
        retries = []
               
        for sync in self.syncs:
            if Common.checkkey(sync,'source') and Common.checkkey(sync,'destination'):
                if os.path.isdir(sync['source']) and os.path.isdir(sync['destination']):
                    event_handler = SyncHandler(self.logger, sync)
                    sync['observer'] = Observer()
                    sync['observer'].schedule(event_handler, path=sync['source'], recursive=True)
                    sync['observer'].start()
                else:
                    if Common.checkkey(sync,'retry'):
                        self.logger.info("Source or destination path doesn't exist for {}, keep on retrying".format(sync['name']))
                        retries.append(sync)
                    else:        
                        self.logger.error("Source or destination path doesn't exist for {}, watch not created".format(sync['name']))
                    
            else:
                self.logger.error("Source or destination path error for {}, watch not created".format(sync['name']))
        
        retrycnt = 0
        while (len(retries)>0) and not self.exitevent.isSet():
            sleep(1)
            if retrycnt < RETRY_DELAY-1:
                retrycnt += 1
            else:
                retrycnt = 0

                for sync in retries:
                    if os.path.isdir(sync['source']) and os.path.isdir(sync['destination']):
                        event_handler = SyncHandler(self.logger, sync)
                        sync['observer'] = Observer()
                        sync['observer'].schedule(event_handler, path=sync['source'], recursive=True)
                        sync['observer'].start()
                        retries.remove(sync)
                        self.logger.info("Source or destination path came online for {}".format(sync['name']))
        
        if not self.exitevent.isSet():
            signal.pause()
        
        for sync in self.syncs:
            if Common.checkkey(sync,'observer'):
                sync['observer'].stop()
                sync['observer'].join()
        
        self.logger.info("SyncWatch Ready")

    def parseopts(self, argv):
        self.title()
        try:
            opts, args = getopt(argv,"hv",["help","version"])
        except GetoptError:
            print("Enter 'SyncWatch -h' for help")
            exit(2)
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                print("Usage:")
                print("         SyncWatch <args>")
                print("         -h, --help   : this help file")
                print("         -v, --version: print version information")
                print("         <no argument>: run as daemon")
                exit()
            elif opt in ("-v", "--version"):
                print("Version: " + VERSION)
                exit()
        
    def GetXML(self):
        etcpath = "/etc/"
        XMLpath = ""
        # first look in etc
        if os.path.isfile(os.path.join(etcpath,XML_FILENAME)):
            XMLpath = os.path.join(etcpath,XML_FILENAME)
        else:
            # then look in home folder
            if os.path.isfile(os.path.join(os.path.expanduser('~'),XML_FILENAME)):
                XMLpath = os.path.join(os.path.expanduser('~'),XML_FILENAME)
            else:
                # look in local folder, hope we may write
                if os.path.isfile(os.path.join(".",XML_FILENAME)):
                    if os.access(os.path.join(".",XML_FILENAME), os.W_OK):
                        XMLpath = os.path.join(".",XML_FILENAME)
                    else:
                        self.logger.error("No write access to XML file")
                        exit(1)
                else:
                    self.logger.error("No XML file found")
                    exit(1)
        try:         
            tree = ET.parse(XMLpath)
            root = tree.getroot()
        
            for child in root:
                cursync={}
                cursync['name']=child.tag
                for toy in child:
                    cursync[toy.tag]=Common.gettype(toy.text)
                cursync['observer']=None
                origname=cursync['name']
                cursync['name']=origname+"-->"
                cursync['1']=Event()
                cursync['list1']=[]
                if Common.checkkey(cursync,'reversesync') == True: 
                    cursync['2']=Event()
                    cursync['list2']=[]
                else:
                    cursync['2']=None
                    cursync['list2']=None
                self.syncs.append(cursync.copy())
                if Common.checkkey(cursync,'reversesync') == True:
                    if Common.checkkey(cursync,'source') and Common.checkkey(cursync,'destination'):
                        tempdest = cursync['destination']
                        cursync['destination']=cursync['source']
                        cursync['source']=tempdest
                        cursync['name']=origname+"<--"
                        temp2=cursync['2']
                        cursync['2']=cursync['1']
                        cursync['1']=temp2
                        templist2=cursync['list2']
                        cursync['list2']=cursync['list1']
                        cursync['list1']=templist2
                        self.syncs.append(cursync)
                    else:
                        print("Error adding job for reserve syncing")
                
        except Exception as e:
            self.logger.error("Error parsing xml file")
            self.logger.error("Check XML file syntax for errors")
            self.logger.exception(e)
            exit(1)
        
    def title(self):
        print("SyncWatch file and folder synchronization")
        print("Version: " + VERSION)
        print(" ")
    
    def GetLogger(self):
        logpath = "/var/log"
        LoggerPath = ""
        # first look in log path
        if os.path.exists(logpath):
            if os.access(logpath, os.W_OK):
                LoggerPath = os.path.join(logpath,LOG_FILENAME)
        if (not LoggerPath):
            # then look in home folder
            if os.access(os.path.expanduser('~'), os.W_OK):
                LoggerPath = os.path.join(os.path.expanduser('~'),LOG_FILENAME)
            else:
                print("Error opening logger, exit syncwatch")
                exit(1) 
        return (LoggerPath)
        
    def exit_app(self, signum, frame):
        self.exitevent.set()
    
#########################################################
if __name__ == "__main__":
    SyncWatch().run(sys.argv[1:])