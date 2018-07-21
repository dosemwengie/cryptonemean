import boto3

db = boto3.client('dynamodb',endpoint_url='http://localhost:8000')
db.delete_table(TableName='users')
db.create_table(
TableName='users',
KeySchema=[
	{
		'AttributeName':'name',
		'KeyType': 'HASH'
	}
	
],
AttributeDefinitions=[
	{
		'AttributeName':'name',
		'AttributeType':'S'
	}
],
ProvisionedThroughput={
        'ReadCapacityUnits': 5,
        'WriteCapacityUnits': 5
    }

)

db.delete_table(TableName='coins')
db.create_table(
TableName='coins',
KeySchema=[
	{
		'AttributeName':'name',
		'KeyType': 'HASH'
	},
	{
		'AttributeName':'last_updated',
		'KeyType': 'RANGE'
	},
	
],
AttributeDefinitions=[
	{
		'AttributeName':'name',
		'AttributeType':'S'
	},
	{
		'AttributeName':'last_updated',
		'AttributeType':'N'
	},
	
	{
		'AttributeName':'expiration',
		'AttributeType':'N'
	}
],
LocalSecondaryIndexes=[
{
'IndexName': 'ExpirationIdx',
'KeySchema':[
	{
		'AttributeName':'name',
		'KeyType': 'HASH'
	},
	{
		'AttributeName':'expiration',
		'KeyType': 'RANGE'
	}
],
'Projection': {
	'ProjectionType': 'ALL'
}
}
],
ProvisionedThroughput={
        'ReadCapacityUnits': 5,
        'WriteCapacityUnits': 5
    }

)

db.update_time_to_live(
TableName='coins',
TimeToLiveSpecification={
	'Enabled': True,
	'AttributeName':'expiration'
}
)
