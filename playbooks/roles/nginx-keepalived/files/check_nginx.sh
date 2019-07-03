#! /bin/bash

if [ "$(ps -ef | grep "nginx: master process"| grep -v grep )" == "" ]; then
  su - root -c 'systemctl start nginx'
  sleep 5
  if [ "$(ps -ef | grep "nginx: master process"| grep -v grep )" == "" ]; then
    systemctl stop  keepalived
  fi
fi
