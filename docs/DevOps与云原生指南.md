# DevOps与云原生指南

## 一、DevOps概述

### 1.1 什么是DevOps

DevOps是Development和Operations的组合，是一种文化和实践，旨在缩短系统开发生命周期，提供高质量的软件交付。

核心原则：
- 持续集成(CI)：频繁合并代码
- 持续交付(CD)：自动化部署
- 持续监控：实时反馈
- 基础设施即代码(IaC)：代码管理基础设施

### 1.2 DevOps工具链

版本控制：Git
CI/CD：Jenkins、GitHub Actions、GitLab CI
容器化：Docker、Podman
编排：Kubernetes
配置管理：Ansible、Terraform
监控：Prometheus、Grafana
日志：ELK Stack

## 二、Git版本控制

### 2.1 基本操作

git init：初始化仓库
git clone：克隆仓库
git add：暂存文件
git commit：提交更改
git push：推送到远程
git pull：拉取远程更新

### 2.2 分支管理

git branch：创建分支
git checkout：切换分支
git merge：合并分支
git rebase：变基

### 2.3 Git工作流

Git Flow：main + develop + feature + release + hotfix
GitHub Flow：main + feature branch
Trunk Based Development：主干开发

### 2.4 最佳实践

有意义的提交信息
小而频繁的提交
代码审查(Pull Request)
保护主分支

## 三、Docker容器化

### 3.1 基本概念

镜像(Image)：只读模板
容器(Container)：运行实例
仓库(Registry)：镜像存储

### 3.2 Dockerfile

FROM：基础镜像
WORKDIR：工作目录
COPY/ADD：复制文件
RUN：执行命令
EXPOSE：声明端口
CMD/ENTRYPOINT：启动命令

示例：
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]

### 3.3 Docker Compose

多容器应用编排：
services:
  web:
    build: .
    ports: ["8000:8000"]
  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: secret

### 3.4 最佳实践

多阶段构建减小镜像
使用.dockerignore
一个容器一个进程
健康检查
非root用户运行

## 四、Kubernetes(K8s)

### 4.1 核心概念

Pod：最小部署单元
Deployment：无状态应用部署
StatefulSet：有状态应用
Service：服务发现和负载均衡
Ingress：HTTP路由
ConfigMap/Secret：配置管理
PV/PVC：持久化存储

### 4.2 常用命令

kubectl get pods：查看Pod
kubectl apply -f manifest.yaml：创建资源
kubectl logs pod-name：查看日志
kubectl exec -it pod-name -- /bin/bash：进入容器
kubectl scale deployment web --replicas=3：扩缩容

### 4.3 部署策略

滚动更新(Rolling Update)：逐步替换
蓝绿部署(Blue-Green)：两套环境切换
金丝雀发布(Canary)：小范围验证

## 五、CI/CD

### 5.1 GitHub Actions

工作流定义在.github/workflows/目录下。

示例：
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: pytest

### 5.2 Jenkins

Pipeline as Code：
pipeline {
    agent any
    stages {
        stage('Build') { steps { sh 'make build' } }
        stage('Test') { steps { sh 'make test' } }
        stage('Deploy') { steps { sh 'make deploy' } }
    }
}

### 5.3 流水线设计

阶段：构建 -> 测试 -> 部署到Staging -> 验证 -> 部署到Production
门控：自动化测试、安全扫描、人工审批

## 六、基础设施即代码

### 6.1 Terraform

声明式基础设施管理。

provider "aws" {
    region = "us-east-1"
}
resource "aws_instance" "web" {
    ami = "ami-0c55b159cbfafe1f0"
    instance_type = "t2.micro"
}

terraform init/plan/apply/destroy

### 6.2 Ansible

配置管理和应用部署。

playbook.yml：
- hosts: webservers
  tasks:
    - name: Install nginx
      apt: name=nginx state=present
    - name: Start nginx
      service: name=nginx state=started

## 七、监控与日志

### 7.1 Prometheus

时间序列数据库，拉取模式采集指标。
PromQL查询语言
告警规则

### 7.2 Grafana

可视化仪表盘。
数据源：Prometheus、Elasticsearch、MySQL
告警通知

### 7.3 ELK Stack

Elasticsearch：搜索引擎和分析引擎
Logstash：日志收集和处理
Kibana：可视化界面

### 7.4 日志最佳实践

结构化日志(JSON格式)
日志级别：DEBUG/INFO/WARN/ERROR
关联ID(Trace ID)
集中式日志管理

## 八、安全

### 8.1 应用安全

HTTPS/TLS
输入验证和消毒
SQL注入防护
XSS防护
CSRF防护

### 8.2 容器安全

镜像扫描(Trivy)
最小权限原则
Secret管理(Vault)
网络策略

### 8.3 代码安全

依赖扫描(Dependabot)
SAST(静态应用安全测试)
DAST(动态应用安全测试)
密钥管理

## 九、云服务

### 9.1 AWS核心服务

EC2：虚拟机
S3：对象存储
RDS：关系型数据库
Lambda：无服务器函数
ECS/EKS：容器服务

### 9.2 阿里云

ECS：云服务器
OSS：对象存储
RDS：数据库
函数计算

## 十、最佳实践

自动化一切：构建、测试、部署、监控
小步快跑：频繁发布小变更
快速反馈：缩短从提交到部署的时间
文化转变：开发和运维协作
持续改进：回顾会议、度量指标
