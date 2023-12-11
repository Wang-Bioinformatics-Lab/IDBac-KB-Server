#!/bin/bash

celery -A tasks worker -l info -c 1 -Q depositionworker --max-tasks-per-child 10 --loglevel INFO

