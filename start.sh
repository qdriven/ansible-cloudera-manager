#!/bin/sh
nohup ansible-playbook playbooks/bootstrap.yml >log 2>&1 &
