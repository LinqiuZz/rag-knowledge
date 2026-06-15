# Linux系统管理与运维指南

## 一、Linux基础

### 1.1 文件系统

目录结构：
/：根目录
/bin：基本命令
/sbin：系统命令
/etc：配置文件
/home：用户目录
/var：可变数据
/tmp：临时文件
/usr：用户程序
/opt：可选软件

### 1.2 常用命令

文件操作：
ls -la：列出文件
cd /path：切换目录
cp/mv/rm：复制/移动/删除
mkdir -p：创建目录
chmod/chown：权限管理
find / -name "*.log"：查找文件
grep "error" file.log：搜索内容

文本处理：
cat/less/more：查看文件
head/tail：查看首尾
sed：流编辑器
awk：文本处理
sort/uniq：排序去重
wc：统计行数/字数

系统信息：
uname -a：系统信息
df -h：磁盘使用
free -h：内存使用
top/htop：进程监控
ps aux：进程列表
lsof：打开文件列表

### 1.3 权限管理

rwx：读/写/执行
chmod 755 file：设置权限
chown user:group file：修改所有者
umask：默认权限掩码

### 1.4 用户管理

useradd/userdel：添加/删除用户
passwd：修改密码
usermod：修改用户属性
su/sudo：切换用户/提权

## 二、Shell脚本

### 2.1 基本语法

变量：name="value"
条件：if [ condition ]; then ... fi
循环：for i in list; do ... done
函数：function name() { ... }
参数：$1, $2, $@, $#

### 2.2 常用技巧

错误处理：set -e
调试：set -x
管道：cmd1 | cmd2
重定向：> >> 2>&1
后台运行：nohup cmd &

## 三、网络管理

### 3.1 网络配置

ip addr：查看IP地址
ip route：查看路由表
netstat/ss：网络连接
ping/traceroute：网络诊断
curl/wget：HTTP请求
nslookup/dig：DNS查询

### 3.2 防火墙

iptables/nftables
firewalld
ufw(Ubuntu)

### 3.3 SSH

ssh user@host：远程登录
scp：文件传输
ssh-keygen：生成密钥
ssh-copy-id：复制公钥
配置免密登录

## 四、服务管理

### 4.1 systemd

systemctl start/stop/restart/status service
systemctl enable/disable service
journalctl -u service：查看日志

### 4.2 Nginx

反向代理、负载均衡、静态文件服务
配置文件：/etc/nginx/nginx.conf
server块、location块、upstream

### 4.3 MySQL

安装配置
用户权限管理
备份恢复
主从复制

## 五、性能优化

### 5.1 CPU优化

top/htop：CPU使用率
perf：性能分析
nice/renice：进程优先级

### 5.2 内存优化

free -h：内存使用
vmstat：虚拟内存
/proc/meminfo：内存详情

### 5.3 磁盘优化

iostat：IO统计
iotop：IO监控
dd：磁盘测试
fio：IO基准测试

### 5.4 网络优化

tcpdump：抓包分析
iftop：流量监控
iperf：带宽测试

## 六、自动化运维

### 6.1 Ansible

无代理，基于SSH
Playbook定义任务
Inventory管理主机

### 6.2 监控

Zabbix：企业级监控
Prometheus + Grafana
Nagios
自定义脚本

## 七、备份与恢复

全量备份、增量备份、差异备份
rsync：文件同步
mysqldump：数据库备份
定时任务：cron

## 八、安全加固

SSH安全：禁用密码登录、修改端口
防火墙：最小权限原则
日志审计：auditd
漏洞扫描：OpenVAS
入侵检测：OSSEC
