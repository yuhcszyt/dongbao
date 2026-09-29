#!/usr/bin/env bash
# usage: run-ai-jump.sh <timeout> <cmd>  — Mac→阿里云→ai-infra(100.105.200.22)
exec expect -c "
set timeout ${1:-300}
spawn ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=10 -J root@47.119.190.152 yu@100.105.200.22 {$2}
expect {
  -re {root@47.119.190.152's [Pp]assword.*:} { send \"f38ae263D\r\"; exp_continue }
  -re {yu@100.105.200.22's [Pp]assword.*:} { send \"abc123\r\"; exp_continue }
  timeout { puts TIMEOUT; exit 124 }
  eof
}
catch wait result
exit [lindex \$result 3]
"
