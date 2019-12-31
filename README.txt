SyncWatch v0.8.1

SyncWatch service to synchronize 2 locations on file or folder change
========= ======= == =========== = ========= == ==== == ====== ======

SyncWatch uses rsync to synchronize files and folders automatically on changes in the source folder.

2 way synchronization (reversesync) is possible.

This program can run as systemd service or as stand-alone program.
As systemd service it starts after rc.local, assuming every location is mounted at this time.

The service is completely configurable via syncwatch.xml, located in /etc/syncwatch.xml.

The xml file described the syncronizations to be done.
	
Add a sync to syncs to add a synchronization. You can name it anything you like. e.g. mybackup:
<mybackup>
	...
</mybackup>

The parameters per sync can be modified: 
	<source> is the source folder, obligated
	<destination> is the destination folder, obligated
	<delay> defines the delay between writing something to the source folder 
					and starting to sync in seconds. This is to prevent syncing while still 
					writing data. Default is 10 seconds.
	<resettimer> defines whether to reset the timer (start the delay again) when writing 
				 	data during the delay time. Default is true.
	<initsync> defines whether to sync on the program start. Default is false.
	<reversesync> defines whether to sync to source when a file or folder on the target changes.
					Default is false.
	<retry> defines whether to keep retrying setting up a connection, e.g. when source or destination
  					is not mounted (yet). Retry is done silent with a 10 second delay. Default is false.
	The following options are all rsync options. The a (archive) option is always added.
	<delete> defines whether to delete file on the destination (see rsync delete). Default is true.
	<exclude> defines patterns to be excluded from syncing (see rsync exclude). Multiple patterns
					should be comma separated. Default is empty.
	<include> defines patterns to be included in syncing (see rsync include). Multiple patterns
					should be comma separated. Default is empty.
	<compress> defines whether to compress files to be synced (see rsync compress). Default is true.
	<update> defines whether to update files to be synced (see rsync update). Default is true.
	<options> defines options added to rsync (see rsync manual). Multiple patterns may be comma
					separated. Contents is not checked. Default is empty.

That's all for now ...

Please send Comments and Bugreports to hellyrulez@home.nl