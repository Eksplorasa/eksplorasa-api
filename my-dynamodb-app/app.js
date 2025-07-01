import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { PutCommand } from "@aws-sdk/lib-dynamodb";

const client = new DynamoDBClient({ region: "ap-southeast-2" });

async function addItem() {
  const params = {
    TableName: "my-first-table",
    Item: {
      id: "user_001",
      username: "presley",
    },
  };

  try {
    const data = await client.send(new PutCommand(params));
    console.log("Success - item added:", data);
  } catch (err) {
    console.error("Error", err.stack);
  }
}

addItem();