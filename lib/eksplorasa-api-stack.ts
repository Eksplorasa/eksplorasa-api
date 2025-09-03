import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as rds from "aws-cdk-lib/aws-rds";
import * as ec2 from "aws-cdk-lib/aws-ec2";

export class EksplorasaApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get stage from context, environment variable, or default to 'prod'
    const stage = this.node.tryGetContext("stage") || process.env.STAGE || "prod";

    // Create VPC for RDS database
    const vpc = new ec2.Vpc(this, `EksplorasaVpc-${stage}`, {
      maxAzs: 2,
      natGateways: 2, // Need at least one NAT gateway for RDS Proxy
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Create security group for RDS - allow public PostgreSQL access
    const dbSecurityGroup = new ec2.SecurityGroup(this, `DbSecurityGroup-${stage}`, {
      vpc,
      description: "Security group for RDS PostgreSQL database - publicly accessible",
      allowAllOutbound: true,
    });

    // Allow PostgreSQL access from VPC and anywhere on IPv4
    dbSecurityGroup.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(5432), "Allow PostgreSQL access from VPC");

    dbSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(5432), "Allow PostgreSQL access from anywhere");

    const database = new rds.DatabaseInstance(this, `EksplorasaDatabase${stage}`, {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_17_5,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO),
      credentials: rds.Credentials.fromPassword("eksplorasa", cdk.SecretValue.unsafePlainText("eksplorasa2025")),
      databaseName: `eksplorasa${stage}`,
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC, // Keep in public subnets for now
      },
      securityGroups: [dbSecurityGroup],
      allocatedStorage: 20,
      storageType: rds.StorageType.GP2,
      multiAz: false,
      publiclyAccessible: true, // Keep publicly accessible
      autoMinorVersionUpgrade: true,
      backupRetention: cdk.Duration.days(0),
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create Lambda Layer for pg8000
    const pg8000Layer = new lambda.LayerVersion(this, `Pg8000Layer-${stage}`, {
      code: lambda.Code.fromAsset("lambda", {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: ["bash", "-c", "mkdir -p /asset-output/python && pip install pg8000==1.30.3 -t /asset-output/python"],
        },
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: "pg8000 pure Python PostgreSQL driver",
    });

    // Create security group for Lambda
    const lambdaSecurityGroup = new ec2.SecurityGroup(this, `LambdaSecurityGroup-${stage}`, {
      vpc,
      description: "Security group for Lambda functions",
      allowAllOutbound: true,
    });

    // Create customer homepage lambda
    const customerHomepageLambda = new lambda.Function(this, `CustomerHomepageLambda-${stage}`, {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset("lambda", {
        exclude: ["requirements.txt"], // Exclude requirements.txt since we're using layers
      }),
      handler: "customer_homepage.handler",
      functionName: `eksplorasa-customer-homepage-${stage}`,
      layers: [pg8000Layer],
      vpc: vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC, // Move lambda to public subnet same as database
      },
      securityGroups: [lambdaSecurityGroup],
      allowPublicSubnet: true, // Allow lambda in public subnet
      environment: {
        DB_ENDPOINT: database.instanceEndpoint.hostname, // Use direct DB endpoint instead of proxy
        DB_PORT: "5432",
        DB_NAME: `eksplorasa${stage}`,
        DB_USERNAME: "eksplorasa",
        DB_PASSWORD: "eksplorasa2025",
      },
      timeout: cdk.Duration.seconds(30),
    });

    const customerHomepageFunctionUrl = customerHomepageLambda.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ["*"],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ["*"],
      },
    });

    dbSecurityGroup.addIngressRule(lambdaSecurityGroup, ec2.Port.tcp(5432), "Temporary: Allow Lambda direct access for testing");

    // Create restaurant detail lambda
    const restaurantDetailLambda = new lambda.Function(this, `RestaurantDetailLambda-${stage}`, {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset("lambda", {
        exclude: ["requirements.txt"], // Exclude requirements.txt since we're using layers
      }),
      handler: "customer_restaurant_detail.handler",
      functionName: `eksplorasa-restaurant-detail-${stage}`,
      layers: [pg8000Layer],
      vpc: vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC, // Move lambda to public subnet same as database
      },
      securityGroups: [lambdaSecurityGroup],
      allowPublicSubnet: true, // Allow lambda in public subnet
      environment: {
        DB_ENDPOINT: database.instanceEndpoint.hostname, // Use direct DB endpoint instead of proxy
        DB_PORT: "5432",
        DB_NAME: `eksplorasa${stage}`,
        DB_USERNAME: "eksplorasa",
        DB_PASSWORD: "eksplorasa2025",
      },
      timeout: cdk.Duration.seconds(30),
    });

    const restaurantDetailFunctionUrl = restaurantDetailLambda.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ["*"],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ["*"],
      },
    });

    new cdk.CfnOutput(this, `CustomerHomepageUrl-${stage}`, {
      value: customerHomepageFunctionUrl.url,
      exportName: `EksplorasaApi-${stage}-CustomerHomepageUrl`,
    });

    new cdk.CfnOutput(this, `RestaurantDetailUrl-${stage}`, {
      value: restaurantDetailFunctionUrl.url,
      exportName: `EksplorasaApi-${stage}-RestaurantDetailUrl`,
    });
  }
}
