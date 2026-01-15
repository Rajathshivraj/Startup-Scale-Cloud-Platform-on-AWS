# 🏗️ Startup-Scale AWS Cloud Platform

## 📋 Overview

This project demonstrates a **production-grade AWS architecture** designed for a scalable startup platform. It showcases expertise in **infrastructure as code, containerization, CI/CD automation, and AWS Well-Architected Framework principles**.

**Purpose:** Portfolio demonstration of AWS DevOps capabilities for Solutions Architect and DevOps Engineer roles.

---

## 🎯 Architecture Highlights

### Core Components

- **Compute:** ECS Fargate (serverless containers) + Lambda (event-driven processing)
- **Networking:** Multi-AZ VPC with public/private subnet isolation
- **Load Balancing:** Application Load Balancer with health checks
- **Data Layer:** RDS (relational) + DynamoDB (NoSQL) for hybrid workloads
- **Observability:** CloudWatch Logs, Metrics, and Alarms
- **CI/CD:** GitHub Actions → ECR → ECS automated deployment pipeline

### Why This Architecture?

**1. Scalability Without Overhead**
- ECS Fargate eliminates EC2 instance management
- Auto-scaling based on CPU/memory metrics
- DynamoDB for unlimited read/write capacity

**2. High Availability**
- Multi-AZ deployment (minimum 2 availability zones)
- ALB automatically distributes traffic across healthy targets
- RDS automated backups and multi-AZ standby

**3. Security-First Design**
- Private subnets for compute/data layers
- NAT Gateway for outbound-only internet access
- IAM least privilege with task-specific roles
- Security groups as stateful firewalls

**4. Cost Optimization**
- Pay-per-use compute (Fargate + Lambda)
- S3 lifecycle policies for log archival
- RDS reserved instances consideration for production

---

## 🔐 Security Model

### Network Security
```
Internet → IGW → Public Subnet (ALB only)
                    ↓
           Private Subnet (ECS Tasks, RDS)
                    ↓
           NAT Gateway → Internet (outbound only)
```

### IAM Architecture
- **ECS Task Role:** Grants container access to DynamoDB, S3, CloudWatch
- **ECS Execution Role:** Pulls images from ECR, writes logs to CloudWatch
- **Lambda Execution Role:** Invokes services, reads from DynamoDB
- **Principle:** No long-lived credentials, STS temporary tokens only

### Data Protection
- RDS encryption at rest (KMS)
- SSL/TLS for data in transit
- Secrets Manager for database credentials
- VPC endpoints to avoid internet exposure

---

## 📊 Observability Strategy

### Logging
- **Application Logs:** Streamed to CloudWatch Logs via awslogs driver
- **ALB Access Logs:** Stored in S3 for compliance/analysis
- **VPC Flow Logs:** Network traffic analysis and security auditing

### Monitoring
- **CloudWatch Metrics:** CPU, memory, request count, latency
- **Custom Metrics:** Business KPIs from application code
- **Alarms:** Automated SNS notifications for threshold breaches

### Tracing
- X-Ray integration for distributed tracing (ready for implementation)
- Request flow: ALB → ECS → RDS/DynamoDB

---

## 🔄 CI/CD Pipeline Flow

```
1. Developer pushes code to GitHub
   ↓
2. GitHub Actions triggered on 'main' branch
   ↓
3. Build Docker image
   ↓
4. Run security scan (Trivy)
   ↓
5. Push image to ECR with Git SHA tag
   ↓
6. Update ECS task definition with new image
   ↓
7. Deploy to ECS Fargate (rolling update)
   ↓
8. Health checks validate deployment
   ↓
9. Rollback on failure (automatic)
```

**Zero-Downtime Deployment:** ALB drains connections before stopping old tasks.

---

## 📁 Project Structure

```
startup-aws-platform/
├── terraform/           # Infrastructure as Code
│   ├── provider.tf      # AWS provider configuration
│   ├── variables.tf     # Centralized variable definitions
│   ├── vpc.tf           # Network foundation
│   ├── ecs.tf           # Container orchestration
│   ├── alb.tf           # Load balancer + target groups
│   ├── iam.tf           # Roles and policies
│   ├── rds.tf           # PostgreSQL database
│   ├── dynamodb.tf      # NoSQL table
│   ├── cloudwatch.tf    # Monitoring and alarms
│   └── outputs.tf       # Export important values
│
├── docker/              # Container definitions
│   └── Dockerfile       # Multi-stage Python build
│
├── app/                 # Application code
│   └── app.py           # Flask API service
│
├── lambda/              # Serverless functions
│   └── handler.py       # Event processor
│
└── .github/workflows/   # CI/CD automation
    └── deploy.yml       # GitHub Actions pipeline
```

---

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform >= 1.5.0
- Docker installed locally

### Deployment Steps

```bash
# 1. Initialize Terraform
cd terraform
terraform init

# 2. Review planned changes
terraform plan

# 3. Apply infrastructure
terraform apply -auto-approve

# 4. Note outputs (ALB DNS, ECR repository)
terraform output

# 5. Build and push Docker image
cd ../docker
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t startup-platform .
docker tag startup-platform:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest

# 6. Access application
curl http://<alb-dns-name>/health
```

---

## 🎓 Key Learning Outcomes

This project demonstrates proficiency in:

✅ **AWS Well-Architected Framework** (5 pillars: operational excellence, security, reliability, performance, cost optimization)  
✅ **Infrastructure as Code** (declarative Terraform, idempotent deployments)  
✅ **Container Orchestration** (ECS task definitions, service auto-scaling)  
✅ **Network Engineering** (VPC design, subnet segmentation, routing)  
✅ **GitOps Practices** (version-controlled infrastructure, automated deployments)  
✅ **Security Compliance** (least privilege IAM, encryption, audit logging)  

---

## 📈 Scalability Considerations

**Current State:** Single region, development-grade

**Production Enhancements:**
- Multi-region active-active with Route 53 failover
- Aurora Serverless for elastic database scaling
- ElastiCache Redis for session management
- CloudFront CDN for static assets
- WAF for application-layer DDoS protection
- Backup automation with AWS Backup

---

## 🛠️ Technologies Used

| Category | Technology |
|----------|-----------|
| Cloud Provider | AWS |
| IaC | Terraform |
| Containers | Docker, ECS Fargate |
| CI/CD | GitHub Actions |
| Languages | Python 3.11 |
| Databases | PostgreSQL (RDS), DynamoDB |
| Monitoring | CloudWatch, CloudWatch Logs |

---

## 📞 Contact

This is a **portfolio demonstration project** showcasing AWS DevOps engineering capabilities.

**Note:** This codebase prioritizes architectural clarity and educational value over production deployment. Real-world implementations would include additional hardening, cost controls, and compliance measures.

---

**License:** MIT (Portfolio Use)
