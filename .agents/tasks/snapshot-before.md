# Snapshot ANTES de Eliminación de Stacks Demo

**Fecha de captura:** 2026-09-07  
**Región:** us-east-1  
**Cuenta AWS:** 062560094883  
**Total stacks activos:** 8 (6 demo + 1 aplicación principal + 1 CDKToolkit)

---

## Resumen Ejecutivo

Se identificaron **6 stacks de demo** creados como recursos de muestra para el Cloud Governance Agent,
más el stack principal `CloudGovernanceAgent` y el bootstrap `CDKToolkit`. Los stacks demo contienen
recursos que generan costos y serán eliminados.

---

## Stacks Activos (stacks-before.json)

| Stack | Estado | Descripción | Creado |
|---|---|---|---|
| `CloudGovernanceAgent` | UPDATE_COMPLETE | Stack principal de la aplicación | 2026-09-07T22:11 |
| `CGA-Sample-Compute` | CREATE_COMPLETE | EC2 subutilizada/detenida, Lambda sin invocaciones | 2026-09-07T22:05 |
| `CGA-Sample-Database` | CREATE_COMPLETE | RDS pública/detenida, DynamoDB inactiva | 2026-09-07T21:57 |
| `CGA-Sample-Storage` | CREATE_COMPLETE | S3 público, sin lifecycle, EBS huérfano | 2026-09-07T21:54 |
| `CGA-Sample-Network` | CREATE_COMPLETE | VPC, Security Groups inseguros, EIP huérfana, ALB inactivo | 2026-09-07T21:50 |
| `CGA-Sample-Frontend` | CREATE_COMPLETE | CloudFront sin WAF, HTTP permitido | 2026-09-07T21:47 |
| `CGA-Sample-IAM` | CREATE_COMPLETE | Usuarios sin MFA, keys antiguas, políticas permisivas | 2026-09-07T21:41 |
| `CDKToolkit` | CREATE_COMPLETE | Bootstrap CDK | 2026-09-07T21:39 |

---

## Detalle de Recursos por Stack Demo

### 1. CGA-Sample-IAM
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-IAM/de952050-ab04-11f1-8d95-0affe682e87b`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** Usuarios sin MFA, access keys antiguas, políticas permisivas

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| CDKMetadata | AWS::CDK::Metadata | de952050-ab04-11f1-8d95-0affe682e87b |
| DevGroup61842E99 | AWS::IAM::Group | developers |
| PolicyPermissive5916FB15 | AWS::IAM::Policy | CGA-S-Polic-BzAswxfPd3Rq |
| UserAdminDirect7261E0D5 | AWS::IAM::User | iam-user-dev-admin |
| UserInactive726643FE | AWS::IAM::User | iam-user-ex-employee |
| UserNoMfa1723E96A | AWS::IAM::User | iam-user-no-mfa |
| UserOldKeyAccessKey | AWS::IAM::AccessKey | AKIAQ5EG7JKR567ZQUHM |
| UserOldKeyC576BC6B | AWS::IAM::User | iam-user-svc-integration |
| UserPermissive8EDEE1AA | AWS::IAM::User | iam-user-emergency |

**Total recursos:** 9

---

### 2. CGA-Sample-Frontend
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-Frontend/b6b1ae40-ab05-11f1-96bf-0e8283057ca7`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** CloudFront sin WAF, HTTP permitido

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| CDKMetadata | AWS::CDK::Metadata | b6b1ae40-ab05-11f1-96bf-0e8283057ca7 |
| CfAdminNoWaf48658357 | AWS::CloudFront::Distribution | EY7V9BY6D9983 |
| CfAdminNoWafOrigin1S3Origin0D119056 | AWS::CloudFront::CloudFrontOriginAccessIdentity | E1CF0MKU5ENZ24 |
| CfNoWafC368A3C6 | AWS::CloudFront::Distribution | E3E9JWI4UVRF7D |
| CfNoWafOrigin1S3Origin55F2BD2F | AWS::CloudFront::CloudFrontOriginAccessIdentity | E1FVWE7I2NECCB |
| CustomS3AutoDeleteObjectsCustomResourceProviderHandler9D90184F | AWS::Lambda::Function | CGA-Sample-Frontend-CustomS3AutoDeleteObjectsCusto-p4HUh6zFaxaS |
| CustomS3AutoDeleteObjectsCustomResourceProviderRole3B1BD092 | AWS::IAM::Role | CGA-Sample-Frontend-CustomS3AutoDeleteObjectsCustom-3mB8fn9X2Bxa |
| OriginBucket2695925C0 | AWS::S3::Bucket | cga-sample-frontend-originbucket2695925c0-8pzllsqlggn9 |
| OriginBucket2AutoDeleteObjectsCustomResource00BE0898 | Custom::S3AutoDeleteObjects | 095cf26a-83c8-4f3a-bfa4-404839f86491 |
| OriginBucket2Policy54A2F994 | AWS::S3::BucketPolicy | cga-sample-frontend-originbucket2695925c0-8pzllsqlggn9 |
| OriginBucketAutoDeleteObjectsCustomResource064ED07E | Custom::S3AutoDeleteObjects | 45b2d8b2-7fb3-40f4-950f-ea184d228290 |
| OriginBucketCA772B8F | AWS::S3::Bucket | cga-sample-frontend-originbucketca772b8f-ivpngzmtvkml |
| OriginBucketPolicyFD67BA59 | AWS::S3::BucketPolicy | cga-sample-frontend-originbucketca772b8f-ivpngzmtvkml |

**Total recursos:** 13

---

### 3. CGA-Sample-Network
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-Network/2869eca0-ab06-11f1-93b7-0e400b3328f7`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** VPC, Security Groups inseguros, EIP huérfana, ALB inactivo

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| AlbIdle10668698 | AWS::ElasticLoadBalancingV2::LoadBalancer | arn:aws:elasticloadbalancing:us-east-1:062560094883:loadbalancer/app/alb-idle-demo/c92068747901a3d6 |
| AlbIdleIdleListener07194058 | AWS::ElasticLoadBalancingV2::Listener | arn:...listener/app/alb-idle-demo/.../dfe3a6c50c5e58bd |
| AlbIdleSecurityGroup6A869547 | AWS::EC2::SecurityGroup | sg-01a05c1fa9c94357b |
| CDKMetadata | AWS::CDK::Metadata | 2869eca0-ab06-11f1-93b7-0e400b3328f7 |
| IdleTargetGroup9278F6E9 | AWS::ElasticLoadBalancingV2::TargetGroup | arn:...targetgroup/CGA-Sa-IdleT-ZJANBDSKY2QI/8ad81f853fe166bc |
| OrphanEIP | AWS::EC2::EIP | 100.49.64.172 |
| SampleVpc07DAD426 | AWS::EC2::VPC | vpc-0aa4f394ecd69c9a8 |
| SampleVpcIGW8FA8DC37 | AWS::EC2::InternetGateway | igw-020632bed7325eb60 |
| SampleVpcIsolatedSubnet1RouteTable79AC7569 | AWS::EC2::RouteTable | rtb-00979adb8e640d636 |
| SampleVpcIsolatedSubnet1RouteTableAssociationFEF6CBBF | AWS::EC2::SubnetRouteTableAssociation | rtbassoc-035375acd63b7295d |
| SampleVpcIsolatedSubnet1SubnetF214E54C | AWS::EC2::Subnet | subnet-02edbcefffef5d62d |
| SampleVpcIsolatedSubnet2RouteTableAssociation5237E009 | AWS::EC2::SubnetRouteTableAssociation | rtbassoc-0733b20bcc492b7b8 |
| SampleVpcIsolatedSubnet2RouteTableC533E9A1 | AWS::EC2::RouteTable | rtb-0fef780f760708ad7 |
| SampleVpcIsolatedSubnet2Subnet07925D58 | AWS::EC2::Subnet | subnet-02b6db2c3ad2dcd24 |
| SampleVpcPublicSubnet1DefaultRouteEA6D638D | AWS::EC2::Route | rtb-0bbab14dce51b7341\|0.0.0.0/0 |
| SampleVpcPublicSubnet1RouteTableAssociation77BCAA2F | AWS::EC2::SubnetRouteTableAssociation | rtbassoc-0f00ca806283562d0 |
| SampleVpcPublicSubnet1RouteTableE2EAB2A8 | AWS::EC2::RouteTable | rtb-0bbab14dce51b7341 |
| SampleVpcPublicSubnet1Subnet365106BA | AWS::EC2::Subnet | subnet-0f5522290d22a3cb4 |
| SampleVpcPublicSubnet2DefaultRoute99897BCA | AWS::EC2::Route | rtb-0d3be9ab287576817\|0.0.0.0/0 |
| SampleVpcPublicSubnet2RouteTable6661BA90 | AWS::EC2::RouteTable | rtb-0d3be9ab287576817 |
| SampleVpcPublicSubnet2RouteTableAssociation0186ED11 | AWS::EC2::SubnetRouteTableAssociation | rtbassoc-07545b981b06c2ae4 |
| SampleVpcPublicSubnet2Subnet08397B4B | AWS::EC2::Subnet | subnet-0643cf6638b034afe |
| SampleVpcVPCGW2B38F286 | AWS::EC2::VPCGatewayAttachment | IGW\|vpc-0aa4f394ecd69c9a8 |
| SgDbOpenB2ACEA9E | AWS::EC2::SecurityGroup | sg-01ebee9aa3e761e87 |
| SgWebOpenEC921A30 | AWS::EC2::SecurityGroup | sg-00b4d72260abae974 |

**Total recursos:** 25

---

### 4. CGA-Sample-Storage
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-Storage/a3060430-ab06-11f1-8000-0e1239767b57`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** S3 público, sin lifecycle, EBS huérfano

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| BucketAccessLogs082E23D6 | AWS::S3::Bucket | cga-sample-storage-bucketaccesslogs082e23d6-w2r2ofj0zvec |
| BucketAccessLogsPolicy8FC20C52 | AWS::S3::BucketPolicy | cga-sample-storage-bucketaccesslogs082e23d6-w2r2ofj0zvec |
| BucketArchive22C6E156 | AWS::S3::Bucket | cga-sample-storage-bucketarchive22c6e156-jxnqiurd8teb |
| BucketArchivePolicy87A924B9 | AWS::S3::BucketPolicy | cga-sample-storage-bucketarchive22c6e156-jxnqiurd8teb |
| BucketNoLogsC5CEDEBA | AWS::S3::Bucket | cga-sample-storage-bucketnologsc5cedeba-x57vvv2qjelc |
| BucketNoLogsPolicy07CDD477 | AWS::S3::BucketPolicy | cga-sample-storage-bucketnologsc5cedeba-x57vvv2qjelc |
| BucketPublic02D45353 | AWS::S3::Bucket | cga-sample-storage-bucketpublic02d45353-4qvutigzub5n |
| CDKMetadata | AWS::CDK::Metadata | a3060430-ab06-11f1-8000-0e1239767b57 |
| EbsOrphan | AWS::EC2::Volume | vol-0a9a460f93268004f |

**Total recursos:** 9

---

### 5. CGA-Sample-Database
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-Database/1f8ea980-ab07-11f1-a384-0afff3638a3b`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** RDS pública/detenida, DynamoDB inactiva

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| CDKMetadata | AWS::CDK::Metadata | 1f8ea980-ab07-11f1-a384-0afff3638a3b |
| CGASampleDatabaseRdsPublicMysqlSecretADDE8B383... | AWS::SecretsManager::Secret | arn:...secret:CGASampleDatabaseRdsPublicM-5vrGUHOPc1XD-9Mn5yU |
| CGASampleDatabaseRdsStoppedPostgresSecret42826FAC... | AWS::SecretsManager::Secret | arn:...secret:CGASampleDatabaseRdsStopped-roz4xdSPyB1U-NKR0G2 |
| RdsPublicMysql526504E2 | AWS::RDS::DBInstance | cga-sample-database-rdspublicmysql526504e2-wvmsqbni2jdv |
| RdsPublicMysqlSecretAttachment3BEB7477 | AWS::SecretsManager::SecretTargetAttachment | arn:...secret:CGASampleDatabaseRdsPublicM-5vrGUHOPc1XD-9Mn5yU |
| RdsPublicMysqlSubnetGroupCA76B4D4 | AWS::RDS::DBSubnetGroup | cga-sample-database-rdspublicmysqlsubnetgroupca76b4d4-zincwolvdcqj |
| RdsStoppedPostgres93B05D34 | AWS::RDS::DBInstance | cga-sample-database-rdsstoppedpostgres93b05d34-n4by6cuc4tq0 |
| RdsStoppedPostgresSecretAttachment2C162547 | AWS::SecretsManager::SecretTargetAttachment | arn:...secret:CGASampleDatabaseRdsStopped-roz4xdSPyB1U-NKR0G2 |
| RdsStoppedPostgresSubnetGroupDE6996E0 | AWS::RDS::DBSubnetGroup | cga-sample-database-rdsstoppedpostgressubnetgroupde6996e0-s07svbhybsdw |
| TblInactiveBEB3D936 | AWS::DynamoDB::Table | tbl-inactive-sessions |

**Total recursos:** 10

---

### 6. CGA-Sample-Compute
**StackId:** `arn:aws:cloudformation:us-east-1:062560094883:stack/CGA-Sample-Compute/31dfe1c0-ab08-11f1-8954-0e447ebf1a8f`  
**Estado:** CREATE_COMPLETE  
**Propósito demo:** EC2 subutilizada/detenida, Lambda sin invocaciones

| LogicalResourceId | ResourceType | PhysicalResourceId |
|---|---|---|
| CDKMetadata | AWS::CDK::Metadata | 31dfe1c0-ab08-11f1-8954-0e447ebf1a8f |
| Ec2NoTags2208BA76 | AWS::EC2::Instance | i-076b75d85f6a96141 |
| Ec2NoTagsInstanceProfile02D162EF | AWS::IAM::InstanceProfile | CGA-Sample-Compute-Ec2NoTagsInstanceProfile02D162EF-75ZQMx0OtxvX |
| Ec2NoTagsInstanceRole33ECF74F | AWS::IAM::Role | CGA-Sample-Compute-Ec2NoTagsInstanceRole33ECF74F-kUBE5J0VFczK |
| Ec2OversizedD0494D94 | AWS::EC2::Instance | i-0080cd765d651a620 |
| Ec2OversizedInstanceProfile604FBAE3 | AWS::IAM::InstanceProfile | CGA-Sample-Compute-Ec2OversizedInstanceProfile604FBAE3-gtK8GNuHpaTL |
| Ec2OversizedInstanceRole8741F262 | AWS::IAM::Role | CGA-Sample-Compute-Ec2OversizedInstanceRole8741F262-rl0RpkDHkL4i |
| Ec2StoppedE6A6593A | AWS::EC2::Instance | i-08f1e0f572fb7dd80 |
| Ec2StoppedInstanceProfile0C0B04F2 | AWS::IAM::InstanceProfile | CGA-Sample-Compute-Ec2StoppedInstanceProfile0C0B04F2-E1QLRVsMpfxh |
| Ec2StoppedInstanceRole29DC83C0 | AWS::IAM::Role | CGA-Sample-Compute-Ec2StoppedInstanceRole29DC83C0-em904mQngyVS |
| FnLegacyBF6153D6 | AWS::Lambda::Function | fn-legacy-webhook |
| FnLegacyServiceRole11923054 | AWS::IAM::Role | CGA-Sample-Compute-FnLegacyServiceRole11923054-2aaqHRNhvPwp |
| FnUnused20D4C174 | AWS::Lambda::Function | fn-unused-processor |
| FnUnusedServiceRoleCD63E439 | AWS::IAM::Role | CGA-Sample-Compute-FnUnusedServiceRoleCD63E439-MZr44OC9EFpd |

**Total recursos:** 14

---

## Resumen de Recursos por Tipo (stacks demo)

| Tipo de Recurso | Cantidad | Stacks |
|---|---|---|
| AWS::EC2::Instance | 3 | Compute |
| AWS::RDS::DBInstance | 2 | Database |
| AWS::CloudFront::Distribution | 2 | Frontend |
| AWS::ElasticLoadBalancingV2::LoadBalancer | 1 | Network |
| AWS::DynamoDB::Table | 1 | Database |
| AWS::EC2::EIP | 1 | Network |
| AWS::EC2::Volume (EBS) | 1 | Storage |
| AWS::Lambda::Function | 3 | Frontend (1), Compute (2) |
| AWS::S3::Bucket | 6 | Frontend (2), Storage (4) |
| AWS::IAM::User | 5 | IAM |
| AWS::IAM::Group | 1 | IAM |
| AWS::IAM::Policy | 1 | IAM |
| AWS::IAM::AccessKey | 1 | IAM |
| AWS::SecretsManager::Secret | 2 | Database |
| AWS::EC2::VPC | 1 | Network |
| AWS::EC2::SecurityGroup | 3 | Network |
| Otros (subnets, route tables, etc.) | ~25 | Network |

---

## Recursos que Generan Costo Significativo (a eliminar)

| Recurso | ID | Stack | Costo estimado/mes |
|---|---|---|---|
| RDS MySQL (público) | cga-sample-database-rdspublicmysql... | Database | ~$15–25 USD |
| RDS PostgreSQL (detenido) | cga-sample-database-rdsstoppedpostgres... | Database | ~$0 (detenido, pero storage ~$2) |
| EC2 Oversized | i-0080cd765d651a620 | Compute | ~$30–70 USD |
| EC2 No Tags | i-076b75d85f6a96141 | Compute | ~$10–30 USD |
| EC2 Stopped | i-08f1e0f572fb7dd80 | Compute | ~$0 (detenido, storage ~$1) |
| ALB Idle | alb-idle-demo | Network | ~$16–20 USD |
| EIP Huérfana | 100.49.64.172 | Network | ~$3.60 USD |
| CloudFront (x2) | EY7V9BY6D9983, E3E9JWI4UVRF7D | Frontend | Mínimo (sin tráfico) |

**Costo total estimado de stacks demo:** **~$80–170 USD/mes**

---

## Stacks a Conservar

- **`CloudGovernanceAgent`** — Stack principal de la aplicación. NO eliminar.
- **`CDKToolkit`** — Bootstrap CDK necesario para futuros deployments. NO eliminar.

---

## Notas

- Todos los 6 stacks demo existían al momento de la captura (ninguno fue reportado como 'ya eliminado').
- Los archivos JSON de detalle se encuentran en: `.agents/tasks/resources-<StackName>.json`
- Este snapshot fue tomado como registro previo a la eliminación de los stacks demo para tener trazabilidad histórica.
