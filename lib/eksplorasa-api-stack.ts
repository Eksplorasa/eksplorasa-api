import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';

export class EksplorasaApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get stage from context, environment variable, or default to 'prod'
    const stage = this.node.tryGetContext('stage') || process.env.STAGE || 'prod';

    // Create VPC for RDS database
    const vpc = new ec2.Vpc(this, `EksplorasaVpc-${stage}`, {
      maxAzs: 2,
      natGateways: 2, // Need at least one NAT gateway for RDS Proxy
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        }
      ],
    });

    // Create security group for RDS - allow public PostgreSQL access
    const dbSecurityGroup = new ec2.SecurityGroup(this, `DbSecurityGroup-${stage}`, {
      vpc,
      description: 'Security group for RDS PostgreSQL database - publicly accessible',
      allowAllOutbound: true,
    });

    // Allow PostgreSQL access from VPC and anywhere on IPv4
    dbSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      'Allow PostgreSQL access from VPC'
    );
    
    dbSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(5432),
      'Allow PostgreSQL access from anywhere'
    );

    const database = new rds.DatabaseInstance(this, `EksplorasaDatabase${stage}`, {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_17_5,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO), 
      credentials: rds.Credentials.fromPassword('eksplorasa', cdk.SecretValue.unsafePlainText('eksplorasa2025')),
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
      code: lambda.Code.fromAsset('lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'mkdir -p /asset-output/python && pip install pg8000==1.30.3 -t /asset-output/python'
          ],
        },
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'pg8000 pure Python PostgreSQL driver',
    });

    // Create security group for Lambda
    const lambdaSecurityGroup = new ec2.SecurityGroup(this, `LambdaSecurityGroup-${stage}`, {
      vpc,
      description: 'Security group for Lambda functions',
      allowAllOutbound: true,
    });


    // Create customer homepage lambda
    const customerHomepageLambda = new lambda.Function(this, `CustomerHomepageLambda-${stage}`, {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset('lambda', {
        exclude: ['requirements.txt'], // Exclude requirements.txt since we're using layers
      }),
      handler: 'customer_homepage.handler',
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
        DB_PORT: '5432',
        DB_NAME: `eksplorasa${stage}`,
        DB_USERNAME: 'eksplorasa',
        DB_PASSWORD: 'eksplorasa2025',
      },
      timeout: cdk.Duration.seconds(30),
    });

    const customerHomepageFunctionUrl = customerHomepageLambda.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ['*'],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ['*'],
      },
    });

    dbSecurityGroup.addIngressRule(
      lambdaSecurityGroup,
      ec2.Port.tcp(5432),
      'Temporary: Allow Lambda direct access for testing'
    );


    new cdk.CfnOutput(this, `CustomerHomepageUrl-${stage}`, {
      value: customerHomepageFunctionUrl.url,
      exportName: `EksplorasaApi-${stage}-CustomerHomepageUrl`,
    });

    // Create browse API lambda
    const browseApiLambda = new lambda.Function(this, `BrowseApiLambda-${stage}`, {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset('lambda', {
        exclude: ['requirements.txt'], // Exclude requirements.txt since we're using layers
      }),
      handler: 'browse_api.handler',
      functionName: `eksplorasa-browse-api-${stage}`,
      layers: [pg8000Layer],
      vpc: vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC, // Move lambda to public subnet same as database
      },
      securityGroups: [lambdaSecurityGroup],
      allowPublicSubnet: true, // Allow lambda in public subnet
      environment: {
        DB_ENDPOINT: database.instanceEndpoint.hostname, // Use direct DB endpoint instead of proxy
        DB_PORT: '5432',
        DB_NAME: 'postgres',
        DB_USERNAME: 'eksplorasa',
        DB_PASSWORD: 'eksplorasa2025',
      },
      timeout: cdk.Duration.seconds(30),
    });

    // Create API Gateway for Browse API
    const browseApi = new apigateway.RestApi(this, `BrowseApi-${stage}`, {
      restApiName: `Eksplorasa Browse API - ${stage}`,
      description: 'REST API for browsing restaurants with filtering capabilities',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
      deployOptions: {
        stageName: stage,
        loggingLevel: apigateway.MethodLoggingLevel.OFF,
        dataTraceEnabled: false,
        metricsEnabled: true,
      },
    });

    // Create Lambda integration for Browse API
    const browseIntegration = new apigateway.LambdaIntegration(browseApiLambda, {
      requestTemplates: { 'application/json': '{ "statusCode": "200" }' },
    });

    // Define API routes for Browse API
    const explore = browseApi.root.addResource('explore');
    explore.addMethod('GET', browseIntegration, {
      requestParameters: {
        'method.request.querystring.sort': false,
        'method.request.querystring.timeStart': false,
        'method.request.querystring.timeEnd': false,
        'method.request.querystring.minPrice': false,
        'method.request.querystring.maxPrice': false,
        'method.request.querystring.cuisines': false,
        'method.request.querystring.bagTypes': false,
        'method.request.querystring.maxDistance': false,
        'method.request.querystring.latitude': false,
        'method.request.querystring.longitude': false,
      },
    });


    // Export the Browse API URL for reference
    new cdk.CfnOutput(this, `BrowseApiUrl-${stage}`, {
      value: browseApi.url,
      exportName: `EksplorasaApi-${stage}-BrowseApiUrl`,
      description: 'Browse API Gateway URL',
    });
  }
}
