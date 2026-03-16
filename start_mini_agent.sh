#!/bin/bash
cd /home/admin/mini-code-agent || exit 1
source /home/admin/mini-code-agent/micode311/bin/activate
exec python -m monitor.run_agent_with_monitor "$@"
