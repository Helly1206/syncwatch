#!/bin/bash
NAME="syncwatch"
INSTALL="/usr/bin/install -c"
INSTALL_DATA="$INSTALL -m 644"
INSTALL_PROGRAM="$INSTALL"
ETCDIR="/etc"
USRDIR="/usr"
OPTDIR="/opt"
OPTLOC="$OPTDIR/$NAME"
ETCLOC=$ETCDIR
BINDIR="$USRDIR/bin"
SERVICEDIR="$ETCDIR/systemd/system"
SERVICESCRIPT="$NAME.service"
DAEMON="$NAME.py"
DAEMONEXE=$NAME
DAEMONCONF="$NAME.xml"
DEBFOLDER="debian"


if [ "$EUID" -ne 0 ]
then 
	echo "Please execute as root ('sudo install.sh' or 'sudo make install')"
	exit
fi

if [ "$1" == "-u" ] || [ "$1" == "-U" ]
then
	echo "$NAME uninstall script"

	echo "Uninstalling daemon $NAME"
	systemctl stop "$SERVICESCRIPT"
	systemctl disable "$SERVICESCRIPT"
	if [ -e "$SERVICEDIR/$SERVICESCRIPT" ]; then rm -f "$SERVICEDIR/$SERVICESCRIPT"; fi
    
    echo "Uninstalling $NAME"
	if [ -e "$BINDIR/$DAEMONEXE" ]; then rm -f "$BINDIR/$DAEMONEXE"; fi
	if [ -d "$OPTLOC" ]; then rm -rf "$OPTLOC"; fi
elif [ "$1" == "-h" ] || [ "$1" == "-H" ]
then
	echo "Usage:"
	echo "  <no argument>: install $NAME"
	echo "  -u/ -U       : uninstall $NAME"
	echo "  -h/ -H       : this help file"
	echo "  -d/ -D       : build debian package"
	echo "  -c/ -C       : Cleanup compiled files in install folder"
elif [ "$1" == "-c" ] || [ "$1" == "-C" ]
then
	echo "$NAME Deleting compiled files in install folder"
	py3clean .
	rm -f ./*.deb
	rm -rf "$DEBFOLDER"/$NAME
	rm -f "$DEBFOLDER"/files
	rm -f "$DEBFOLDER"/files.new
	rm -f "$DEBFOLDER"/$NAME.*
elif [ "$1" == "-d" ] || [ "$1" == "-D" ]
then
	echo "$NAME build debian package"
	py3clean .
	fakeroot debian/rules clean binary
	mv ../*.deb .
else
	echo "$NAME install script"

	echo "Stop running services"
	systemctl stop $SERVICESCRIPT
    systemctl disable $SERVICESCRIPT

    echo "Installing $NAME"
    if [ -d "$OPTLOC" ]; then rm -rf "$OPTLOC"; fi
	if [ ! -d "$OPTLOC" ]; then 
		mkdir "$OPTLOC"
		chmod 755 "$OPTLOC"
	fi

	$INSTALL_PROGRAM ".$OPTLOC/$DAEMON" "$OPTLOC"
    
    echo "Installing $DAEMONCONF"
	if [ ! -e "$ETCLOC/$DAEMONCONF" ]; then 
		$INSTALL_DATA ".$ETCLOC/$DAEMONCONF" "$ETCLOC/$DAEMONCONF"
	fi

	echo "Installing daemon $NAME"
	read -p "Do you want to install an automatic startup service for $NAME (Y/n)? " -n 1 -r
	echo    # (optional) move to a new line
	if [[ $REPLY =~ ^[Nn]$ ]]
	then
		echo "Skipping install automatic startup service for $NAME"
	else
		echo "Install automatic startup service for $NAME"
		$INSTALL_DATA "$SERVICEDIR/$SERVICESCRIPT" "$SERVICEDIR/$SERVICESCRIPT"

		systemctl enable $SERVICESCRIPT
		systemctl start $SERVICESCRIPT
	fi
fi