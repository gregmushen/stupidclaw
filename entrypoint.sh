#!/bin/bash
# Dump env vars for cron (cron doesn't inherit Docker env vars)
printenv | grep -v "no_proxy" >> /etc/environment
cron -f
