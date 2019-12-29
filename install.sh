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
SYSTEMDDIR="./systemd"
SERVICEDIR="$ETCDIR/systemd/system"
SERVICESCRIPT="$NAME.service"
DAEMON="$NAME.py"
DAEMONEXE=$NAME
DAEMONCONF="$NAME.xml"


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

	$INSTALL_PROGRAM "./$DAEMON" "$OPTLOC"
    
    echo "Installing $DAEMONCONF"
	if [ ! -e "$ETCLOC/$DAEMONCONF" ]; then 
		$INSTALL_DATA "./$DAEMONCONF" "$ETCLOC/$DAEMONCONF"
	fi

	echo "Installing daemon $NAME"
	read -p "Do you want to install an automatic startup service for $NAME (Y/n)? " -n 1 -r
	echo    # (optional) move to a new line
	if [[ $REPLY =~ ^[Nn]$ ]]
	then
		echo "Skipping install automatic startup service for $NAME"
	else
		echo "Install automatic startup service for $NAME"
		$INSTALL_DATA "$SYSTEMDDIR/$SERVICESCRIPT" "$SERVICEDIR/$SERVICESCRIPT"

		systemctl enable $SERVICESCRIPT
		systemctl start $SERVICESCRIPT
	fi
fi