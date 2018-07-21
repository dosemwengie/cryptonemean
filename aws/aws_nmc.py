from decimal import Decimal
import boto3
import json
import requests
import os


#coin_table=boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('coins')
#user_table=boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('users')


user_example = {'preference': {
  'XLM': {'allocation': Decimal('0.25'),
   'buy': Decimal('-0.1'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.15')},
  'ADA': {'allocation': Decimal('0.25'),
   'buy': Decimal('-0.20'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.10')}},
 'username': 'Nemean',
 'wallet': Decimal('250.0')}



URL = 'https://api.coinmarketcap.com/v2/ticker/?convert=USD&limit=50'
FEE = Decimal('0.001')
THRESHOLD=1209600

class NMC():
	def __init__(self):
		self.region=os.environ.get('AWS_REGION')
		self.coin_table,self.user_table = None, None
		self.set_db()
		self.fetch_online_data()
		self.insert_data()
		self.map_user_evaluation()

	def set_db(self):
		if not self.region:
			self.coin_table = boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('coins')
			self.user_table = boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('users')
		else:
			self.coin_table = boto3.resource('dynamodb').Table('coins')
			self.user_table = boto3.resource('dynamodb').Table('users')
			
	def fetch_online_data(self):
		print("Getting online data")
		response = requests.get(URL)
		self.online_data = response.json().get('data')

		self.traverse_dictionary()

	def traverse_dictionary(self):
		keys = self.online_data.keys()
		for key in keys:
			new_key = self.online_data[key]['symbol']
			self.online_data[new_key] = self.online_data.pop(key)

			

	def insert_data(self):
		print("Inserting Data into DynamoDB")
		with self.coin_table.batch_writer() as batch:
			for coin in self.online_data:
				if coin not in self.online_data:
					continue		
				data = self.online_data[coin]
				supplies = ['circulating_supply','max_supply','total_supply']
				for supply in supplies:
					if data[supply] is None:
						data[supply] = Decimal('0')
					else:
						data[supply] = Decimal(str(data[supply]))
				item={
					'name':data['name'],
					'last_updated':data['last_updated'],
					'rank':data['rank'],
					'symbol':data['symbol'],
					'quotes':data['quotes'],
					'circulating_supply':data['circulating_supply'],
					'id':data['id'],
					'max_supply':data['max_supply'],
					'total_supply':data['total_supply'],
					'website_slug':data['website_slug'],
					'expiration':data['last_updated']+THRESHOLD
				}
				for numericals in item['quotes']['USD']:
					if item['quotes']['USD'][numericals] is None:
						item['quotes']['USD'][numericals] = Decimal('0')
					else:
					 item['quotes']['USD'][numericals] = Decimal(str(item['quotes']['USD'][numericals]))

				batch.put_item(
					Item=item
		)
	def map_user_evaluation(self):
		response = self.user_table.scan()
		users = response['Items']
		map(self.data_evaluation,users)

	def data_evaluation(self,user_data):
		print("User: %s"%(user_data['name']))
		for coin in user_data['preference']:
			print("Checking coin: %s"%(coin))
			coin_data = user_data['preference'][coin]
			can_sell, can_buy = False, False
			current_price = self.online_data[coin]['quotes']['USD']['price']
			current_price=Decimal(current_price)
			percentages = [ self.online_data[coin]['quotes']['USD'][x] for x in self.online_data[coin]['quotes']['USD'] if x.startswith('percent_change')]
			buy_percentage = coin_data['buy']*100
			sell_percentage = coin_data['sell']*100
			print("Percentages: %s"%(percentages))
			print(coin_data)
			if coin_data['coin_amount'] == 0:
				if buy_percentage >= min(percentages):
					can_buy = True
			else:
				worth_per_coin = coin_data['coin_amount']/coin_data['holdings']
				if (current_price - worth_per_coin)/100 <= buy_percentage:
					can_buy = True
				elif (current_price - worth_per_coin)/100 >= sell_percentage:
					can_sell = True 
			
			print("Before Wallet %s"%(user_data['wallet']))
			if can_buy:
				self.do_transaction(coin,user_data,current_price,action='buy')
			if can_sell:
				self.do_transaction(coin,user_data,current_price,action='sell')
		print(user_data)
		self.user_table.put_item(Item=user_data)
	def do_transaction(self,coin,user_data,current_price,action=None):
		wallet = user_data['wallet']
		allocation = user_data['preference'][coin]['allocation']
		coin_amount = user_data['preference'][coin]['coin_amount']
		quota = user_data['preference'][coin]['quota']
		holdings = user_data['preference'][coin]['holdings']
		if quota:
			print("Quota reached!")
			return

		if action == 'buy':
			limit = Decimal(allocation * wallet)
			wallet_factor = -1
			holding_coin_factor = 1
			user_data['preference'][coin]['quota'] = True
			

		elif action == 'sell':
			limit = Decimal(current_price * coin_amount)
			wallet_factor = 1
			holding_coin_factor = -1
			user_data['preference'][coin]['quota'] = False

		else:
			raise Exception('action needed')

		fee = limit * FEE
		real_limit = limit - fee
		new_coins = real_limit/current_price
		user_data['wallet'] += limit * wallet_factor
		user_data['preference'][coin]['holdings'] += real_limit * holding_coin_factor
		user_data['preference'][coin]['coin_amount'] += new_coins * holding_coin_factor
		print("User %s, %s:%s worth of %s"%(user_data["name"],action,real_limit,coin))
		print("After Wallet %s"%(user_data['wallet']))
		print("Holdings %s\nCoin Amount %s"%(user_data['preference'][coin]['holdings'],user_data['preference'][coin]['coin_amount']))

_=NMC()

'''

Compare the price of each coin in preference

we dont have the coin
	if any quotes.USD.percent_change <= buy:
		can we afford it(at most allocation amount or lower)
			yes - purchase allocation amount or lower
				update holdings,coin_amount, wallet
	

we already have the coin
	if (current_price - worth_per_coin)/100 <= buy
		can we afford it
			yes - purchase allocation amount or lower
				update holdings,coin_amount, wallet
	elif (current_price - worth_per_coin)/100 >= sell
		sell the coin
			update holdings,coin_amount, wallet

'''
