import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

export class MyCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    new dynamodb.Table(this, 'MyFirstTable', {
      tableName: 'my-first-table',
      partitionKey: { 
        name: 'id', 
        type: dynamodb.AttributeType.STRING 
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY, 
    });
  }
}