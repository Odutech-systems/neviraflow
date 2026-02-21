#!/bin/bash

PORT=5000
SCRIPT="/home/administrator/biometric/zkteco_http_listener.py "
LOGFILE="/home/administrator/biometric/listener.log"
PYTHON="/usr/bin/python3"

echo "=======================" >> $LOGFILE
echo "Run started at $(date)" >> $LOGFILE

PID=$(lsof -ti:$PORT)

if [ -n "$PID" ]; then
    echo "Port $PORT occupied by PID $PID - terminating ....." >> $LOGFILE
    kill -9 $PID
    sleep 2
else
    echo "Port $PORT already free." >> $LOGFILE
fi


# RUN SCRIPT
echo "Executing biometric listener ...." >> $LOGFILE

$PYTHON $SCRIPT >> $LOGFILE 2>&1

EXIT_CODE=$?

echo "Script Finished with exit code $EXIT_CODE" >> $LOGFILE
echo "Run ended at $(date)" >> $LOGFILE